# API Integration Specification

## Overview

This specification defines the comprehensive API integration layer for the Next.js frontend, providing type-safe communication with the FastAPI backend while handling authentication, error management, and real-time features.

## API Client Architecture

### Core API Client
```typescript
// Pseudocode: Main API client configuration
CLASS ApiClient:
  PROPERTY baseURL: string
  PROPERTY httpClient: AxiosInstance
  PROPERTY wsClient: WebSocketManager
  
  CONSTRUCTOR(config: ApiConfig):
    this.baseURL = config.baseURL || ENV.NEXT_PUBLIC_API_URL
    this.httpClient = this.createHttpClient()
    this.wsClient = new WebSocketManager(config.wsURL || ENV.NEXT_PUBLIC_WS_URL)
    this.setupInterceptors()
  
  METHOD createHttpClient(): AxiosInstance:
    RETURN axios.create({
      baseURL: this.baseURL,
      timeout: ENV.NEXT_PUBLIC_API_TIMEOUT || 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
  
  METHOD setupInterceptors():
    // Request interceptor for authentication
    this.httpClient.interceptors.request.use(
      (config) => {
        token = getStoredToken()
        IF token:
          config.headers.Authorization = `Bearer ${token}`
        
        // Add request ID for tracking
        config.headers['X-Request-ID'] = generateRequestId()
        
        RETURN config
      },
      (error) => Promise.reject(error)
    )
    
    // Response interceptor for error handling
    this.httpClient.interceptors.response.use(
      (response) => {
        // Log successful requests in development
        IF ENV.NODE_ENV === 'development':
          console.log(`API Success: ${response.config.method?.toUpperCase()} ${response.config.url}`)
        
        RETURN response
      },
      (error) => this.handleApiError(error)
    )
  
  METHOD handleApiError(error: AxiosError): Promise<never>:
    requestId = error.config?.headers?.['X-Request-ID']
    
    // Log error with context
    console.error('API Error:', {
      requestId,
      method: error.config?.method,
      url: error.config?.url,
      status: error.response?.status,
      message: error.message
    })
    
    // Handle specific error types
    SWITCH error.response?.status:
      CASE 401:
        this.handleUnauthorized()
        BREAK
      CASE 403:
        this.handleForbidden()
        BREAK
      CASE 429:
        this.handleRateLimit(error.response)
        BREAK
      CASE 500:
      CASE 502:
      CASE 503:
      CASE 504:
        this.handleServerError(error.response)
        BREAK
    
    // Transform error for consistent handling
    apiError = new ApiError({
      message: error.response?.data?.message || error.message,
      status: error.response?.status,
      code: error.response?.data?.code,
      requestId,
      originalError: error
    })
    
    THROW apiError
  
  METHOD handleUnauthorized():
    // Clear stored tokens
    removeStoredToken()
    
    // Reset auth store
    useAuthStore.getState().reset()
    
    // Redirect to login if not already there
    IF NOT window.location.pathname.includes('/login'):
      window.location.href = '/login'
  
  METHOD handleRateLimit(response: AxiosResponse):
    retryAfter = response.headers['retry-after']
    
    useUIStore.getState().addNotification({
      title: 'Rate Limit Exceeded',
      description: `Please wait ${retryAfter} seconds before trying again`,
      type: 'warning',
      duration: parseInt(retryAfter) * 1000
    })
  
  METHOD handleServerError(response: AxiosResponse):
    useUIStore.getState().addNotification({
      title: 'Server Error',
      description: 'Our servers are experiencing issues. Please try again later.',
      type: 'error',
      duration: 10000
    })

// Global API client instance
apiClient = new ApiClient({
  baseURL: ENV.NEXT_PUBLIC_API_URL,
  wsURL: ENV.NEXT_PUBLIC_WS_URL
})
```

