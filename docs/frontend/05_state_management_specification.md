# State Management Specification

## Overview

This specification defines the comprehensive state management architecture using Zustand for client state and TanStack Query for server state, providing efficient data flow and synchronization across the Next.js application.

## Zustand Store Architecture

### AuthStore
```typescript
// Pseudocode: Authentication state management
INTERFACE AuthState:
  user: User | null
  session: Session | null
  isAuthenticated: boolean
  guestAnalysisCount: number
  isLoading: boolean

INTERFACE AuthActions:
  setUser: (user: User | null) => void
  setSession: (session: Session | null) => void
  setGuestAnalysisCount: (count: number) => void
  incrementGuestCount: () => void
  checkGuestLimits: () => boolean
  reset: () => void

STORE useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  // Initial state
  user: null,
  session: null,
  isAuthenticated: false,
  guestAnalysisCount: 0,
  isLoading: true,
  
  // Actions
  setUser: (user) => set((state) => ({
    user,
    isAuthenticated: !!user,
    isLoading: false
  })),
  
  setSession: (session) => set({ session }),
  
  setGuestAnalysisCount: (count) => {
    localStorage.setItem('guestAnalysisCount', count.toString())
    set({ guestAnalysisCount: count })
  },
  
  incrementGuestCount: () => {
    newCount = get().guestAnalysisCount + 1
    get().setGuestAnalysisCount(newCount)
  },
  
  checkGuestLimits: () => {
    maxAnalyses = ENV.NEXT_PUBLIC_MAX_GUEST_ANALYSES || 3
    RETURN get().guestAnalysisCount < maxAnalyses
  },
  
  reset: () => set({
    user: null,
    session: null,
    isAuthenticated: false,
    guestAnalysisCount: 0,
    isLoading: false
  })
}))

// Selectors for optimized re-renders
SELECTORS:
  useUser = () => useAuthStore(state => state.user)
  useIsAuthenticated = () => useAuthStore(state => state.isAuthenticated)
  useGuestCount = () => useAuthStore(state => state.guestAnalysisCount)
  useAuthLoading = () => useAuthStore(state => state.isLoading)
```

### UIStore
```typescript
// Pseudocode: UI state management
INTERFACE UIState:
  theme: 'light' | 'dark' | 'system'
  sidebarOpen: boolean
  modals: Record<string, boolean>
  notifications: Notification[]
  loading: Record<string, boolean>

INTERFACE UIActions:
  setTheme: (theme: UIState['theme']) => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  openModal: (modalId: string) => void
  closeModal: (modalId: string) => void
  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
  setLoading: (key: string, loading: boolean) => void
  reset: () => void

STORE useUIStore = create<UIState & UIActions>((set, get) => ({
  // Initial state
  theme: 'system',
  sidebarOpen: true,
  modals: {},
  notifications: [],
  loading: {},
  
  // Actions
  setTheme: (theme) => {
    localStorage.setItem('theme', theme)
    set({ theme })
  },
  
  toggleSidebar: () => set((state) => ({ 
    sidebarOpen: !state.sidebarOpen 
  })),
  
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  
  openModal: (modalId) => set((state) => ({
    modals: { ...state.modals, [modalId]: true }
  })),
  
  closeModal: (modalId) => set((state) => ({
    modals: { ...state.modals, [modalId]: false }
  })),
  
  addNotification: (notification) => {
    id = generateId()
    newNotification = { ...notification, id }
    
    set((state) => ({
      notifications: [...state.notifications, newNotification]
    }))
    
    // Auto-remove after delay
    IF notification.duration !== 0:
      setTimeout(() => {
        get().removeNotification(id)
      }, notification.duration || 5000)
  },
  
  removeNotification: (id) => set((state) => ({
    notifications: state.notifications.filter(n => n.id !== id)
  })),
  
  setLoading: (key, loading) => set((state) => ({
    loading: { ...state.loading, [key]: loading }
  })),
  
  reset: () => set({
    sidebarOpen: true,
    modals: {},
    notifications: [],
    loading: {}
  })
}))

// Selectors
SELECTORS:
  useTheme = () => useUIStore(state => state.theme)
  useSidebarOpen = () => useUIStore(state => state.sidebarOpen)
  useModal = (modalId: string) => useUIStore(state => state.modals[modalId] || false)
  useNotifications = () => useUIStore(state => state.notifications)
  useLoading = (key: string) => useUIStore(state => state.loading[key] || false)
```

