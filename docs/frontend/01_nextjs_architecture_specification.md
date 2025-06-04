# Next.js Frontend Architecture Specification

## Overview

This specification defines the comprehensive Next.js 14 frontend architecture that replaces the Streamlit UI while maintaining complete feature parity and integrating with the FastAPI backend.

## Technology Stack

### Core Framework
```typescript
// Pseudocode: Technology stack configuration
FRAMEWORK: Next.js 14 with App Router
LANGUAGE: TypeScript (strict mode)
STYLING: Tailwind CSS + Shadcn/ui components
STATE_MANAGEMENT: Zustand for client state
SERVER_STATE: TanStack Query (React Query) for API integration
AUTHENTICATION: Supabase Auth with JWT tokens
REAL_TIME: WebSocket for streaming chat
FORMS: React Hook Form + Zod validation
THEMES: next-themes for light/dark mode
ICONS: Lucide React
NOTIFICATIONS: Sonner toast library
```

### Project Structure
```
src/
├── app/                    # Next.js App Router
│   ├── (auth)/            # Auth route group
│   ├── (dashboard)/       # Main app route group
│   ├── api/               # API route handlers (proxy)
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Home page
├── components/            # Reusable UI components
│   ├── ui/               # Shadcn/ui base components
│   ├── layout/           # Layout components
│   ├── video/            # Video-related components
│   ├── chat/             # Chat interface components
│   ├── auth/             # Authentication components
│   └── settings/         # Settings components
├── lib/                  # Utility libraries
│   ├── api/              # API client and types
│   ├── auth/             # Authentication utilities
│   ├── stores/           # Zustand stores
│   ├── utils/            # General utilities
│   └── validations/      # Zod schemas
├── hooks/                # Custom React hooks
├── types/                # TypeScript type definitions
└── constants/            # Application constants
```

## Core Architecture Patterns

### State Management Strategy
```typescript
// Pseudocode: State management architecture
PATTERN: Separation of concerns with specialized stores

// Client State (Zustand)
STORE AuthStore:
  - user: User | null
  - isAuthenticated: boolean
  - guestAnalysisCount: number
  - login(credentials): Promise<void>
  - logout(): void
  - checkGuestLimits(): boolean

STORE UIStore:
  - theme: 'light' | 'dark'
  - sidebarOpen: boolean
  - modals: Record<string, boolean>
  - notifications: Notification[]
  - toggleSidebar(): void
  - showModal(id: string): void
  - addNotification(notification): void

STORE SettingsStore:
  - modelName: string
  - temperature: number
  - transcriptionModel: string
  - subtitleLanguage: string
  - useCache: boolean
  - updateSettings(settings): void
  - resetToDefaults(): void

// Server State (TanStack Query)
QUERIES:
  - useVideoAnalysis(videoId)
  - useChatHistory(sessionId)
  - useUserStats()
  - useTokenUsage()
  - useAvailableModels()

MUTATIONS:
  - useAnalyzeVideo()
  - useSendChatMessage()
  - useGenerateContent()
  - useTranslateSubtitles()
```

### API Integration Architecture
```typescript
// Pseudocode: API client architecture
CLASS ApiClient:
  PROPERTY baseURL: string = ENV.NEXT_PUBLIC_API_URL
  PROPERTY httpClient: AxiosInstance
  
  CONSTRUCTOR():
    this.httpClient = axios.create({
      baseURL: this.baseURL,
      timeout: ENV.NEXT_PUBLIC_API_TIMEOUT || 30000
    })
    this.setupInterceptors()
  
  METHOD setupInterceptors():
    // Request interceptor for auth
    this.httpClient.interceptors.request.use((config) => {
      token = getAuthToken()
      IF token:
        config.headers.Authorization = `Bearer ${token}`
      RETURN config
    })
    
    // Response interceptor for error handling
    this.httpClient.interceptors.response.use(
      (response) => response,
      (error) => this.handleApiError(error)
    )
  
  METHOD handleApiError(error):
    IF error.response?.status === 401:
      // Handle unauthorized - redirect to login
      authStore.logout()
      router.push('/login')
    ELSE IF error.response?.status >= 500:
      // Handle server errors
      showNotification('Server error occurred', 'error')
    
    THROW error

// API service modules
MODULE VideoAnalysisAPI:
  FUNCTION analyzeVideo(request: VideoAnalysisRequest): Promise<AnalysisResult>
  FUNCTION getAnalysisStatus(videoId: string): Promise<AnalysisStatus>
  FUNCTION generateContent(request: ContentGenerationRequest): Promise<Content>
  FUNCTION getTranscript(videoId: string): Promise<Transcript>

MODULE ChatAPI:
  FUNCTION createChatSession(videoId: string): Promise<ChatSession>
  FUNCTION sendMessage(message: ChatMessage): Promise<ChatResponse>
  FUNCTION getChatHistory(sessionId: string): Promise<ChatMessage[]>
  FUNCTION connectWebSocket(sessionId: string): WebSocket

MODULE AuthAPI:
  FUNCTION login(credentials: LoginRequest): Promise<AuthResponse>
  FUNCTION signup(userData: SignupRequest): Promise<AuthResponse>
  FUNCTION refreshToken(token: string): Promise<AuthResponse>
  FUNCTION logout(): Promise<void>
```

