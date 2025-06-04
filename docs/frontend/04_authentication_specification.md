# Authentication Specification

## Overview

This specification defines the authentication system for the Next.js frontend, integrating with Supabase Auth and the FastAPI backend to provide secure user authentication, guest access, and session management.

## Authentication Architecture

### AuthProvider Component
```typescript
// Pseudocode: Authentication context provider
COMPONENT AuthProvider:
  PROPS:
    children: ReactNode
  
  STATE:
    user: User | null = null
    session: Session | null = null
    isLoading: boolean = true
    guestAnalysisCount: number = 0
  
  CONTEXT_VALUE:
    user: user,
    session: session,
    isLoading: isLoading,
    isAuthenticated: !!user,
    guestAnalysisCount: guestAnalysisCount,
    login: login,
    signup: signup,
    logout: logout,
    resetPassword: resetPassword,
    updatePassword: updatePassword,
    checkGuestLimits: checkGuestLimits,
    incrementGuestCount: incrementGuestCount
  
  EFFECTS:
    useEffect(() => {
      // Initialize auth state from Supabase
      initializeAuth()
      
      // Listen for auth state changes
      authListener = supabase.auth.onAuthStateChange(
        (event, session) => handleAuthStateChange(event, session)
      )
      
      RETURN () => authListener.data.subscription.unsubscribe()
    }, [])
    
    useEffect(() => {
      // Load guest analysis count from localStorage
      savedCount = localStorage.getItem('guestAnalysisCount')
      IF savedCount:
        setGuestAnalysisCount(parseInt(savedCount, 10))
    }, [])
  
  METHODS:
    FUNCTION initializeAuth():
      TRY:
        { data: { session } } = await supabase.auth.getSession()
        IF session:
          setSession(session)
          setUser(session.user)
        setIsLoading(false)
      CATCH error:
        console.error('Auth initialization error:', error)
        setIsLoading(false)
    
    FUNCTION handleAuthStateChange(event: AuthChangeEvent, session: Session | null):
      setSession(session)
      setUser(session?.user ?? null)
      
      IF event === 'SIGNED_OUT':
        // Clear guest count on logout
        setGuestAnalysisCount(0)
        localStorage.removeItem('guestAnalysisCount')
    
    FUNCTION login(credentials: LoginCredentials): Promise<AuthResult>:
      TRY:
        { data, error } = await supabase.auth.signInWithPassword({
          email: credentials.email,
          password: credentials.password
        })
        
        IF error:
          THROW new AuthError(error.message)
        
        // Exchange Supabase session for FastAPI JWT
        apiToken = await exchangeSupabaseToken(data.session.access_token)
        
        // Store API token
        setApiToken(apiToken)
        
        RETURN { success: true, user: data.user }
      CATCH error:
        THROW new AuthError(error.message)
    
    FUNCTION signup(userData: SignupData): Promise<AuthResult>:
      TRY:
        { data, error } = await supabase.auth.signUp({
          email: userData.email,
          password: userData.password,
          options: {
            data: {
              full_name: userData.fullName
            }
          }
        })
        
        IF error:
          THROW new AuthError(error.message)
        
        RETURN { 
          success: true, 
          user: data.user,
          needsVerification: !data.session
        }
      CATCH error:
        THROW new AuthError(error.message)
    
    FUNCTION logout(): Promise<void>:
      TRY:
        await supabase.auth.signOut()
        removeApiToken()
        
        // Clear all stored data
        localStorage.clear()
        sessionStorage.clear()
        
        // Reset stores
        useSettingsStore.getState().resetToDefaults()
        useUIStore.getState().reset()
      CATCH error:
        console.error('Logout error:', error)
    
    FUNCTION checkGuestLimits(): boolean:
      maxAnalyses = ENV.NEXT_PUBLIC_MAX_GUEST_ANALYSES || 3
      RETURN guestAnalysisCount < maxAnalyses
    
    FUNCTION incrementGuestCount():
      newCount = guestAnalysisCount + 1
      setGuestAnalysisCount(newCount)
      localStorage.setItem('guestAnalysisCount', newCount.toString())
  
  RENDER:
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>

// Custom hook for using auth context
HOOK useAuth:
  context = useContext(AuthContext)
  IF NOT context:
    THROW new Error('useAuth must be used within AuthProvider')
  RETURN context
```

### Authentication Components

