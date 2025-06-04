# Frontend Implementation TODO

## Overview

This document provides a comprehensive, detailed TODO list for implementing the missing features in the Next.js frontend application. Each item includes specific implementation details, file paths, and code examples to make implementation straightforward.

## Current Implementation Status

### ✅ Already Implemented
- Basic Next.js 14 project structure with App Router
- TypeScript configuration and type definitions
- Tailwind CSS + Shadcn/ui component library setup
- Basic layout components (AppLayout, Header, Sidebar, ChatPanel)
- UI components (Button, Input, Card, etc.)
- Constants and validation schemas
- Package.json with all required dependencies

### ❌ Missing Critical Features

## 1. State Management Implementation

### 1.1 Zustand Stores Setup
**Priority: HIGH**

**Files to Create:**
- `src/frontend/lib/stores/index.ts`
- `src/frontend/lib/stores/auth-store.ts`
- `src/frontend/lib/stores/ui-store.ts`
- `src/frontend/lib/stores/chat-store.ts`
- `src/frontend/lib/stores/settings-store.ts`
- `src/frontend/lib/stores/video-analysis-store.ts`

**Implementation Details:**

```typescript
// src/frontend/lib/stores/auth-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, Session } from '@/types';

interface AuthState {
  user: User | null;
  session: Session | null;
  isAuthenticated: boolean;
  guestAnalysisCount: number;
  isLoading: boolean;
}

interface AuthActions {
  setUser: (user: User | null) => void;
  setSession: (session: Session | null) => void;
  setGuestAnalysisCount: (count: number) => void;
  incrementGuestCount: () => void;
  checkGuestLimits: () => boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reset: () => void;
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      session: null,
      isAuthenticated: false,
      guestAnalysisCount: 0,
      isLoading: false,
      
      // Actions
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setSession: (session) => set({ session }),
      setGuestAnalysisCount: (count) => set({ guestAnalysisCount: count }),
      incrementGuestCount: () => {
        const { guestAnalysisCount } = get();
        set({ guestAnalysisCount: guestAnalysisCount + 1 });
      },
      checkGuestLimits: () => {
        const { guestAnalysisCount } = get();
        return guestAnalysisCount < 3; // MAX_GUEST_ANALYSES
      },
      login: async (email, password) => {
        set({ isLoading: true });
        try {
          // Implementation with Supabase auth
          // const { data, error } = await supabase.auth.signInWithPassword({ email, password });
          // Handle response and set user/session
        } catch (error) {
          throw error;
        } finally {
          set({ isLoading: false });
        }
      },
      logout: async () => {
        // Implementation with Supabase auth
        set({ user: null, session: null, isAuthenticated: false });
      },
      reset: () => set({
        user: null,
        session: null,
        isAuthenticated: false,
        guestAnalysisCount: 0,
        isLoading: false
      })
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        guestAnalysisCount: state.guestAnalysisCount
      })
    }
  )
);
```

**Missing Store Implementations:**
- UI Store (theme, sidebar state, notifications)
- Chat Store (sessions, messages, WebSocket state)
- Settings Store (model preferences, analysis types)
- Video Analysis Store (current analysis, progress, results)

## 2. API Integration Layer

### 2.1 API Client Setup
**Priority: HIGH**

**Files to Create:**
- `src/frontend/lib/api/client.ts`
- `src/frontend/lib/api/video-analysis.ts`
- `src/frontend/lib/api/chat.ts`
- `src/frontend/lib/api/auth.ts`
- `src/frontend/lib/api/websocket.ts`

**Implementation Details:**

```typescript
// src/frontend/lib/api/client.ts
import axios, { AxiosInstance, AxiosError } from 'axios';
import { API_CONFIG } from '@/constants';
import { useAuthStore } from '@/lib/stores';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        const { session } = useAuthStore.getState();
        if (session?.access_token) {
          config.headers.Authorization = `Bearer ${session.access_token}`;
        }
        config.metadata = { startTime: Date.now() };
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => {
        const duration = Date.now() - response.config.metadata.startTime;
        console.log(`API ${response.config.method?.toUpperCase()} ${response.config.url} - ${duration}ms`);
        return response;
      },
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Handle token refresh or logout
          useAuthStore.getState().logout();
        }
        return Promise.reject(error);
      }
    );
  }

  // HTTP methods
  async get<T>(url: string, params?: any): Promise<T> {
    const response = await this.client.get(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.post(url, data);
    return response.data;
  }

  // Add put, delete, patch methods...
}

export const apiClient = new ApiClient();
```

### 2.2 Video Analysis API Methods
**Files to Create:**
- Video analysis endpoints integration
- Progress tracking for long-running analysis
- Cache management integration

