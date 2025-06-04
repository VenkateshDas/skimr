// Application constants
export const APP_CONFIG = {
  NAME: process.env.NEXT_PUBLIC_APP_NAME || 'YouTube Analysis',
  VERSION: '1.0.0',
  DESCRIPTION: 'AI-powered YouTube video analysis and chat',
} as const;

// API Configuration
export const API_CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  TIMEOUT: parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || '30000'),
} as const;

// Feature flags
export const FEATURES = {
  CHAT: process.env.NEXT_PUBLIC_ENABLE_CHAT !== 'false',
  SUBTITLES: process.env.NEXT_PUBLIC_ENABLE_SUBTITLES !== 'false',
  HIGHLIGHTS: process.env.NEXT_PUBLIC_ENABLE_HIGHLIGHTS === 'true',
  ANALYTICS: process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === 'true',
} as const;

// User limits
export const USER_LIMITS = {
  MAX_GUEST_ANALYSES: parseInt(process.env.NEXT_PUBLIC_MAX_GUEST_ANALYSES || '3'),
  MAX_CHAT_MESSAGES_PER_SESSION: 100,
  MAX_FILE_SIZE_MB: 10,
} as const;

// Analysis types
export const ANALYSIS_TYPES = [
  {
    id: 'summary',
    label: 'Summary & Classification',
    description: 'Get a comprehensive summary and content classification',
    taskKey: 'classify_and_summarize_content',
    icon: '📊',
    default: true,
  },
  {
    id: 'action_plan',
    label: 'Action Plan',
    description: 'Generate actionable steps based on video content',
    taskKey: 'analyze_and_plan_content',
    icon: '📋',
    default: false,
  },
  {
    id: 'blog_post',
    label: 'Blog Post',
    description: 'Create a blog post from video content',
    taskKey: 'write_blog_post',
    icon: '📝',
    default: false,
  },
  {
    id: 'linkedin_post',
    label: 'LinkedIn Post',
    description: 'Generate a professional LinkedIn post',
    taskKey: 'write_linkedin_post',
    icon: '💼',
    default: false,
  },
  {
    id: 'tweet',
    label: 'X Tweet',
    description: 'Create engaging tweets from video content',
    taskKey: 'write_tweet',
    icon: '🐦',
    default: false,
  },
] as const;

// Model configurations
export const MODEL_CONFIGS = [
  {
    name: 'gpt-4o-mini',
    displayName: 'GPT-4o Mini',
    description: 'Fast and cost-effective for most tasks',
    maxTokens: 128000,
    costPerToken: 0.00015,
    defaultTemperature: 0.7,
  },
  {
    name: 'gpt-4o',
    displayName: 'GPT-4o',
    description: 'Most capable model for complex analysis',
    maxTokens: 128000,
    costPerToken: 0.005,
    defaultTemperature: 0.7,
  },
  {
    name: 'claude-3-haiku',
    displayName: 'Claude 3 Haiku',
    description: 'Fast and efficient for quick analysis',
    maxTokens: 200000,
    costPerToken: 0.00025,
    defaultTemperature: 0.7,
  },
] as const;

// Transcription models
export const TRANSCRIPTION_MODELS = [
  {
    name: 'openai',
    displayName: 'OpenAI Whisper',
    description: 'High-quality transcription with good accuracy',
  },
  {
    name: 'youtube',
    displayName: 'YouTube Auto-generated',
    description: 'Use existing YouTube captions when available',
  },
] as const;

// Supported languages
export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'es', name: 'Spanish', nativeName: 'Español' },
  { code: 'fr', name: 'French', nativeName: 'Français' },
  { code: 'de', name: 'German', nativeName: 'Deutsch' },
  { code: 'it', name: 'Italian', nativeName: 'Italiano' },
  { code: 'pt', name: 'Portuguese', nativeName: 'Português' },
  { code: 'ru', name: 'Russian', nativeName: 'Русский' },
  { code: 'ja', name: 'Japanese', nativeName: '日本語' },
  { code: 'ko', name: 'Korean', nativeName: '한국어' },
  { code: 'zh', name: 'Chinese', nativeName: '中文' },
] as const;

// Subtitle languages (alias for SUPPORTED_LANGUAGES)
export const SUBTITLE_LANGUAGES = SUPPORTED_LANGUAGES;

// Default settings
export const DEFAULT_SETTINGS = {
  modelName: 'gpt-4o-mini',
  temperature: 0.7,
  transcriptionModel: 'openai',
  subtitleLanguage: 'en',
  useCache: true,
  analysisTypes: ['summary'],
} as const;

// UI Constants
export const UI_CONSTANTS = {
  SIDEBAR_WIDTH: 256,
  HEADER_HEIGHT: 64,
  MOBILE_BREAKPOINT: 768,
  TABLET_BREAKPOINT: 1024,
  DESKTOP_BREAKPOINT: 1280,
} as const;

// Animation durations (in milliseconds)
export const ANIMATIONS = {
  FAST: 150,
  NORMAL: 300,
  SLOW: 500,
  VERY_SLOW: 1000,
} as const;

// Notification durations (in milliseconds)
export const NOTIFICATION_DURATIONS = {
  SUCCESS: 5000,
  INFO: 5000,
  WARNING: 7000,
  ERROR: 10000,
} as const;

// YouTube URL patterns
export const YOUTUBE_URL_PATTERNS = [
  /^https?:\/\/(www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
  /^https?:\/\/(www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
  /^https?:\/\/youtu\.be\/([a-zA-Z0-9_-]{11})/,
  /^https?:\/\/(www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})/,
] as const;

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network connection failed. Please check your internet connection.',
  INVALID_URL: 'Please enter a valid YouTube URL.',
  UNAUTHORIZED: 'You need to be logged in to perform this action.',
  RATE_LIMIT: 'Too many requests. Please wait before trying again.',
  SERVER_ERROR: 'Server error occurred. Please try again later.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  GUEST_LIMIT_EXCEEDED: 'Guest analysis limit exceeded. Please sign in to continue.',
} as const;

// Success messages
export const SUCCESS_MESSAGES = {
  ANALYSIS_COMPLETE: 'Video analysis completed successfully!',
  CONTENT_GENERATED: 'Content generated successfully!',
  SETTINGS_SAVED: 'Settings saved successfully!',
  CACHE_CLEARED: 'Cache cleared successfully!',
} as const;

// Local storage keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  REFRESH_TOKEN: 'refresh_token',
  USER_SETTINGS: 'user_settings',
  GUEST_ANALYSIS_COUNT: 'guest_analysis_count',
  THEME: 'theme',
  SIDEBAR_STATE: 'sidebar_state',
} as const;

// Query keys for React Query
export const QUERY_KEYS = {
  VIDEO_ANALYSIS: (videoId: string) => ['videoAnalysis', videoId],
  ANALYSIS_STATUS: (videoId: string) => ['analysisStatus', videoId],
  TRANSCRIPT: (videoId: string) => ['transcript', videoId],
  CHAT_SESSION: (videoId: string) => ['chatSession', videoId],
  CHAT_HISTORY: (sessionId: string) => ['chatHistory', sessionId],
  USER_STATS: () => ['userStats'],
  TOKEN_USAGE: () => ['tokenUsage'],
  AVAILABLE_MODELS: () => ['availableModels'],
  SUPPORTED_LANGUAGES: () => ['supportedLanguages'],
  CACHE_STATS: () => ['cacheStats'],
  SYSTEM_STATUS: () => ['systemStatus'],
} as const;