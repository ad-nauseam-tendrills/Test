import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image as PILImage

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.storage import (
    ensure_storage_dirs,
    generate_storage_key,
    upload_path,
    validate_upload,
    variant_path,
)
from app.db.session import get_db
from app.models.image_analysis import ImageAnalysis
from app.models.image_variant import ImageVariant
from app.models.instagram_account import InstagramAccount
from app.models.recommendation import Recommendation
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.image import (
    AnalyzeImageResponse,
    GenerateVariantRequest,
    ImageAnalysisRead,
    ImageVariantRead,
    RecommendationRead,
    ScoreBreakdown,
    ScoreReport,
    UploadedImageRead,
)
from app.services.analytics.dashboard import build_dashboard
from app.services.image_analysis.metrics import analyze_image
from app.services.image_processing.optimizer import Adjustments, apply_adjustments
from app.services.recommendations.rules import generate_recommendations
from app.services.recommendations.scoring import (
    score_historical_similarity,
    score_image_readiness,
    score_overall_readiness,
    score_timing_opportunity,
)

router = APIRouter(prefix="/images", tags=["images"])


def _to_public_url(kind: str, storage_key: str) -> str:
    return f"{settings.API_V1_PREFIX}/images/file/{kind}/{storage_key}"


_SAFE_STORAGE_KEY = re.compile(r"^[a-zA-Z0-9_-]+\.(jpg|jpeg|png|webp)$")


