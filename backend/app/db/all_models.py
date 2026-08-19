"""
Import every ORM model module so Base.metadata is fully populated.

This module is imported by Alembic (env.py) and by anything that needs
Base.metadata.create_all() to see every table (e.g. the test suite). It
is deliberately NOT imported by app.db.base itself, to avoid a circular
import between models and the declarative base they depend on.
"""
from app.models.user import User  # noqa: F401
from app.models.instagram_account import InstagramAccount  # noqa: F401
from app.models.instagram_post import InstagramPost  # noqa: F401
from app.models.instagram_post_metric import InstagramPostMetric  # noqa: F401
from app.models.uploaded_image import UploadedImage  # noqa: F401
from app.models.image_analysis import ImageAnalysis  # noqa: F401
from app.models.image_variant import ImageVariant  # noqa: F401
from app.models.recommendation import Recommendation  # noqa: F401
from app.models.prediction_score import PredictionScore  # noqa: F401
from app.models.generated_caption import GeneratedCaption  # noqa: F401
from app.models.scheduled_post import ScheduledPost  # noqa: F401
from app.models.post_outcome import PostOutcome  # noqa: F401
from app.models.experiment import Experiment, ExperimentVariant  # noqa: F401

from app.db.base import Base  # noqa: F401