#### AuthModal Component
```typescript
// Pseudocode: Authentication modal with login/signup forms
COMPONENT AuthModal:
  PROPS:
    isOpen: boolean
    onClose: () => void
    defaultMode?: 'login' | 'signup'
  
  STATE:
    mode: 'login' | 'signup' | 'reset' = defaultMode || 'login'
    isLoading: boolean = false
    error: string | null = null
  
  HOOKS:
    { login, signup, resetPassword } = useAuth()
  
  METHODS:
    FUNCTION handleLogin(data: LoginFormData):
      setIsLoading(true)
      setError(null)
      
      TRY:
        await login(data)
        onClose()
        showNotification('Successfully logged in!', 'success')
      CATCH error:
        setError(error.message)
      FINALLY:
        setIsLoading(false)
    
    FUNCTION handleSignup(data: SignupFormData):
      setIsLoading(true)
      setError(null)
      
      TRY:
        result = await signup(data)
        
        IF result.needsVerification:
          showNotification('Please check your email to verify your account', 'info')
          setMode('login')
        ELSE:
          onClose()
          showNotification('Account created successfully!', 'success')
      CATCH error:
        setError(error.message)
      FINALLY:
        setIsLoading(false)
    
    FUNCTION handleResetPassword(email: string):
      setIsLoading(true)
      setError(null)
      
      TRY:
        await resetPassword(email)
        showNotification('Password reset email sent!', 'success')
        setMode('login')
      CATCH error:
        setError(error.message)
      FINALLY:
        setIsLoading(false)
  
  RENDER:
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === 'login' && 'Sign In'}
            {mode === 'signup' && 'Create Account'}
            {mode === 'reset' && 'Reset Password'}
          </DialogTitle>
        </DialogHeader>
        
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {mode === 'login' && (
          <LoginForm 
            onSubmit={handleLogin}
            isLoading={isLoading}
            onSwitchToSignup={() => setMode('signup')}
            onSwitchToReset={() => setMode('reset')}
          />
        )}
        
        {mode === 'signup' && (
          <SignupForm
            onSubmit={handleSignup}
            isLoading={isLoading}
            onSwitchToLogin={() => setMode('login')}
          />
        )}
        
        {mode === 'reset' && (
          <ResetPasswordForm
            onSubmit={handleResetPassword}
            isLoading={isLoading}
            onSwitchToLogin={() => setMode('login')}
          />
        )}
      </DialogContent>
    </Dialog>

COMPONENT LoginForm:
  PROPS:
    onSubmit: (data: LoginFormData) => void
    isLoading: boolean
    onSwitchToSignup: () => void
    onSwitchToReset: () => void
  
  VALIDATION:
    SCHEMA LoginSchema = z.object({
      email: z.string().email('Please enter a valid email'),
      password: z.string().min(6, 'Password must be at least 6 characters')
    })
  
  FORM:
    form = useForm<LoginFormData>({
      resolver: zodResolver(LoginSchema),
      defaultValues: {
        email: '',
        password: ''
      }
    })
  
  RENDER:
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="Enter your email"
          {...form.register('email')}
          error={form.formState.errors.email?.message}
        />
      </div>
      
      <div>
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder="Enter your password"
          {...form.register('password')}
          error={form.formState.errors.password?.message}
        />
      </div>
      
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Signing in...
          </>
        ) : (
          'Sign In'
        )}
      </Button>
      
      <div className="text-center space-y-2">
        <Button
          type="button"
          variant="link"
          onClick={onSwitchToReset}
          className="text-sm"
        >
          Forgot your password?
        </Button>
        
        <div className="text-sm text-muted-foreground">
          Don't have an account?{' '}
          <Button
            type="button"
            variant="link"
            onClick={onSwitchToSignup}
            className="p-0 h-auto"
          >
            Sign up
          </Button>
        </div>
      </div>
    </form>

COMPONENT SignupForm:
  PROPS:
    onSubmit: (data: SignupFormData) => void
    isLoading: boolean
    onSwitchToLogin: () => void
  
  VALIDATION:
    SCHEMA SignupSchema = z.object({
      fullName: z.string().min(2, 'Name must be at least 2 characters'),
      email: z.string().email('Please enter a valid email'),
      password: z.string().min(6, 'Password must be at least 6 characters'),
      confirmPassword: z.string()
    }).refine(data => data.password === data.confirmPassword, {
      message: "Passwords don't match",
      path: ["confirmPassword"]
    })
  
  FORM:
    form = useForm<SignupFormData>({
      resolver: zodResolver(SignupSchema),
      defaultValues: {
        fullName: '',
        email: '',
        password: '',
        confirmPassword: ''
      }
    })
  
  RENDER:
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="fullName">Full Name</Label>
        <Input
          id="fullName"
          placeholder="Enter your full name"
          {...form.register('fullName')}
          error={form.formState.errors.fullName?.message}
        />
      </div>
      
      <div>
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="Enter your email"
          {...form.register('email')}
          error={form.formState.errors.email?.message}
        />
      </div>
      
      <div>
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder="Create a password"
          {...form.register('password')}
          error={form.formState.errors.password?.message}
        />
      </div>
      
      <div>
        <Label htmlFor="confirmPassword">Confirm Password</Label>
        <Input
          id="confirmPassword"
          type="password"
          placeholder="Confirm your password"
          {...form.register('confirmPassword')}
          error={form.formState.errors.confirmPassword?.message}
        />
      </div>
      
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Creating account...
          </>
        ) : (
          'Create Account'
        )}
      </Button>
      
      <div className="text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Button
          type="button"
          variant="link"
          onClick={onSwitchToLogin}
          className="p-0 h-auto"
        >
          Sign in
        </Button>
      </div>
    </form>
```

