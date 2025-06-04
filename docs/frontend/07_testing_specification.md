# Testing Specification

## Overview

This specification defines comprehensive testing strategies for the Next.js frontend, covering unit tests, integration tests, and end-to-end tests with TDD anchors and testing utilities for reliable, maintainable code.

## Testing Architecture

### Testing Stack Configuration
```typescript
// Pseudocode: Testing framework setup
TESTING_STACK:
  UNIT_TESTING:
    framework: Jest
    testing_library: @testing-library/react
    mocking: MSW (Mock Service Worker)
    coverage: Jest built-in coverage
  
  INTEGRATION_TESTING:
    framework: Jest + Testing Library
    api_mocking: MSW
    component_testing: React Testing Library
  
  E2E_TESTING:
    framework: Playwright
    browsers: Chromium, Firefox, Safari
    visual_testing: Playwright screenshots
  
  PERFORMANCE_TESTING:
    lighthouse: Lighthouse CI
    bundle_analysis: @next/bundle-analyzer

// Jest configuration
JEST_CONFIG:
  testEnvironment: 'jsdom'
  setupFilesAfterEnv: ['<rootDir>/src/test/setup.ts']
  moduleNameMapping:
    '^@/(.*)$': '<rootDir>/src/$1'
    '^@/test/(.*)$': '<rootDir>/src/test/$1'
  collectCoverageFrom:
    - 'src/**/*.{ts,tsx}'
    - '!src/**/*.d.ts'
    - '!src/test/**/*'
  coverageThreshold:
    global:
      branches: 80
      functions: 80
      lines: 80
      statements: 80
```

### Test Utilities and Setup
```typescript
// Pseudocode: Testing utilities and providers
FUNCTION renderWithProviders(
  component: ReactElement,
  options?: RenderOptions & {
    initialAuthState?: Partial<AuthState>
    initialUIState?: Partial<UIState>
    queryClient?: QueryClient
  }
):
  // Create test query client
  testQueryClient = options?.queryClient || createTestQueryClient()
  
  // Create test stores with initial state
  testAuthStore = createTestAuthStore(options?.initialAuthState)
  testUIStore = createTestUIStore(options?.initialUIState)
  
  // Wrapper component with all providers
  AllTheProviders = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={testQueryClient}>
      <ThemeProvider attribute="class" defaultTheme="light">
        <AuthProvider testStore={testAuthStore}>
          <NotificationProvider testStore={testUIStore}>
            {children}
          </NotificationProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
  
  RETURN render(component, { wrapper: AllTheProviders, ...options })

FUNCTION createTestQueryClient(): QueryClient:
  RETURN new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
        staleTime: 0
      },
      mutations: {
        retry: false
      }
    },
    logger: {
      log: console.log,
      warn: console.warn,
      error: () => {} // Suppress error logs in tests
    }
  })

FUNCTION createTestAuthStore(initialState?: Partial<AuthState>):
  RETURN create<AuthState & AuthActions>(() => ({
    user: null,
    session: null,
    isAuthenticated: false,
    guestAnalysisCount: 0,
    isLoading: false,
    ...initialState,
    // Mock actions
    setUser: jest.fn(),
    setSession: jest.fn(),
    setGuestAnalysisCount: jest.fn(),
    incrementGuestCount: jest.fn(),
    checkGuestLimits: jest.fn(() => true),
    reset: jest.fn()
  }))

// Mock API responses with MSW
MOCK_HANDLERS = [
  rest.post(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/video/analyze`, (req, res, ctx) => {
    RETURN res(
      ctx.status(200),
      ctx.json({
        video_id: 'test-video-id',
        task_outputs: {
          classify_and_summarize_content: 'Test summary content'
        },
        transcript: 'Test transcript',
        transcript_segments: [],
        token_usage: { total_tokens: 100, prompt_tokens: 50, completion_tokens: 50 }
      })
    )
  }),
  
  rest.post(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/video/chat/session`, (req, res, ctx) => {
    RETURN res(
      ctx.status(200),
      ctx.json({
        session_id: 'test-session-id',
        video_id: 'test-video-id',
        created_at: new Date().toISOString()
      })
    )
  }),
  
  rest.get(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/auth/stats`, (req, res, ctx) => {
    RETURN res(
      ctx.status(200),
      ctx.json({
        summary_count: 5,
        total_tokens_used: 1000
      })
    )
  })
]