### Component Architecture
```typescript
// Pseudocode: Component hierarchy and patterns
COMPONENT AppLayout:
  CHILDREN:
    - Header (logo, auth status, theme toggle)
    - Sidebar (navigation, settings, user info)
    - MainContent (dynamic based on route)
    - NotificationContainer (global notifications)
  
  RESPONSIBILITIES:
    - Global layout structure
    - Theme provider context
    - Authentication state management
    - Global error boundary

COMPONENT VideoAnalysisPage:
  CHILDREN:
    - VideoInput (URL input and validation)
    - VideoPlayer (YouTube embed with custom subtitles)
    - AnalysisResults (tabbed interface)
    - ChatInterface (real-time chat)
    - TokenUsageDisplay (cost tracking)
  
  STATE:
    - currentVideoId: string | null
    - analysisStatus: 'idle' | 'analyzing' | 'complete' | 'error'
    - selectedTab: string
  
  RESPONSIBILITIES:
    - Coordinate video analysis workflow
    - Manage analysis state
    - Handle user interactions

COMPONENT ChatInterface:
  CHILDREN:
    - MessageList (chat history display)
    - MessageInput (user input with streaming)
    - TypingIndicator (AI response indicator)
  
  STATE:
    - messages: ChatMessage[]
    - isStreaming: boolean
    - currentInput: string
  
  RESPONSIBILITIES:
    - Real-time chat functionality
    - WebSocket connection management
    - Message streaming display
```

## Environment Configuration
```typescript
// Pseudocode: Environment variables (no hardcoded values)
ENVIRONMENT_VARIABLES:
  // API Configuration
  NEXT_PUBLIC_API_URL: string = ENV.NEXT_PUBLIC_API_URL
  NEXT_PUBLIC_WS_URL: string = ENV.NEXT_PUBLIC_WS_URL
  NEXT_PUBLIC_API_TIMEOUT: number = ENV.NEXT_PUBLIC_API_TIMEOUT || 30000
  
  // Supabase Configuration
  NEXT_PUBLIC_SUPABASE_URL: string = ENV.NEXT_PUBLIC_SUPABASE_URL
  NEXT_PUBLIC_SUPABASE_ANON_KEY: string = ENV.NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  // Application Configuration
  NEXT_PUBLIC_APP_NAME: string = ENV.NEXT_PUBLIC_APP_NAME || "YouTube Analysis"
  NEXT_PUBLIC_MAX_GUEST_ANALYSES: number = ENV.NEXT_PUBLIC_MAX_GUEST_ANALYSES || 3
  NEXT_PUBLIC_ENABLE_ANALYTICS: boolean = ENV.NEXT_PUBLIC_ENABLE_ANALYTICS === 'true'
  
  // Feature Flags
  NEXT_PUBLIC_ENABLE_CHAT: boolean = ENV.NEXT_PUBLIC_ENABLE_CHAT !== 'false'
  NEXT_PUBLIC_ENABLE_SUBTITLES: boolean = ENV.NEXT_PUBLIC_ENABLE_SUBTITLES !== 'false'
  NEXT_PUBLIC_ENABLE_HIGHLIGHTS: boolean = ENV.NEXT_PUBLIC_ENABLE_HIGHLIGHTS === 'true'
```