### Video Analysis API
```typescript
// Pseudocode: Video analysis API methods
MODULE VideoAnalysisAPI:
  
  FUNCTION analyzeVideo(request: VideoAnalysisRequest): Promise<AnalysisResult>:
    TRY:
      response = await apiClient.httpClient.post('/api/v1/video/analyze', request)
      RETURN response.data
    CATCH error:
      // Add context-specific error handling
      IF error.status === 400 AND error.code === 'INVALID_URL':
        THROW new ValidationError('Please provide a valid YouTube URL')
      THROW error
  
  FUNCTION getAnalysisStatus(videoId: string): Promise<AnalysisStatus>:
    response = await apiClient.httpClient.get(`/api/v1/video/${videoId}/status`)
    RETURN response.data
  
  FUNCTION generateContent(request: ContentGenerationRequest): Promise<GeneratedContent>:
    response = await apiClient.httpClient.post('/api/v1/video/generate-content', request)
    RETURN response.data
  
  FUNCTION getTranscript(videoId: string, options?: TranscriptOptions): Promise<Transcript>:
    params = new URLSearchParams()
    IF options?.includeTimestamps:
      params.append('include_timestamps', 'true')
    IF options?.language:
      params.append('language', options.language)
    
    response = await apiClient.httpClient.get(
      `/api/v1/video/${videoId}/transcript?${params.toString()}`
    )
    RETURN response.data
  
  FUNCTION translateSubtitles(request: SubtitleTranslationRequest): Promise<SubtitleData>:
    response = await apiClient.httpClient.post('/api/v1/video/subtitles/translate', request)
    RETURN response.data
  
  FUNCTION downloadSubtitles(videoId: string, language: string, format: string): Promise<Blob>:
    response = await apiClient.httpClient.get(
      `/api/v1/video/${videoId}/subtitles/download`,
      {
        params: { language, format },
        responseType: 'blob'
      }
    )
    RETURN response.data

// Streaming analysis with Server-Sent Events
FUNCTION streamAnalysis(videoId: string, onProgress: (progress: AnalysisProgress) => void): EventSource:
  eventSource = new EventSource(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/video/${videoId}/stream`)
  
  eventSource.onmessage = (event) => {
    TRY:
      data = JSON.parse(event.data)
      onProgress(data)
    CATCH error:
      console.error('Failed to parse SSE data:', error)
  }
  
  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error)
    eventSource.close()
  }
  
  RETURN eventSource
```

### Chat API
```typescript
// Pseudocode: Chat API methods
MODULE ChatAPI:
  
  FUNCTION createChatSession(videoId: string): Promise<ChatSession>:
    response = await apiClient.httpClient.post('/api/v1/video/chat/session', {
      video_id: videoId
    })
    RETURN response.data
  
  FUNCTION getChatHistory(sessionId: string, options?: ChatHistoryOptions): Promise<ChatMessage[]>:
    params = {
      limit: options?.limit || 50,
      offset: options?.offset || 0
    }
    
    response = await apiClient.httpClient.get(
      `/api/v1/video/chat/${sessionId}/history`,
      { params }
    )
    RETURN response.data
  
  FUNCTION sendMessage(message: ChatMessageRequest): Promise<ChatMessageResponse>:
    response = await apiClient.httpClient.post('/api/v1/video/chat/message', message)
    RETURN response.data
  
  FUNCTION deleteChatSession(sessionId: string): Promise<void>:
    await apiClient.httpClient.delete(`/api/v1/video/chat/${sessionId}`)

