export interface User {
  id: string;
  email: string;
  full_name: string | null;
  artwork_integrity_enabled: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface InstagramAccount {
  id: string;
  provider: string;
  ig_user_id: string;
  username: string;
  account_type: string;
  profile_picture_url: string | null;
  follower_count: number | null;
  is_active: boolean;
  last_synced_at: string | null;
}

export interface PostMetric {
  likes: number | null;
  comments: number | null;
  saves: number | null;
  shares: number | null;
  reach: number | null;
  impressions: number | null;
  profile_visits: number | null;
}

export interface InstagramPost {
  id: string;
  ig_media_id: string;
  media_type: "IMAGE" | "CAROUSEL_ALBUM" | "VIDEO";
  caption: string | null;
  media_url: string | null;
  permalink: string | null;
  thumbnail_url: string | null;
  posted_at: string;
  follower_count_at_posting: number | null;
  metrics: PostMetric | null;
  engagement_rate: number | null;
  performance_index: number | null;
}

export interface OverviewStats {
  total_posts: number;
  avg_reach: number | null;
  avg_engagement_rate: number | null;
  avg_saves: number | null;
  has_enough_data: boolean;
  message: string | null;
}

export interface DayOfWeekStat {
  day: string;
  day_index: number;
  post_count: number;
  avg_engagement_rate: number | null;
}

export interface HourOfDayStat {
  hour: number;
  post_count: number;
  avg_engagement_rate: number | null;
}

export interface MediaTypeStat {
  media_type: string;
  post_count: number;
  avg_engagement_rate: number | null;
  avg_reach: number | null;
}

export interface DashboardResponse {
  overview: OverviewStats;
  best_posts: InstagramPost[];
  recent_posts: InstagramPost[];
  by_day_of_week: DayOfWeekStat[];
  by_hour_of_day: HourOfDayStat[];
  by_media_type: MediaTypeStat[];
  has_enough_data: boolean;
  insufficient_data_message: string | null;
}

export interface UploadedImage {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  width: number;
  height: number;
  created_at: string;
  url: string | null;
}

export interface DominantColor {
  hex: string;
  ratio: number;
}

export interface ImageAnalysis {
  id: string;
  image_id: string;
  width: number;
  height: number;
  aspect_ratio: number;
  brightness: number;
  contrast: number;
  saturation: number;
  color_temperature: number;
  sharpness: number;
  highlight_clipping_pct: number;
  shadow_clipping_pct: number;
  face_count: number;
  largest_face_area_ratio: number | null;
  subject_offset_x: number | null;
  subject_offset_y: number | null;
  negative_space_ratio: number | null;
  dominant_colors: DominantColor[];
  image_readiness_score: number;
  historical_similarity_score: number | null;
}

export interface ScoreBreakdown {
  score: number;
  label: string;
  explanation: string;
}

export interface ScoreReport {
  image_readiness: ScoreBreakdown;
  timing_opportunity: ScoreBreakdown;
  historical_similarity: ScoreBreakdown;
  overall_readiness: ScoreBreakdown;
}

export interface Recommendation {
  id: string;
  category: string;
  severity: "info" | "suggestion" | "warning";
  title: string;
  detail: string;
  rule_id: string;
}

export interface AnalyzeImageResponse {
  analysis: ImageAnalysis;
  scores: ScoreReport;
  recommendations: Recommendation[];
}

export interface ImageVariant {
  id: string;
  image_id: string;
  width: number;
  height: number;
  artwork_integrity_mode: boolean;
  adjustments: Record<string, unknown>;
  created_at: string;
  url: string | null;
}

export interface ImageDetail {
  image: UploadedImage;
  analysis: ImageAnalysis | null;
  scores: ScoreReport | null;
  recommendations: Recommendation[];
  variants: ImageVariant[];
}
