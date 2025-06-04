// UI and Theme Types
export type Theme = 'light' | 'dark' | 'system';

// Core application types
export interface User {
  id: string;
  email: string;
  name?: string;
  avatar_url?: string;
  created_at: string;
  updated_at: string;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: User;
}

// Video analysis types
export interface VideoInfo {
  id: string;
  title: string;
  description: string;
  duration: number;
  thumbnail_url: string;
  channel_name: string;
  upload_date: string;
  view_count?: number;
  like_count?: number;
}

export interface VideoAnalysisRequest {
  youtube_url: string;
  analysis_types: string[];
  model_name?: string;
  temperature?: number;
  use_cache?: boolean;
}

export interface AnalysisResult {
  video_id: string;
  title: string;
  description: string;
  duration: number;
  thumbnail_url: string;
  transcript: string;
  transcript_segments?: TranscriptSegment[];
  task_outputs: Record<string, string>;
  token_usage: TokenUsage;
  created_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
}

// Chat types
export interface ChatSession {
  id: string;
  title: string;
  video_id?: string;
  messages?: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  token_usage?: TokenUsage;
}

export interface ChatMessageRequest {
  session_id: string;
  message: string;
  model_name?: string;
  temperature?: number;
  use_context?: boolean;
}

// UI State types
export interface Notification {
  id: string;
  title: string;
  description?: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

export interface Settings {
  modelName: string;
  temperature: number;
  transcriptionModel: string;
  subtitleLanguage: string;
  useCache: boolean;
  analysisTypes: string[];
}

// API Response types
export interface ApiResponse<T = any> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, any>;
}

// Configuration types
export interface ModelInfo {
  name: string;
  display_name: string;
  description: string;
  max_tokens: number;
  cost_per_token: number;
}

export interface LanguageInfo {
  code: string;
  name: string;
  native_name: string;
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'down';
  version: string;
  uptime: number;
  services: Record<string, 'healthy' | 'degraded' | 'down'>;
}

// User statistics
export interface UserStats {
  total_analyses: number;
  total_tokens_used: number;
  total_cost: number;
  analyses_this_month: number;
  tokens_this_month: number;
  cost_this_month: number;
}

// Subtitle types
export interface SubtitleData {
  language: string;
  content: string;
  format: 'srt' | 'vtt' | 'txt';
}

export interface SubtitleTranslationRequest {
  video_id: string;
  target_language: string;
  source_language?: string;
}

// Analysis progress types
export interface AnalysisProgress {
  video_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  estimated_time_remaining?: number;
  error?: string;
}

// WebSocket message types
export interface WebSocketMessage {
  type: 'message_start' | 'message_chunk' | 'message_complete' | 'error';
  messageId?: string;
  chunk?: string;
  tokenUsage?: TokenUsage;
  error?: string;
}

// Form validation types
export interface FormErrors {
  [key: string]: string | string[];
}

// Cache types
export interface CacheStats {
  total_entries: number;
  total_size_mb: number;
  hit_rate: number;
  oldest_entry: string;
  newest_entry: string;
}

export interface CacheClearRequest {
  video_ids?: string[];
  older_than_days?: number;
  clear_all?: boolean;
}

export interface CacheClearResponse {
  cleared_entries: number;
  freed_space_mb: number;
}