// WebSocket Chat Integration
CLASS ChatWebSocketClient:
  PROPERTY ws: WebSocket | null = null
  PROPERTY sessionId: string
  PROPERTY callbacks: ChatCallbacks
  PROPERTY reconnectAttempts: number = 0
  PROPERTY maxReconnectAttempts: number = 5
  
  CONSTRUCTOR(sessionId: string, callbacks: ChatCallbacks):
    this.sessionId = sessionId
    this.callbacks = callbacks
  
  METHOD connect():
    TRY:
      wsUrl = `${ENV.NEXT_PUBLIC_WS_URL}/api/v1/video/chat/${this.sessionId}/ws`
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.callbacks.onConnect?.()
      }
      
      this.ws.onmessage = (event) => {
        TRY:
          data = JSON.parse(event.data)
          this.handleMessage(data)
        CATCH error:
          console.error('Failed to parse WebSocket message:', error)
      }
      
      this.ws.onclose = (event) => {
        this.callbacks.onDisconnect?.(event.code, event.reason)
        this.attemptReconnect()
      }
      
      this.ws.onerror = (error) => {
        this.callbacks.onError?.(error)
      }
    CATCH error:
      this.callbacks.onError?.(error)
  
  METHOD handleMessage(data: WebSocketMessage):
    SWITCH data.type:
      CASE 'message_start':
        this.callbacks.onMessageStart?.(data.messageId)
        BREAK
      CASE 'message_chunk':
        this.callbacks.onMessageChunk?.(data.messageId, data.chunk)
        BREAK
      CASE 'message_complete':
        this.callbacks.onMessageComplete?.(data.messageId, data.tokenUsage)
        BREAK
      CASE 'error':
        this.callbacks.onError?.(new Error(data.error))
        BREAK
  
  METHOD sendMessage(content: string, options?: ChatMessageOptions):
    IF this.ws?.readyState === WebSocket.OPEN:
      message = {
        type: 'chat_message',
        content,
        session_id: this.sessionId,
        model_name: options?.modelName,
        temperature: options?.temperature,
        use_context: options?.useContext ?? true
      }
      
      this.ws.send(JSON.stringify(message))
    ELSE:
      THROW new Error('WebSocket not connected')
  
  METHOD attemptReconnect():
    IF this.reconnectAttempts < this.maxReconnectAttempts:
      delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
      
      setTimeout(() => {
        this.reconnectAttempts++
        this.connect()
      }, delay)
    ELSE:
      this.callbacks.onMaxReconnectAttemptsReached?.()
  
  METHOD disconnect():
    IF this.ws:
      this.ws.close()
      this.ws = null
```

### Authentication API
```typescript
// Pseudocode: Authentication API methods
MODULE AuthAPI:
  
  FUNCTION exchangeSupabaseToken(supabaseToken: string): Promise<ApiTokenResponse>:
    response = await apiClient.httpClient.post('/api/v1/auth/exchange-token', {
      supabase_token: supabaseToken
    })
    
    // Store the API token
    setStoredToken(response.data.access_token)
    
    RETURN response.data
  
  FUNCTION refreshApiToken(refreshToken: string): Promise<ApiTokenResponse>:
    response = await apiClient.httpClient.post('/api/v1/auth/refresh', {
      refresh_token: refreshToken
    })
    
    setStoredToken(response.data.access_token)
    
    RETURN response.data
  
  FUNCTION validateToken(): Promise<TokenValidationResponse>:
    response = await apiClient.httpClient.get('/api/v1/auth/validate')
    RETURN response.data
  
  FUNCTION getUserProfile(): Promise<UserProfile>:
    response = await apiClient.httpClient.get('/api/v1/auth/profile')
    RETURN response.data
  
  FUNCTION updateUserProfile(profile: UpdateProfileRequest): Promise<UserProfile>:
    response = await apiClient.httpClient.put('/api/v1/auth/profile', profile)
    RETURN response.data

// Token management utilities
FUNCTION getStoredToken(): string | null:
  RETURN localStorage.getItem('api_token')

FUNCTION setStoredToken(token: string):
  localStorage.setItem('api_token', token)

FUNCTION removeStoredToken():
  localStorage.removeItem('api_token')

FUNCTION isTokenExpired(token: string): boolean:
  TRY:
    payload = JSON.parse(atob(token.split('.')[1]))
    RETURN payload.exp * 1000 < Date.now()
  CATCH:
    RETURN true
```

### Configuration API
```typescript
// Pseudocode: Configuration and system API methods
MODULE ConfigAPI:
  
  FUNCTION getAvailableModels(): Promise<ModelInfo[]>:
    response = await apiClient.httpClient.get('/api/v1/config/models')
    RETURN response.data
  
  FUNCTION getSupportedLanguages(): Promise<LanguageInfo[]>:
    response = await apiClient.httpClient.get('/api/v1/config/languages')
    RETURN response.data
  
  FUNCTION getSystemStatus(): Promise<SystemStatus>:
    response = await apiClient.httpClient.get('/api/v1/config/status')
    RETURN response.data
  
  FUNCTION getCacheStats(): Promise<CacheStats>:
    response = await apiClient.httpClient.get('/api/v1/cache/stats')
    RETURN response.data
  
  FUNCTION clearCache(request: CacheClearRequest): Promise<CacheClearResponse>:
    response = await apiClient.httpClient.post('/api/v1/cache/clear', request)
    RETURN response.data