### SettingsStore
```typescript
// Pseudocode: Application settings management
INTERFACE SettingsState:
  modelName: string
  temperature: number
  transcriptionModel: string
  subtitleLanguage: string
  useCache: boolean
  analysisTypes: string[]

INTERFACE SettingsActions:
  updateSettings: (settings: Partial<SettingsState>) => void
  resetToDefaults: () => void
  loadFromStorage: () => void
  saveToStorage: () => void

CONSTANTS:
  DEFAULT_SETTINGS: SettingsState = {
    modelName: 'gpt-4o-mini',
    temperature: 0.7,
    transcriptionModel: 'openai',
    subtitleLanguage: 'en',
    useCache: true,
    analysisTypes: ['Summary & Classification']
  }

STORE useSettingsStore = create<SettingsState & SettingsActions>((set, get) => ({
  // Initial state from defaults
  ...DEFAULT_SETTINGS,
  
  // Actions
  updateSettings: (newSettings) => {
    set((state) => ({ ...state, ...newSettings }))
    get().saveToStorage()
  },
  
  resetToDefaults: () => {
    set(DEFAULT_SETTINGS)
    get().saveToStorage()
  },
  
  loadFromStorage: () => {
    TRY:
      stored = localStorage.getItem('appSettings')
      IF stored:
        settings = JSON.parse(stored)
        // Merge with defaults to handle new settings
        mergedSettings = { ...DEFAULT_SETTINGS, ...settings }
        set(mergedSettings)
    CATCH error:
      console.warn('Failed to load settings from storage:', error)
      get().resetToDefaults()
  },
  
  saveToStorage: () => {
    TRY:
      settings = get()
      // Extract only settings, not actions
      settingsToSave = {
        modelName: settings.modelName,
        temperature: settings.temperature,
        transcriptionModel: settings.transcriptionModel,
        subtitleLanguage: settings.subtitleLanguage,
        useCache: settings.useCache,
        analysisTypes: settings.analysisTypes
      }
      localStorage.setItem('appSettings', JSON.stringify(settingsToSave))
    CATCH error:
      console.warn('Failed to save settings to storage:', error)
  }
}))

// Initialize settings from storage
useSettingsStore.getState().loadFromStorage()

// Selectors
SELECTORS:
  useModelName = () => useSettingsStore(state => state.modelName)
  useTemperature = () => useSettingsStore(state => state.temperature)
  useTranscriptionModel = () => useSettingsStore(state => state.transcriptionModel)
  useSubtitleLanguage = () => useSettingsStore(state => state.subtitleLanguage)
  useAnalysisTypes = () => useSettingsStore(state => state.analysisTypes)
```