```typescript
// src/frontend/lib/api/video-analysis.ts
export class VideoAnalysisAPI {
  async analyzeVideo(request: VideoAnalysisRequest): Promise<AnalysisResult> {
    return apiClient.post('/api/v1/video/analyze', request);
  }

  async getAnalysisStatus(videoId: string): Promise<AnalysisProgress> {
    return apiClient.get(`/api/v1/video/${videoId}/status`);
  }

  async getAnalysisResult(videoId: string): Promise<AnalysisResult> {
    return apiClient.get(`/api/v1/video/${videoId}`);
  }

  async regenerateContent(videoId: string, taskKey: string, customInstruction?: string): Promise<any> {
    return apiClient.post(`/api/v1/video/${videoId}/regenerate`, {
      task_key: taskKey,
      custom_instruction: customInstruction
    });
  }
}
```

## 3. Authentication System

### 3.1 Supabase Integration
**Priority: HIGH**

**Files to Create:**
- `src/frontend/lib/auth/supabase.ts`
- `src/frontend/lib/auth/auth-provider.tsx`
- `src/frontend/components/auth/AuthModal.tsx`
- `src/frontend/components/auth/LoginForm.tsx`
- `src/frontend/components/auth/SignupForm.tsx`

**Implementation Details:**

```typescript
// src/frontend/lib/auth/supabase.ts
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export class AuthService {
  async signUp(email: string, password: string, fullName: string) {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
        },
      },
    });
    
    if (error) throw error;
    return data;
  }

  async signIn(email: string, password: string) {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    
    if (error) throw error;
    
    // Exchange Supabase token for FastAPI JWT
    const fastApiToken = await this.exchangeTokenWithFastAPI(data.session.access_token);
    
    return { ...data, fastApiToken };
  }

  private async exchangeTokenWithFastAPI(supabaseToken: string) {
    // Call FastAPI auth endpoint to exchange tokens
    const response = await fetch(`${API_CONFIG.BASE_URL}/api/v1/auth/exchange-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${supabaseToken}`,
      },
    });
    
    if (!response.ok) throw new Error('Token exchange failed');
    
    const { access_token } = await response.json();
    return access_token;
  }
}
```

### 3.2 Authentication Components
**Missing Components:**
- AuthModal with login/signup tabs
- Form validation with React Hook Form + Zod
- Password reset functionality
- Email verification handling
- Guest user limits display

## 4. Video Analysis Components

### 4.1 Video Input Component
**Priority: HIGH**

**Files to Create:**
- `src/frontend/components/video/VideoInput.tsx`
- `src/frontend/components/video/AnalysisTypeSelector.tsx`
- `src/frontend/components/video/ModelSelector.tsx`

**Implementation Details:**

```typescript
// src/frontend/components/video/VideoInput.tsx
'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { videoInputSchema, VideoInputData } from '@/lib/validations/video';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { ANALYSIS_TYPES } from '@/constants';

interface VideoInputProps {
  onAnalyze: (data: VideoInputData) => void;
  isAnalyzing: boolean;
}

export function VideoInput({ onAnalyze, isAnalyzing }: VideoInputProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
  } = useForm<VideoInputData>({
    resolver: zodResolver(videoInputSchema),
    defaultValues: {
      analysisTypes: ['summary'],
      useCache: true,
    },
  });

  const selectedTypes = watch('analysisTypes');

  const onSubmit = (data: VideoInputData) => {
    onAnalyze(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* YouTube URL Input */}
      <div className="space-y-2">
        <Label htmlFor="url">YouTube URL</Label>
        <Input
          id="url"
          {...register('url')}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={isAnalyzing}
        />
        {errors.url && (
          <p className="text-sm text-destructive">{errors.url.message}</p>
        )}
      </div>

      {/* Analysis Types */}
      <div className="space-y-3">
        <Label>Analysis Types</Label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {ANALYSIS_TYPES.map((type) => (
            <div key={type.id} className="flex items-center space-x-2">
              <Checkbox
                id={type.id}
                checked={selectedTypes.includes(type.id)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    setValue('analysisTypes', [...selectedTypes, type.id]);
                  } else {
                    setValue('analysisTypes', selectedTypes.filter(t => t !== type.id));
                  }
                }}
                disabled={isAnalyzing}
              />
              <div className="grid gap-1.5 leading-none">
                <label
                  htmlFor={type.id}
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {type.icon} {type.label}
                </label>
                <p className="text-xs text-muted-foreground">
                  {type.description}
                </p>
              </div>
            </div>
          ))}
        </div>
        {errors.analysisTypes && (
          <p className="text-sm text-destructive">{errors.analysisTypes.message}</p>
        )}
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={isAnalyzing}
        className="w-full"
      >
        {isAnalyzing ? 'Analyzing...' : 'Analyze Video'}
      </Button>
    </form>
  );
}
```