### UserProfile Component
```typescript
// Pseudocode: User profile and statistics display
COMPONENT UserProfile:
  PROPS:
    user: User
    onEditProfile: () => void
    onChangePassword: () => void
  
  HOOKS:
    userStats = useQuery(['userStats'], getUserStats, {
      enabled: !!user
    })
    tokenUsage = useQuery(['tokenUsage'], getTokenUsage, {
      enabled: !!user
    })
  
  RENDER:
    <Card>
      <CardHeader>
        <div className="flex items-center space-x-4">
          <Avatar className="h-16 w-16">
            <AvatarImage src={user.user_metadata?.avatar_url} />
            <AvatarFallback>
              {user.user_metadata?.full_name?.charAt(0) || user.email.charAt(0)}
            </AvatarFallback>
          </Avatar>
          
          <div>
            <h3 className="text-lg font-semibold">
              {user.user_metadata?.full_name || 'User'}
            </h3>
            <p className="text-sm text-muted-foreground">{user.email}</p>
            <Badge variant="secondary" className="mt-1">
              {user.email_confirmed_at ? 'Verified' : 'Unverified'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-6">
        <div>
          <h4 className="font-medium mb-3">Usage Statistics</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">
                {userStats.data?.summaryCount || 0}
              </div>
              <div className="text-sm text-muted-foreground">
                Videos Analyzed
              </div>
            </div>
            
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">
                {tokenUsage.data?.totalTokens || 0}
              </div>
              <div className="text-sm text-muted-foreground">
                Total Tokens Used
              </div>
            </div>
          </div>
        </div>
        
        <div className="space-y-2">
          <Button
            variant="outline"
            onClick={onEditProfile}
            className="w-full"
          >
            <User className="mr-2 h-4 w-4" />
            Edit Profile
          </Button>
          
          <Button
            variant="outline"
            onClick={onChangePassword}
            className="w-full"
          >
            <Lock className="mr-2 h-4 w-4" />
            Change Password
          </Button>
        </div>
      </CardContent>
    </Card>

COMPONENT GuestLimitDisplay:
  PROPS:
    guestCount: number
    maxAnalyses: number
    onSignUp: () => void
  
  COMPUTED:
    remaining = maxAnalyses - guestCount
    percentage = (guestCount / maxAnalyses) * 100
  
  RENDER:
    <Card className="border-orange-200 bg-orange-50 dark:border-orange-800 dark:bg-orange-950">
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Gift className="h-5 w-5" />
          <span>Guest Access</span>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span>Free analyses used</span>
            <span>{guestCount} / {maxAnalyses}</span>
          </div>
          
          <Progress value={percentage} className="h-2" />
        </div>
        
        {remaining > 0 ? (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              You have {remaining} free analysis{remaining !== 1 ? 'es' : ''} remaining.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              You've used all your free analyses. Sign up to continue!
            </AlertDescription>
          </Alert>
        )}
        
        <Button onClick={onSignUp} className="w-full">
          <UserPlus className="mr-2 h-4 w-4" />
          Create Free Account
        </Button>
      </CardContent>
    </Card>
```

## Authentication Guards

### ProtectedRoute Component
```typescript
// Pseudocode: Route protection component
COMPONENT ProtectedRoute:
  PROPS:
    children: ReactNode
    requireAuth?: boolean = false
    allowGuest?: boolean = true
    guestLimit?: boolean = false
  
  HOOKS:
    { user, isLoading, guestAnalysisCount, checkGuestLimits } = useAuth()
    router = useRouter()
  
  EFFECTS:
    useEffect(() => {
      IF NOT isLoading:
        IF requireAuth AND NOT user:
          router.push('/login')
        ELSE IF guestLimit AND NOT user AND NOT checkGuestLimits():
          router.push('/signup')
    }, [user, isLoading, requireAuth, guestLimit])
  
  RENDER:
    IF isLoading:
      RETURN <PageLoader />
    
    IF requireAuth AND NOT user:
      RETURN <LoginPrompt />
    
    IF guestLimit AND NOT user AND NOT checkGuestLimits():
      RETURN <GuestLimitReached />
    
    RETURN children

COMPONENT LoginPrompt:
  RENDER:
    <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
      <Lock className="h-12 w-12 text-muted-foreground" />
      <h2 className="text-xl font-semibold">Authentication Required</h2>
      <p className="text-muted-foreground text-center max-w-md">
        Please sign in to access this feature and save your analysis history.
      </p>
      <Button onClick={() => router.push('/login')}>
        Sign In
      </Button>
    </div>

COMPONENT GuestLimitReached:
  RENDER:
    <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
      <AlertTriangle className="h-12 w-12 text-orange-500" />
      <h2 className="text-xl font-semibold">Free Limit Reached</h2>
      <p className="text-muted-foreground text-center max-w-md">
        You've used all your free analyses. Create an account to continue analyzing videos.
      </p>
      <Button onClick={() => router.push('/signup')}>
        Create Free Account
      </Button>
    </div>
```

This authentication specification provides comprehensive user authentication with Supabase integration, guest access management, and secure session handling while maintaining a smooth user experience.