### VideoAnalysisStore
```typescript
// Pseudocode: Video analysis state management
INTERFACE VideoAnalysisState:
  currentVideoId: string | null
  analysisStatus: 'idle' | 'analyzing' | 'complete' | 'error'
  analysisProgress: number
  analysisResults: AnalysisResult | null
  error: string | null
  tokenUsage: TokenUsage | null

INTERFACE VideoAnalysisActions:
  setCurrentVideo: (videoId: string) => void
  setAnalysisStatus: (status: VideoAnalysisState['analysisStatus']) => void
  setAnalysisProgress: (progress: number) => void
  setAnalysisResults: (results: AnalysisResult) => void
  setError: (error: string | null) => void
  setTokenUsage: (usage: TokenUsage) => void
  reset: () => void
  clearCurrentAnalysis: () => void

STORE useVideoAnalysisStore = create<VideoAnalysisState & VideoAnalysisActions>((set, get) => ({
  // Initial state
  currentVideoId: null,
  analysisStatus: 'idle',
  analysisProgress: 0,
  analysisResults: null,
  error: null,
  tokenUsage: null,
  
  // Actions
  setCurrentVideo: (videoId) => set({ 
    currentVideoId: videoId,
    analysisStatus: 'idle',
    analysisProgress: 0,
    error: null
  }),
  
  setAnalysisStatus: (status) => set({ analysisStatus: status }),
  
  setAnalysisProgress: (progress) => set({ analysisProgress: progress }),
  
  setAnalysisResults: (results) => set({ 
    analysisResults: results,
    analysisStatus: 'complete',
    analysisProgress: 100
  }),
  
  setError: (error) => set({ 
    error,
    analysisStatus: error ? 'error' : get().analysisStatus
  }),
  
  setTokenUsage: (usage) => set({ tokenUsage: usage }),
  
  reset: () => set({
    currentVideoId: null,
    analysisStatus: 'idle',
    analysisProgress: 0,
    analysisResults: null,
    error: null,
    tokenUsage: null
  }),
  
  clearCurrentAnalysis: () => set({
    analysisStatus: 'idle',
    analysisProgress: 0,
    analysisResults: null,
    error: null
  })
}))

// Selectors
SELECTORS:
  useCurrentVideoId = () => useVideoAnalysisStore(state => state.currentVideoId)
  useAnalysisStatus = () => useVideoAnalysisStore(state => state.analysisStatus)
  useAnalysisProgress = () => useVideoAnalysisStore(state => state.analysisProgress)
  useAnalysisResults = () => useVideoAnalysisStore(state => state.analysisResults)
  useAnalysisError = () => useVideoAnalysisStore(state => state.error)
  useTokenUsage = () => useVideoAnalysisStore(state => state.tokenUsage)
```

## TanStack Query Configuration

### Query Client Setup
```typescript
// Pseudocode: React Query configuration
FUNCTION createQueryClient(): QueryClient:
  RETURN new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,        // 5 minutes
        cacheTime: 10 * 60 * 1000,       // 10 minutes
        retry: (failureCount, error) => {
          // Don't retry on 4xx errors
          IF error.response?.status >= 400 AND error.response?.status < 500:
            RETURN false
          RETURN failureCount < 3
        },
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
        refetchOnWindowFocus: false,
        refetchOnReconnect: true
      },
      mutations: {
        retry: false,
        onError: (error) => {
          // Global error handling for mutations
          IF error.response?.status === 401:
            useAuthStore.getState().reset()
            router.push('/login')
          ELSE:
            useUIStore.getState().addNotification({
              title: 'Error',
              description: error.message || 'An unexpected error occurred',
              type: 'error'
            })
        }
      }
    }
  })

// Query keys factory
QUERY_KEYS = {
  // Video analysis
  videoAnalysis: (videoId: string) => ['videoAnalysis', videoId],
  analysisStatus: (videoId: string) => ['analysisStatus', videoId],
  transcript: (videoId: string) => ['transcript', videoId],
  
  // Chat
  chatSession: (videoId: string) => ['chatSession', videoId],
  chatHistory: (sessionId: string) => ['chatHistory', sessionId],
  
  // User data
  userStats: () => ['userStats'],
  tokenUsage: () => ['tokenUsage'],
  
  // Configuration
  availableModels: () => ['availableModels'],
  supportedLanguages: () => ['supportedLanguages'],
  
  // Cache
  cacheStats: () => ['cacheStats']
}
```