### 4.2 Analysis Results Components
**Files to Create:**
- `src/frontend/components/video/AnalysisResults.tsx`
- `src/frontend/components/video/VideoPlayer.tsx`
- `src/frontend/components/video/ResultsTabs.tsx`
- `src/frontend/components/video/ContentRegenerator.tsx`

**Missing Features:**
- Tabbed interface for different analysis types
- Video player with transcript synchronization
- Content regeneration with custom instructions
- Export functionality (PDF, markdown)
- Social sharing buttons

## 5. Real-time Chat System

### 5.1 WebSocket Integration
**Priority: HIGH**

**Files to Create:**
- `src/frontend/lib/api/websocket.ts`
- `src/frontend/hooks/useWebSocket.ts`
- `src/frontend/hooks/useChat.ts`

**Implementation Details:**

```typescript
// src/frontend/lib/api/websocket.ts
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(
    private url: string,
    private onMessage: (data: any) => void,
    private onError: (error: Event) => void,
    private onClose: () => void
  ) {}

  connect(sessionId: string, token: string) {
    const wsUrl = `${this.url}/ws/chat/${sessionId}?token=${token}`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError(error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.onClose();
      this.attemptReconnect(sessionId, token);
    };
  }

  sendMessage(message: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ message }));
    }
  }

  private attemptReconnect(sessionId: string, token: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect(sessionId, token);
      }, this.reconnectDelay * this.reconnectAttempts);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

### 5.2 Chat Interface Components
**Files to Create:**
- `src/frontend/components/chat/ChatInterface.tsx`
- `src/frontend/components/chat/MessageList.tsx`
- `src/frontend/components/chat/MessageInput.tsx`
- `src/frontend/components/chat/StreamingMessage.tsx`

**Missing Features:**
- Real-time message streaming with typing indicators
- Message persistence and history
- Chat session management
- Message export functionality

## 6. Settings and Configuration

### 6.1 Settings Components
**Priority: MEDIUM**

**Files to Create:**
- `src/frontend/components/settings/SettingsModal.tsx`
- `src/frontend/components/settings/ModelSettings.tsx`
- `src/frontend/components/settings/AnalysisSettings.tsx`
- `src/frontend/components/settings/CacheSettings.tsx`

**Implementation Details:**

```typescript
// src/frontend/components/settings/SettingsModal.tsx
export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSettings } = useSettingsStore();
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>
        
        <Tabs defaultValue="model" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="model">Model</TabsTrigger>
            <TabsTrigger value="analysis">Analysis</TabsTrigger>
            <TabsTrigger value="cache">Cache</TabsTrigger>
            <TabsTrigger value="account">Account</TabsTrigger>
          </TabsList>
          
          <TabsContent value="model">
            <ModelSettings settings={settings} onUpdate={updateSettings} />
          </TabsContent>
          
          <TabsContent value="analysis">
            <AnalysisSettings settings={settings} onUpdate={updateSettings} />
          </TabsContent>
          
          <TabsContent value="cache">
            <CacheSettings />
          </TabsContent>
          
          <TabsContent value="account">
            <AccountSettings />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
```

## 7. Navigation and Routing

### 7.1 App Router Pages
**Priority: HIGH**

**Files to Create:**
- `src/frontend/app/(dashboard)/analyze/page.tsx`
- `src/frontend/app/(dashboard)/history/page.tsx`
- `src/frontend/app/(dashboard)/settings/page.tsx`
- `src/frontend/app/(dashboard)/video/[id]/page.tsx`
- `src/frontend/app/(auth)/login/page.tsx`
- `src/frontend/app/(auth)/signup/page.tsx`

**Implementation Details:**

```typescript
// src/frontend/app/(dashboard)/analyze/page.tsx
'use client';

import { useState } from 'react';
import { VideoInput } from '@/components/video/VideoInput';
import { AnalysisResults } from '@/components/video/AnalysisResults';
import { useVideoAnalysis } from '@/hooks/useVideoAnalysis';
import { VideoInputData } from '@/lib/validations/video';