@router.get("/file/{kind}/{storage_key}")
def get_image_file(kind: str, storage_key: str):
    """
    Serve a stored upload or generated variant. storage_key is always a
    randomly generated, extension-suffixed filename (never user input
    passed through) and is validated against a strict pattern here as an
    additional guard against path traversal.
    """
    if kind not in ("uploads", "variants") or not _SAFE_STORAGE_KEY.match(storage_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    path = upload_path(storage_key) if kind == "uploads" else variant_path(storage_key)
    if not os.path.isfile(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(path)


@router.post("/upload", response_model=UploadedImageRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_storage_dirs()
    contents = await file.read()
    extension = validate_upload(file, len(contents))

    storage_key = generate_storage_key(extension)
    dest_path = upload_path(storage_key)
    with open(dest_path, "wb") as f:
        f.write(contents)

    try:
        with PILImage.open(dest_path) as im:
            im.verify()
        with PILImage.open(dest_path) as im:
            width, height = im.size
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid image")

    image = UploadedImage(
        user_id=current_user.id,
        storage_key=storage_key,
        original_filename=file.filename or "upload",
        content_type=file.content_type,
        file_size_bytes=len(contents),
        width=width,
        height=height,
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    result = UploadedImageRead.model_validate(image)
    result.url = _to_public_url("uploads", storage_key)
    return result


@router.get("", response_model=list[UploadedImageRead])
def list_images(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    images = (
        db.query(UploadedImage)
        .filter(UploadedImage.user_id == current_user.id)
        .order_by(UploadedImage.created_at.desc())
        .all()
    )
    output = []
    for image in images:
        item = UploadedImageRead.model_validate(image)
        item.url = _to_public_url("uploads", image.storage_key)
        output.append(item)
    return output


def _get_owned_image(db: Session, image_id: str, user: User) -> UploadedImage:
    image = db.get(UploadedImage, image_id)
    if not image or image.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


@router.post("/{image_id}/analyze", response_model=AnalyzeImageResponse)
def analyze_uploaded_image(
    image_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    image = _get_owned_image(db, image_id, current_user)
    metrics = analyze_image(upload_path(image.storage_key))

    # Historical context, derived only from this user's own connected
    # account(s) -- never from other users' data.
    account = (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id, InstagramAccount.is_active.is_(True))
        .first()
    )
    dashboard = None
    if account:
        dashboard = build_dashboard(db, account.id)

    historical_context = {
        "avg_brightness": None,  # v0.1 does not re-analyze historical post images; see README limitations
        "avg_contrast": None,
        "posting_windows": dashboard["posting_windows"] if dashboard else None,
        "has_enough_data": dashboard["has_enough_data"] if dashboard else False,
    }

    drafts, adjustments = generate_recommendations(metrics, historical_context)

    readiness = score_image_readiness(metrics)

    if dashboard:
        historical_similarity = score_historical_similarity(
            metrics, dashboard["by_media_type"], dashboard["overview"]["total_posts"]
        )
    else:
        historical_similarity = score_historical_similarity(metrics, [], 0)

    # Timing opportunity reflects the moment of analysis (current day/hour
    # vs. this account's own historical pattern). Computed now, alongside
    # the other sections, and persisted as a snapshot -- re-run "Analyze"
    # at a different time to get a fresh read.
    now = datetime.now(timezone.utc)
    if dashboard:
        timing = score_timing_opportunity(
            current_hour=now.hour,
            current_day_index=now.weekday(),
            by_day_of_week=dashboard["by_day_of_week"],
            by_hour_of_day=dashboard["by_hour_of_day"],
            total_posts=dashboard["overview"]["total_posts"],
        )
    else:
        timing = score_timing_opportunity(now.hour, now.weekday(), [], [], 0)

    overall = score_overall_readiness(readiness, timing, historical_similarity)

    score_report = {
        "image_readiness": vars(readiness),
        "timing_opportunity": vars(timing),
        "historical_similarity": vars(historical_similarity),
        "overall_readiness": vars(overall),
    }

    analysis = ImageAnalysis(
        image_id=image.id,
        width=metrics.width,
        height=metrics.height,
        aspect_ratio=metrics.aspect_ratio,
        brightness=metrics.brightness,
        contrast=metrics.contrast,
        saturation=metrics.saturation,
        color_temperature=metrics.color_temperature,
        sharpness=metrics.sharpness,
        highlight_clipping_pct=metrics.highlight_clipping_pct,
        shadow_clipping_pct=metrics.shadow_clipping_pct,
        face_count=len(metrics.faces),
        largest_face_area_ratio=max((f.area_ratio for f in metrics.faces), default=None),
        subject_offset_x=metrics.subject_offset_x,
        subject_offset_y=metrics.subject_offset_y,
        negative_space_ratio=metrics.negative_space_ratio,
        dominant_colors=metrics.dominant_colors,
        raw_metrics={**metrics.raw, "suggested_adjustments": adjustments.to_dict(), "score_report": score_report},
        image_readiness_score=readiness.score,
        historical_similarity_score=historical_similarity.score,
    )
    db.add(analysis)
    db.flush()

    for draft in drafts:
        db.add(
            Recommendation(
                analysis_id=analysis.id,
                category=draft.category,
                severity=draft.severity,
                title=draft.title,
                detail=draft.detail,
                rule_id=draft.rule_id,
                metadata_json=draft.metadata,
            )
        )
    db.commit()
    db.refresh(analysis)

    return AnalyzeImageResponse(
        analysis=_analysis_to_schema(analysis),
        scores=ScoreReport(
            image_readiness=ScoreBreakdown(**vars(readiness)),
            timing_opportunity=ScoreBreakdown(**vars(timing)),
            historical_similarity=ScoreBreakdown(**vars(historical_similarity)),
            overall_readiness=ScoreBreakdown(**vars(overall)),
        ),
        recommendations=[RecommendationRead.model_validate(r) for r in analysis.recommendations],
    )


def _analysis_to_schema(analysis: ImageAnalysis) -> ImageAnalysisRead:
    return ImageAnalysisRead.model_validate(analysis)


@router.get("/{image_id}", response_model=dict)
def get_image_detail(image_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    image = _get_owned_image(db, image_id, current_user)
    latest_analysis = (
        db.query(ImageAnalysis)
        .filter(ImageAnalysis.image_id == image.id)
        .order_by(ImageAnalysis.created_at.desc())
        .first()
    )
    variants = (
        db.query(ImageVariant)
        .filter(ImageVariant.image_id == image.id)
        .order_by(ImageVariant.created_at.desc())
        .all()
    )

    image_out = UploadedImageRead.model_validate(image)
    image_out.url = _to_public_url("uploads", image.storage_key)

    variants_out = []
    for v in variants:
        vout = ImageVariantRead.model_validate(v)
        vout.url = _to_public_url("variants", v.storage_key)
        variants_out.append(vout)

    analysis_out = None
    recommendations_out = []
    scores_out = None
    if latest_analysis:
        analysis_out = _analysis_to_schema(latest_analysis)
        recommendations_out = [RecommendationRead.model_validate(r) for r in latest_analysis.recommendations]
        score_report = latest_analysis.raw_metrics.get("score_report")
        if score_report:
            scores_out = ScoreReport(
                image_readiness=ScoreBreakdown(**score_report["image_readiness"]),
                timing_opportunity=ScoreBreakdown(**score_report["timing_opportunity"]),
                historical_similarity=ScoreBreakdown(**score_report["historical_similarity"]),
                overall_readiness=ScoreBreakdown(**score_report["overall_readiness"]),
            )

    return {
        "image": image_out,
        "analysis": analysis_out,
        "scores": scores_out,
        "recommendations": recommendations_out,
        "variants": variants_out,
    }


@router.post("/{image_id}/generate-variant", response_model=ImageVariantRead)
def generate_variant(
    image_id: str,
    payload: GenerateVariantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = _get_owned_image(db, image_id, current_user)
    latest_analysis = (
        db.query(ImageAnalysis)
        .filter(ImageAnalysis.image_id == image.id)
        .order_by(ImageAnalysis.created_at.desc())
        .first()
    )
    if not latest_analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analyze this image before generating an optimized version.",
        )

    suggested = latest_analysis.raw_metrics.get("suggested_adjustments", {})
    adjustments = Adjustments(
        exposure=suggested.get("exposure", 0.0),
        contrast=suggested.get("contrast", 0.0),
        white_balance_shift=suggested.get("white_balance_shift", 0.0),
        highlight_recovery=suggested.get("highlight_recovery", 0.0),
        shadow_recovery=suggested.get("shadow_recovery", 0.0),
        saturation=suggested.get("saturation", 0.0),
        sharpen_amount=suggested.get("sharpen_amount", 0.0),
        crop_box=tuple(suggested["crop_box"]) if suggested.get("crop_box") else None,
        target_aspect_ratio=suggested.get("target_aspect_ratio"),
        rotation_degrees=suggested.get("rotation_degrees", 0.0),
    )

    if payload.overrides:
        o = payload.overrides
        adjustments = Adjustments(
            exposure=o.exposure,
            contrast=o.contrast,
            white_balance_shift=o.white_balance_shift,
            highlight_recovery=o.highlight_recovery,
            shadow_recovery=o.shadow_recovery,
            saturation=o.saturation,
            sharpen_amount=o.sharpen_amount,
            crop_box=tuple(o.crop_box) if o.crop_box else adjustments.crop_box,
            target_aspect_ratio=o.target_aspect_ratio or adjustments.target_aspect_ratio,
            rotation_degrees=0.0,
        )

    ensure_storage_dirs()
    result_image = apply_adjustments(
        upload_path(image.storage_key), adjustments, artwork_integrity_mode=payload.artwork_integrity_mode
    )

    applied = adjustments.clamped() if payload.artwork_integrity_mode else adjustments

    storage_key = f"{uuid.uuid4().hex}.jpg"
    result_image.save(variant_path(storage_key), format="JPEG", quality=92)

    variant = ImageVariant(
        image_id=image.id,
        storage_key=storage_key,
        width=result_image.width,
        height=result_image.height,
        artwork_integrity_mode=payload.artwork_integrity_mode,
        adjustments=applied.to_dict(),
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)

    out = ImageVariantRead.model_validate(variant)
    out.url = _to_public_url("variants", storage_key)
    return out