// Test server setup
testServer = setupServer(...MOCK_HANDLERS)

// Setup and teardown
beforeAll(() => testServer.listen())
afterEach(() => testServer.resetHandlers())
afterAll(() => testServer.close())
```

## Unit Tests

### Component Unit Tests
```typescript
// Pseudocode: Component unit test examples
DESCRIBE 'VideoInput Component':
  
  TEST 'renders input form correctly':
    render(<VideoInput onAnalyze={jest.fn()} isAnalyzing={false} />)
    
    EXPECT(screen.getByLabelText('YouTube URL')).toBeInTheDocument()
    EXPECT(screen.getByText('Analyze Video')).toBeInTheDocument()
    EXPECT(screen.getByText('Analysis Types')).toBeInTheDocument()
  
  TEST 'validates YouTube URL format':
    mockOnAnalyze = jest.fn()
    render(<VideoInput onAnalyze={mockOnAnalyze} isAnalyzing={false} />)
    
    urlInput = screen.getByLabelText('YouTube URL')
    submitButton = screen.getByText('Analyze Video')
    
    // Test invalid URL
    fireEvent.change(urlInput, { target: { value: 'invalid-url' } })
    fireEvent.click(submitButton)
    
    EXPECT(screen.getByText('Please enter a valid YouTube URL')).toBeInTheDocument()
    EXPECT(mockOnAnalyze).not.toHaveBeenCalled()
  
  TEST 'submits valid form data':
    mockOnAnalyze = jest.fn()
    render(<VideoInput onAnalyze={mockOnAnalyze} isAnalyzing={false} />)
    
    urlInput = screen.getByLabelText('YouTube URL')
    submitButton = screen.getByText('Analyze Video')
    
    // Enter valid YouTube URL
    fireEvent.change(urlInput, { 
      target: { value: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' } 
    })
    fireEvent.click(submitButton)
    
    EXPECT(mockOnAnalyze).toHaveBeenCalledWith(
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      expect.objectContaining({
        analysisTypes: ['Summary & Classification'],
        useCache: true
      })
    )
  
  TEST 'disables form when analyzing':
    render(<VideoInput onAnalyze={jest.fn()} isAnalyzing={true} />)
    
    submitButton = screen.getByText('Analyzing...')
    EXPECT(submitButton).toBeDisabled()
    EXPECT(screen.getByRole('progressbar')).toBeInTheDocument()

DESCRIBE 'ChatInterface Component':
  
  TEST 'renders empty state when no messages':
    renderWithProviders(
      <ChatInterface 
        videoId="test-video" 
        analysisResults={{}} 
        onMessageSent={jest.fn()} 
        onChatReset={jest.fn()} 
      />
    )
    
    EXPECT(screen.getByText('Start a conversation')).toBeInTheDocument()
    EXPECT(screen.getByText('Ask questions about the video content')).toBeInTheDocument()
  
  TEST 'sends message when form submitted':
    mockOnMessageSent = jest.fn()
    
    renderWithProviders(
      <ChatInterface 
        videoId="test-video" 
        analysisResults={{}} 
        onMessageSent={mockOnMessageSent} 
        onChatReset={jest.fn()} 
      />
    )
    
    messageInput = screen.getByPlaceholderText('Type your message...')
    sendButton = screen.getByRole('button', { name: /send/i })
    
    fireEvent.change(messageInput, { target: { value: 'Test message' } })
    fireEvent.click(sendButton)
    
    EXPECT(mockOnMessageSent).toHaveBeenCalledWith('Test message')
    EXPECT(messageInput).toHaveValue('')
  
  TEST 'handles WebSocket connection states':
    renderWithProviders(
      <ChatInterface 
        videoId="test-video" 
        analysisResults={{}} 
        onMessageSent={jest.fn()} 
        onChatReset={jest.fn()} 
      />
    )
    
    // Should show connection status
    EXPECT(screen.getByText('Connected')).toBeInTheDocument()
    
    // Simulate disconnection
    act(() => {
      // Trigger WebSocket disconnect event
      mockWebSocket.triggerDisconnect()
    })
    
    EXPECT(screen.getByText('Disconnected')).toBeInTheDocument()
```

### Hook Unit Tests
```typescript
// Pseudocode: Custom hook unit tests
DESCRIBE 'useVideoAnalysis Hook':
  
  TEST 'fetches video analysis data':
    wrapper = ({ children }) => (
      <QueryClientProvider client={createTestQueryClient()}>
        {children}
      </QueryClientProvider>
    )
    
    { result } = renderHook(() => useVideoAnalysis('test-video-id'), { wrapper })
    
    // Wait for query to complete
    await waitFor(() => {
      EXPECT(result.current.isSuccess).toBe(true)
    })
    
    EXPECT(result.current.data).toEqual(
      expect.objectContaining({
        video_id: 'test-video-id',
        task_outputs: expect.any(Object)
      })
    )
  
  TEST 'handles analysis error':
    // Mock API error
    testServer.use(
      rest.get(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/video/test-video-id`, (req, res, ctx) => {
        RETURN res(ctx.status(404), ctx.json({ message: 'Video not found' }))
      })
    )
    
    wrapper = ({ children }) => (
      <QueryClientProvider client={createTestQueryClient()}>
        {children}
      </QueryClientProvider>
    )
    
    { result } = renderHook(() => useVideoAnalysis('test-video-id'), { wrapper })
    
    await waitFor(() => {
      EXPECT(result.current.isError).toBe(true)
    })
    
    EXPECT(result.current.error.message).toBe('Video not found')

DESCRIBE 'useAuth Hook':
  
  TEST 'provides authentication state':
    { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider testStore={createTestAuthStore({ isAuthenticated: true })}>
          {children}
        </AuthProvider>
      )
    })
    
    EXPECT(result.current.isAuthenticated).toBe(true)
    EXPECT(typeof result.current.login).toBe('function')
    EXPECT(typeof result.current.logout).toBe('function')
  
  TEST 'throws error when used outside provider':
    EXPECT(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within AuthProvider')
```

### Store Unit Tests
```typescript
// Pseudocode: Zustand store unit tests
DESCRIBE 'AuthStore':
  
  TEST 'initializes with default state':
    store = useAuthStore.getState()
    
    EXPECT(store.user).toBeNull()
    EXPECT(store.isAuthenticated).toBe(false)
    EXPECT(store.guestAnalysisCount).toBe(0)
  
  TEST 'updates user state correctly':
    mockUser = { id: '1', email: 'test@example.com' }
    
    act(() => {
      useAuthStore.getState().setUser(mockUser)
    })
    
    state = useAuthStore.getState()
    EXPECT(state.user).toEqual(mockUser)
    EXPECT(state.isAuthenticated).toBe(true)
  
  TEST 'increments guest count and persists to localStorage':
    // Clear localStorage
    localStorage.clear()
    
    act(() => {
      useAuthStore.getState().incrementGuestCount()
    })
    
    EXPECT(useAuthStore.getState().guestAnalysisCount).toBe(1)
    EXPECT(localStorage.getItem('guestAnalysisCount')).toBe('1')
  
  TEST 'checks guest limits correctly':
    // Set guest count to maximum
    act(() => {
      useAuthStore.getState().setGuestAnalysisCount(3)
    })
    
    EXPECT(useAuthStore.getState().checkGuestLimits()).toBe(false)
    
    // Set below maximum
    act(() => {
      useAuthStore.getState().setGuestAnalysisCount(2)
    })
    
    EXPECT(useAuthStore.getState().checkGuestLimits()).toBe(true)

DESCRIBE 'SettingsStore':
  
  TEST 'loads settings from localStorage on initialization':
    // Set up localStorage with test settings
    testSettings = {
      modelName: 'gpt-4',
      temperature: 0.5,
      useCache: false
    }
    localStorage.setItem('appSettings', JSON.stringify(testSettings))
    
    // Reinitialize store
    useSettingsStore.getState().loadFromStorage()
    
    state = useSettingsStore.getState()
    EXPECT(state.modelName).toBe('gpt-4')
    EXPECT(state.temperature).toBe(0.5)
    EXPECT(state.useCache).toBe(false)
  
  TEST 'saves settings to localStorage when updated':
    act(() => {
      useSettingsStore.getState().updateSettings({
        modelName: 'gpt-3.5-turbo',
        temperature: 0.8
      })
    })
    
    savedSettings = JSON.parse(localStorage.getItem('appSettings'))
    EXPECT(savedSettings.modelName).toBe('gpt-3.5-turbo')
    EXPECT(savedSettings.temperature).toBe(0.8)
```

## Integration Tests

### API Integration Tests
```typescript
// Pseudocode: API integration test examples
DESCRIBE 'Video Analysis Integration':
  
  TEST 'complete video analysis workflow':
    renderWithProviders(<VideoAnalysisPage />)
    
    // Enter YouTube URL
    urlInput = screen.getByLabelText('YouTube URL')
    fireEvent.change(urlInput, { 
      target: { value: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' } 
    })
    
    // Start analysis
    analyzeButton = screen.getByText('Analyze Video')
    fireEvent.click(analyzeButton)
    
    // Should show loading state
    EXPECT(screen.getByText('Analyzing...')).toBeInTheDocument()
    
    // Wait for analysis to complete
    await waitFor(() => {
      EXPECT(screen.getByText('Analysis Results')).toBeInTheDocument()
    })
    
    // Should display results tabs
    EXPECT(screen.getByText('📊 Summary')).toBeInTheDocument()
    EXPECT(screen.getByText('📋 Action Plan')).toBeInTheDocument()
    
    // Should show analysis content
    EXPECT(screen.getByText('Test summary content')).toBeInTheDocument()
  
  TEST 'handles analysis error gracefully':
    // Mock API error
    testServer.use(
      rest.post(`${ENV.NEXT_PUBLIC_API_URL}/api/v1/video/analyze`, (req, res, ctx) => {
        RETURN res(ctx.status(400), ctx.json({ message: 'Invalid video URL' }))
      })
    )
    
    renderWithProviders(<VideoAnalysisPage />)
    
    urlInput = screen.getByLabelText('YouTube URL')
    fireEvent.change(urlInput, { 
      target: { value: 'https://www.youtube.com/watch?v=invalid' } 
    })
    
    analyzeButton = screen.getByText('Analyze Video')
    fireEvent.click(analyzeButton)
    
    // Should show error message
    await waitFor(() => {
      EXPECT(screen.getByText('Invalid video URL')).toBeInTheDocument()
    })

DESCRIBE 'Authentication Integration':
  
  TEST 'login flow updates global state':
    renderWithProviders(<AuthModal isOpen={true} onClose={jest.fn()} />)
    
    // Fill login form
    emailInput = screen.getByLabelText('Email')
    passwordInput = screen.getByLabelText('Password')
    
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } })
    fireEvent.change(passwordInput, { target: { value: 'password123' } })
    
    // Submit form
    loginButton = screen.getByText('Sign In')
    fireEvent.click(loginButton)
    
    // Should update auth store
    await waitFor(() => {
      authState = useAuthStore.getState()
      EXPECT(authState.isAuthenticated).toBe(true)
      EXPECT(authState.user?.email).toBe('test@example.com')
    })
```

## End-to-End Tests

### Playwright E2E Tests
```typescript
// Pseudocode: End-to-end test examples
DESCRIBE 'Video Analysis E2E Flow':
  
  TEST 'user can analyze video and view results':
    // Navigate to application
    await page.goto('http://localhost:3000')
    
    // Enter YouTube URL
    await page.fill('[data-testid="youtube-url-input"]', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    
    // Select analysis types
    await page.check('[data-testid="analysis-type-summary"]')
    await page.check('[data-testid="analysis-type-action-plan"]')
    
    // Start analysis
    await page.click('[data-testid="analyze-button"]')
    
    // Wait for analysis to complete
    await page.waitForSelector('[data-testid="analysis-results"]', { timeout: 30000 })
    
    // Verify results are displayed
    await expect(page.locator('[data-testid="summary-tab"]')).toBeVisible()
    await expect(page.locator('[data-testid="action-plan-tab"]')).toBeVisible()
    
    // Take screenshot for visual regression testing
    await page.screenshot({ path: 'test-results/analysis-complete.png' })
  
  TEST 'chat functionality works correctly':
    // Assume video is already analyzed
    await page.goto('http://localhost:3000/video/test-video-id')
    
    // Wait for chat interface to load
    await page.waitForSelector('[data-testid="chat-interface"]')
    
    // Send a message
    await page.fill('[data-testid="chat-input"]', 'What are the main points of this video?')
    await page.click('[data-testid="send-button"]')
    
    // Wait for AI response
    await page.waitForSelector('[data-testid="ai-message"]', { timeout: 15000 })
    
    // Verify message appears in chat
    await expect(page.locator('[data-testid="user-message"]')).toContainText('What are the main points')
    await expect(page.locator('[data-testid="ai-message"]')).toBeVisible()
  
  TEST 'guest user sees usage limits':
    // Navigate as guest user
    await page.goto('http://localhost:3000')
    
    // Should see guest limit indicator
    await expect(page.locator('[data-testid="guest-limit-display"]')).toBeVisible()
    await expect(page.locator('[data-testid="remaining-analyses"]')).toContainText('3 free analysis')
    
    // Analyze a video
    await page.fill('[data-testid="youtube-url-input"]', 'https://www.youtube.com/watch?v=test1')
    await page.click('[data-testid="analyze-button"]')
    await page.waitForSelector('[data-testid="analysis-results"]')
    
    // Should show updated count
    await expect(page.locator('[data-testid="remaining-analyses"]')).toContainText('2 free analysis')

DESCRIBE 'Authentication E2E Flow':
  
  TEST 'user can sign up and login':
    await page.goto('http://localhost:3000')
    
    // Click login button
    await page.click('[data-testid="login-button"]')
    
    // Switch to signup
    await page.click('[data-testid="switch-to-signup"]')
    
    // Fill signup form
    await page.fill('[data-testid="full-name-input"]', 'Test User')
    await page.fill('[data-testid="email-input"]', 'test@example.com')
    await page.fill('[data-testid="password-input"]', 'password123')
    await page.fill('[data-testid="confirm-password-input"]', 'password123')
    
    // Submit signup
    await page.click('[data-testid="signup-button"]')
    
    // Should show verification message
    await expect(page.locator('[data-testid="verification-message"]')).toBeVisible()
    
    // Mock email verification and login
    await page.click('[data-testid="switch-to-login"]')
    await page.fill('[data-testid="email-input"]', 'test@example.com')
    await page.fill('[data-testid="password-input"]', 'password123')
    await page.click('[data-testid="login-button"]')
    
    // Should be logged in
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible()
    await expect(page.locator('[data-testid="user-email"]')).toContainText('test@example.com')
```

## Performance Tests

### Lighthouse CI Configuration
```typescript
// Pseudocode: Performance testing setup
LIGHTHOUSE_CONFIG:
  ci:
    collect:
      url: ['http://localhost:3000', 'http://localhost:3000/video/test-id']
      numberOfRuns: 3
    assert:
      assertions:
        'categories:performance': ['warn', { minScore: 0.8 }]
        'categories:accessibility': ['error', { minScore: 0.9 }]
        'categories:best-practices': ['warn', { minScore: 0.8 }]
        'categories:seo': ['warn', { minScore: 0.8 }]
    upload:
      target: 'temporary-public-storage'

// Bundle analysis test
TEST 'bundle size is within limits':
  bundleAnalysis = await analyzeBundles()
  
  EXPECT(bundleAnalysis.totalSize).toBeLessThan(500 * 1024) // 500KB
  EXPECT(bundleAnalysis.chunks.vendor.size).toBeLessThan(200 * 1024) // 200KB
  EXPECT(bundleAnalysis.chunks.main.size).toBeLessThan(100 * 1024) // 100KB
```

This testing specification provides comprehensive coverage for all aspects of the Next.js frontend, ensuring reliability, performance, and maintainability through systematic testing approaches.