export default function AnalyzePage() {
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);
  const { analyzeVideo, isAnalyzing } = useVideoAnalysis();

  const handleAnalyze = async (data: VideoInputData) => {
    try {
      const result = await analyzeVideo(data);
      setCurrentVideoId(result.video_id);
    } catch (error) {
      console.error('Analysis failed:', error);
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold">Analyze YouTube Video</h1>
        <p className="text-muted-foreground">
          Enter a YouTube URL to get AI-powered analysis and insights
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div>
          <VideoInput onAnalyze={handleAnalyze} isAnalyzing={isAnalyzing} />
        </div>
        
        <div>
          {currentVideoId && (
            <AnalysisResults videoId={currentVideoId} />
          )}
        </div>
      </div>
    </div>
  );
}
```

### 7.2 Route Protection
**Files to Create:**
- `src/frontend/components/auth/ProtectedRoute.tsx`
- `src/frontend/middleware.ts`

## 8. Custom Hooks

### 8.1 Data Fetching Hooks
**Priority: HIGH**

**Files to Create:**
- `src/frontend/hooks/useVideoAnalysis.ts`
- `src/frontend/hooks/useChat.ts`
- `src/frontend/hooks/useAuth.ts`
- `src/frontend/hooks/useSettings.ts`

**Implementation Details:**

```typescript
// src/frontend/hooks/useVideoAnalysis.ts
import { useMutation, useQuery } from '@tanstack/react-query';
import { videoAnalysisAPI } from '@/lib/api/video-analysis';
import { QUERY_KEYS } from '@/constants';

export function useVideoAnalysis() {
  const analyzeVideoMutation = useMutation({
    mutationFn: videoAnalysisAPI.analyzeVideo,
    onSuccess: (data) => {
      // Invalidate and refetch related queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.VIDEO_ANALYSIS(data.video_id) });
    },
  });

  const getAnalysisQuery = (videoId: string) => useQuery({
    queryKey: QUERY_KEYS.VIDEO_ANALYSIS(videoId),
    queryFn: () => videoAnalysisAPI.getAnalysisResult(videoId),
    enabled: !!videoId,
  });

  return {
    analyzeVideo: analyzeVideoMutation.mutateAsync,
    isAnalyzing: analyzeVideoMutation.isPending,
    getAnalysis: getAnalysisQuery,
  };
}
```

## 9. Error Handling and Loading States

### 9.1 Error Boundaries
**Priority: MEDIUM**

**Files to Create:**
- `src/frontend/components/error/ErrorBoundary.tsx`
- `src/frontend/components/error/ErrorFallback.tsx`
- `src/frontend/lib/error-handling.ts`

### 9.2 Loading Components
**Files to Create:**
- `src/frontend/components/ui/loading-spinner.tsx`
- `src/frontend/components/ui/skeleton.tsx`
- `src/frontend/components/video/AnalysisProgress.tsx`

## 10. Testing Setup

### 10.1 Test Configuration
**Priority: LOW**

**Files to Create:**
- `src/frontend/jest.config.js`
- `src/frontend/jest.setup.js`
- `src/frontend/playwright.config.ts`
- `src/frontend/__tests__/setup.ts`

### 10.2 Test Files
**Files to Create:**
- Component tests for all major components
- Hook tests for custom hooks
- Integration tests for API calls
- E2E tests for user workflows

## 11. Environment Configuration

### 11.1 Environment Variables
**Priority: HIGH**

**Files to Create:**
- `src/frontend/.env.local.example`
- `src/frontend/.env.development`
- `src/frontend/.env.production`

**Required Environment Variables:**
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

# Feature Flags
NEXT_PUBLIC_ENABLE_CHAT=true
NEXT_PUBLIC_ENABLE_SUBTITLES=true
NEXT_PUBLIC_ENABLE_ANALYTICS=false

# User Limits
NEXT_PUBLIC_MAX_GUEST_ANALYSES=3
```

## 12. Performance Optimizations

### 12.1 Code Splitting
**Files to Create:**
- Dynamic imports for heavy components
- Route-based code splitting
- Component lazy loading

### 12.2 Caching Strategy
**Implementation Needed:**
- TanStack Query cache configuration
- Service worker for offline support
- Image optimization setup

## Implementation Priority Order

### Phase 1 (Critical - Week 1)
1. Complete Zustand stores implementation
2. API client and video analysis integration
3. Basic authentication with Supabase
4. Video input and analysis results components
5. Navigation and routing setup

### Phase 2 (Important - Week 2)
1. Real-time chat with WebSocket
2. Settings and configuration
3. Error handling and loading states
4. Custom hooks implementation
5. Environment configuration

### Phase 3 (Enhancement - Week 3)
1. Testing setup and test files
2. Performance optimizations
3. Advanced features (export, sharing)
4. Documentation and deployment
5. Bug fixes and polish

## Estimated Implementation Time

- **Total Estimated Time:** 3-4 weeks for full implementation
- **Critical Path:** State management → API integration → Authentication → Core components
- **Team Size:** 2-3 developers recommended
- **Complexity Level:** Medium to High (due to real-time features and state management)

This TODO provides a comprehensive roadmap for implementing the complete Next.js frontend with all features from the Streamlit application while adding modern React patterns and improved user experience.