## Performance Optimization Strategy
```typescript
// Pseudocode: Performance optimization patterns
OPTIMIZATION_PATTERNS:
  
  // Code Splitting
  DYNAMIC_IMPORTS:
    - ChatInterface: lazy(() => import('./ChatInterface'))
    - VideoPlayer: lazy(() => import('./VideoPlayer'))
    - AnalysisResults: lazy(() => import('./AnalysisResults'))
  
  // Caching Strategy
  REACT_QUERY_CONFIG:
    defaultOptions:
      queries:
        staleTime: 5 * 60 * 1000  // 5 minutes
        cacheTime: 10 * 60 * 1000 // 10 minutes
        retry: 3
        refetchOnWindowFocus: false
  
  // Image Optimization
  NEXT_IMAGE_CONFIG:
    domains: ['img.youtube.com', 'i.ytimg.com']
    formats: ['image/webp', 'image/avif']
    sizes: '(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw'
  
  // Bundle Optimization
  WEBPACK_CONFIG:
    splitChunks:
      chunks: 'all'
      cacheGroups:
        vendor:
          test: /[\\/]node_modules[\\/]/
          name: 'vendors'
          chunks: 'all'
```

## Error Handling Strategy
```typescript
// Pseudocode: Comprehensive error handling
ERROR_BOUNDARY_HIERARCHY:
  
  COMPONENT GlobalErrorBoundary:
    CATCHES: All unhandled React errors
    FALLBACK: Generic error page with retry option
    LOGGING: Send error reports to monitoring service
  
  COMPONENT ApiErrorBoundary:
    CATCHES: API-related errors
    FALLBACK: API error message with retry button
    RECOVERY: Automatic retry with exponential backoff
  
  COMPONENT ChatErrorBoundary:
    CATCHES: Chat/WebSocket errors
    FALLBACK: Chat unavailable message
    RECOVERY: Attempt to reconnect WebSocket

ERROR_HANDLING_PATTERNS:
  
  FUNCTION handleApiError(error: ApiError):
    SWITCH error.type:
      CASE 'NETWORK_ERROR':
        showNotification('Network connection lost', 'error')
        RETURN { retry: true, delay: 5000 }
      
      CASE 'VALIDATION_ERROR':
        showFieldErrors(error.fieldErrors)
        RETURN { retry: false }
      
      CASE 'RATE_LIMIT':
        showNotification('Rate limit exceeded', 'warning')
        RETURN { retry: true, delay: error.retryAfter * 1000 }
      
      CASE 'SERVER_ERROR':
        showNotification('Server error occurred', 'error')
        RETURN { retry: true, delay: 10000 }
```

## Testing Strategy
```typescript
// Pseudocode: Testing architecture
TESTING_LAYERS:
  
  // Unit Tests (Jest + Testing Library)
  UNIT_TESTS:
    - Component rendering and interactions
    - Custom hooks behavior
    - Utility functions
    - Store actions and state updates
  
  // Integration Tests
  INTEGRATION_TESTS:
    - API client integration
    - Authentication flow
    - Video analysis workflow
    - Chat functionality
  
  // E2E Tests (Playwright)
  E2E_TESTS:
    - Complete user journeys
    - Cross-browser compatibility
    - Performance benchmarks
    - Accessibility compliance

TEST_UTILITIES:
  
  FUNCTION renderWithProviders(component, options):
    // Wrap component with all necessary providers
    RETURN render(component, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={testQueryClient}>
          <ThemeProvider>
            <AuthProvider>
              {children}
            </AuthProvider>
          </ThemeProvider>
        </QueryClientProvider>
      ),
      ...options
    })
  
  FUNCTION createMockApiClient():
    // Create mock API client for testing
    RETURN {
      analyzeVideo: jest.fn(),
      sendChatMessage: jest.fn(),
      // ... other API methods
    }
```

This architecture specification provides the foundation for a scalable, maintainable Next.js frontend that maintains feature parity with the existing Streamlit application while leveraging modern React patterns and best practices.