MODULE UserStatsAPI:
  
  FUNCTION getUserStats(): Promise<UserStats>:
    response = await apiClient.httpClient.get('/api/v1/auth/stats')
    RETURN response.data
  
  FUNCTION getTokenUsage(period?: string): Promise<TokenUsage>:
    params = period ? { period } : {}
    response = await apiClient.httpClient.get('/api/v1/auth/token-usage', { params })
    RETURN response.data
```

## Error Handling

### Custom Error Classes
```typescript
// Pseudocode: Custom error types for API integration
CLASS ApiError EXTENDS Error:
  PROPERTY status?: number
  PROPERTY code?: string
  PROPERTY requestId?: string
  PROPERTY originalError?: Error
  
  CONSTRUCTOR(options: ApiErrorOptions):
    super(options.message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code
    this.requestId = options.requestId
    this.originalError = options.originalError

CLASS ValidationError EXTENDS ApiError:
  PROPERTY fieldErrors?: Record<string, string[]>
  
  CONSTRUCTOR(message: string, fieldErrors?: Record<string, string[]>):
    super({ message, status: 400, code: 'VALIDATION_ERROR' })
    this.name = 'ValidationError'
    this.fieldErrors = fieldErrors

CLASS NetworkError EXTENDS ApiError:
  CONSTRUCTOR(message: string = 'Network connection failed'):
    super({ message, code: 'NETWORK_ERROR' })
    this.name = 'NetworkError'

CLASS RateLimitError EXTENDS ApiError:
  PROPERTY retryAfter?: number
  
  CONSTRUCTOR(retryAfter?: number):
    super({ 
      message: 'Rate limit exceeded', 
      status: 429, 
      code: 'RATE_LIMIT_EXCEEDED' 
    })
    this.name = 'RateLimitError'
    this.retryAfter = retryAfter

// Error boundary for API errors
COMPONENT ApiErrorBoundary:
  PROPS:
    children: ReactNode
    fallback?: ComponentType<{ error: Error; retry: () => void }>
  
  STATE:
    hasError: boolean = false
    error: Error | null = null
  
  STATIC getDerivedStateFromError(error: Error):
    RETURN { hasError: true, error }
  
  METHOD componentDidCatch(error: Error, errorInfo: ErrorInfo):
    // Log error to monitoring service
    console.error('API Error Boundary caught error:', error, errorInfo)
    
    // Report to error tracking service
    IF ENV.NODE_ENV === 'production':
      reportError(error, errorInfo)
  
  METHOD handleRetry():
    this.setState({ hasError: false, error: null })
  
  RENDER:
    IF this.state.hasError:
      FallbackComponent = this.props.fallback || DefaultApiErrorFallback
      RETURN <FallbackComponent error={this.state.error} retry={this.handleRetry} />
    
    RETURN this.props.children
```

## Request/Response Types

### TypeScript Interfaces
```typescript
// Pseudocode: API request/response type definitions
INTERFACE VideoAnalysisRequest:
  youtube_url: string
  analysis_types: string[]
  model_name?: string
  temperature?: number
  use_cache?: boolean
  custom_instruction?: string

INTERFACE AnalysisResult:
  video_id: string
  task_outputs: Record<string, string>
  transcript: string
  transcript_segments: TranscriptSegment[]
  token_usage: TokenUsage
  analysis_metadata: AnalysisMetadata

INTERFACE ChatMessageRequest:
  message: string
  video_id: string
  session_id?: string
  model_name?: string
  temperature?: number
  use_context?: boolean

INTERFACE ChatMessageResponse:
  message_id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: string
  token_usage?: TokenUsage

INTERFACE WebSocketMessage:
  type: 'message_start' | 'message_chunk' | 'message_complete' | 'error'
  messageId?: string
  chunk?: string
  tokenUsage?: TokenUsage
  error?: string

INTERFACE ApiConfig:
  baseURL: string
  wsURL: string
  timeout?: number
  retryAttempts?: number
  retryDelay?: number
```

This API integration specification provides a comprehensive, type-safe, and robust communication layer between the Next.js frontend and FastAPI backend, with proper error handling, authentication, and real-time capabilities.