### Custom Query Hooks
```typescript
// Pseudocode: Custom hooks for API integration
HOOK useVideoAnalysis:
  PARAMS:
    videoId: string
    enabled?: boolean = true
  
  RETURN useQuery({
    queryKey: QUERY_KEYS.videoAnalysis(videoId),
    queryFn: () => getVideoAnalysis(videoId),
    enabled: enabled && !!videoId,
    onSuccess: (data) => {
      useVideoAnalysisStore.getState().setAnalysisResults(data)
    },
    onError: (error) => {
      useVideoAnalysisStore.getState().setError(error.message)
    }
  })

HOOK useAnalyzeVideoMutation:
  RETURN useMutation({
    mutationFn: analyzeVideo,
    onMutate: (variables) => {
      // Optimistic update
      useVideoAnalysisStore.getState().setCurrentVideo(variables.videoId)
      useVideoAnalysisStore.getState().setAnalysisStatus('analyzing')
      useUIStore.getState().setLoading('videoAnalysis', true)
    },
    onSuccess: (data, variables) => {
      // Update cache
      queryClient.setQueryData(
        QUERY_KEYS.videoAnalysis(variables.videoId),
        data
      )
      
      // Update store
      useVideoAnalysisStore.getState().setAnalysisResults(data)
      
      // Increment guest count if not authenticated
      IF NOT useAuthStore.getState().isAuthenticated:
        useAuthStore.getState().incrementGuestCount()
      
      // Show success notification
      useUIStore.getState().addNotification({
        title: 'Analysis Complete',
        description: 'Video analysis has been completed successfully',
        type: 'success'
      })
    },
    onError: (error) => {
      useVideoAnalysisStore.getState().setError(error.message)
      useUIStore.getState().addNotification({
        title: 'Analysis Failed',
        description: error.message,
        type: 'error'
      })
    },
    onSettled: () => {
      useUIStore.getState().setLoading('videoAnalysis', false)
    }
  })

HOOK useChatSession:
  PARAMS:
    videoId: string
    enabled?: boolean = true
  
  RETURN useQuery({
    queryKey: QUERY_KEYS.chatSession(videoId),
    queryFn: () => createChatSession(videoId),
    enabled: enabled && !!videoId,
    staleTime: Infinity, // Chat sessions don't change
    cacheTime: 30 * 60 * 1000 // 30 minutes
  })

HOOK useSendChatMessageMutation:
  RETURN useMutation({
    mutationFn: sendChatMessage,
    onMutate: async (variables) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(
        QUERY_KEYS.chatHistory(variables.sessionId)
      )
      
      // Snapshot previous value
      previousMessages = queryClient.getQueryData(
        QUERY_KEYS.chatHistory(variables.sessionId)
      )
      
      // Optimistically update
      queryClient.setQueryData(
        QUERY_KEYS.chatHistory(variables.sessionId),
        (old: ChatMessage[]) => [
          ...old,
          {
            id: generateId(),
            role: 'user',
            content: variables.message,
            timestamp: new Date()
          }
        ]
      )
      
      RETURN { previousMessages }
    },
    onError: (error, variables, context) => {
      // Rollback on error
      IF context?.previousMessages:
        queryClient.setQueryData(
          QUERY_KEYS.chatHistory(variables.sessionId),
          context.previousMessages
        )
    },
    onSettled: (data, error, variables) => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries(
        QUERY_KEYS.chatHistory(variables.sessionId)
      )
    }
  })

HOOK useUserStats:
  user = useUser()
  
  RETURN useQuery({
    queryKey: QUERY_KEYS.userStats(),
    queryFn: getUserStats,
    enabled: !!user,
    staleTime: 2 * 60 * 1000 // 2 minutes
  })
```

## State Persistence

### LocalStorage Integration
```typescript
// Pseudocode: State persistence utilities
FUNCTION persistStore<T>(
  storeName: string,
  store: StateCreator<T>
): StateCreator<T>:
  RETURN (set, get, api) => {
    // Load initial state from localStorage
    TRY:
      stored = localStorage.getItem(storeName)
      IF stored:
        initialState = JSON.parse(stored)
        // Merge with store defaults
        store = { ...store(set, get, api), ...initialState }
    CATCH error:
      console.warn(`Failed to load ${storeName} from localStorage:`, error)
    
    // Create store with persistence
    storeApi = store(
      (partial, replace) => {
        set(partial, replace)
        
        // Save to localStorage after state update
        TRY:
          currentState = get()
          localStorage.setItem(storeName, JSON.stringify(currentState))
        CATCH error:
          console.warn(`Failed to save ${storeName} to localStorage:`, error)
      },
      get,
      api
    )
    
    RETURN storeApi

// Usage example
STORE usePersistedSettingsStore = create(
  persistStore('appSettings', (set, get) => ({
    // Store implementation
  }))
)
```

This state management specification provides a comprehensive, type-safe, and performant state architecture that efficiently handles both client and server state while maintaining data consistency across the application.