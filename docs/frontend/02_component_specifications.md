# Next.js Component Specifications

## Overview

This specification defines the detailed component architecture for the Next.js frontend, providing comprehensive pseudocode for all major UI components that replicate Streamlit functionality.

## Layout Components

### AppLayout Component
```typescript
// Pseudocode: Main application layout
COMPONENT AppLayout:
  PROPS:
    children: ReactNode
  
  STATE:
    sidebarOpen: boolean = useUIStore(state => state.sidebarOpen)
    theme: string = useTheme()
    user: User | null = useAuthStore(state => state.user)
  
  RENDER:
    <div className="min-h-screen bg-background">
      <Header 
        user={user}
        onToggleSidebar={() => toggleSidebar()}
        onThemeToggle={() => toggleTheme()}
      />
      
      <div className="flex">
        <Sidebar 
          isOpen={sidebarOpen}
          user={user}
          onClose={() => setSidebarOpen(false)}
        />
        
        <main className={cn(
          "flex-1 transition-all duration-300",
          sidebarOpen ? "ml-64" : "ml-0"
        )}>
          <ErrorBoundary fallback={<ErrorFallback />}>
            <Suspense fallback={<PageLoader />}>
              {children}
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
      
      <NotificationContainer />
    </div>

COMPONENT Header:
  PROPS:
    user: User | null
    onToggleSidebar: () => void
    onThemeToggle: () => void
  
  RENDER:
    <header className="border-b bg-background/95 backdrop-blur">
      <div className="flex h-16 items-center px-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
        >
          <Menu className="h-5 w-5" />
        </Button>
        
        <div className="flex items-center space-x-2 ml-4">
          <Image
            src="/logo.png"
            alt="Skimr Logo"
            width={32}
            height={32}
          />
          <h1 className="text-xl font-semibold">
            {ENV.NEXT_PUBLIC_APP_NAME}
          </h1>
        </div>
        
        <div className="ml-auto flex items-center space-x-4">
          <ThemeToggle onClick={onThemeToggle} />
          <UserMenu user={user} />
        </div>
      </div>
    </header>

COMPONENT Sidebar:
  PROPS:
    isOpen: boolean
    user: User | null
    onClose: () => void
  
  STATE:
    settings: Settings = useSettingsStore()
    userStats: UserStats = useQuery(['userStats'], getUserStats)
    guestCount: number = useAuthStore(state => state.guestAnalysisCount)
  
  RENDER:
    <aside className={cn(
      "fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 border-r bg-background/95 backdrop-blur transition-transform duration-300 z-40",
      isOpen ? "translate-x-0" : "-translate-x-full"
    )}>
      <div className="flex flex-col h-full p-4 space-y-6">
        <UserAccountSection 
          user={user}
          stats={userStats}
          guestCount={guestCount}
        />
        
        <Separator />
        
        <SettingsSection 
          settings={settings}
          onSettingsChange={updateSettings}
        />
        
        <Separator />
        
        <AnalysisControlsSection />
        
        <div className="mt-auto">
          <AppVersionInfo />
        </div>
      </div>
    </aside>
```

## Video Analysis Components

### VideoInput Component
```typescript
// Pseudocode: Video URL input and validation
COMPONENT VideoInput:
  PROPS:
    onAnalyze: (url: string, options: AnalysisOptions) => void
    isAnalyzing: boolean
  
  STATE:
    url: string = ''
    errors: Record<string, string> = {}
    analysisTypes: string[] = ['Summary & Classification']
  
  VALIDATION:
    SCHEMA VideoInputSchema = z.object({
      url: z.string()
        .url('Please enter a valid URL')
        .refine(isYouTubeUrl, 'Please enter a valid YouTube URL'),
      analysisTypes: z.array(z.string()).min(1, 'Select at least one analysis type')
    })
  
  METHODS:
    FUNCTION handleSubmit(data: VideoInputData):
      TRY:
        validatedData = VideoInputSchema.parse(data)
        onAnalyze(validatedData.url, {
          analysisTypes: validatedData.analysisTypes,
          useCache: settings.useCache,
          modelName: settings.modelName,
          temperature: settings.temperature
        })
      CATCH ValidationError as error:
        setErrors(error.fieldErrors)
  
  RENDER:
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>Analyze YouTube Video</CardTitle>
        <CardDescription>
          Enter a YouTube URL to get AI-powered analysis
        </CardDescription>
      </CardHeader>
      
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="url">YouTube URL</Label>
            <Input
              id="url"
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              error={errors.url}
            />
          </div>
          
          <div>
            <Label>Analysis Types</Label>
            <AnalysisTypeSelector
              selected={analysisTypes}
              onChange={setAnalysisTypes}
              error={errors.analysisTypes}
            />
          </div>
          
          <Button 
            type="submit" 
            disabled={isAnalyzing}
            className="w-full"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              'Analyze Video'
            )}
          </Button>
        </form>
      </CardContent>
    </Card>

COMPONENT AnalysisTypeSelector:
  PROPS:
    selected: string[]
    onChange: (types: string[]) => void
    error?: string
  
  CONSTANTS:
    ANALYSIS_TYPES = [
      { id: 'summary', label: 'Summary & Classification', default: true },
      { id: 'action_plan', label: 'Action Plan', default: false },
      { id: 'blog_post', label: 'Blog Post', default: false },
      { id: 'linkedin_post', label: 'LinkedIn Post', default: false },
      { id: 'tweet', label: 'X Tweet', default: false }
    ]
  
  RENDER:
    <div className="space-y-2">
      {ANALYSIS_TYPES.map(type => (
        <div key={type.id} className="flex items-center space-x-2">
          <Checkbox
            id={type.id}
            checked={selected.includes(type.id)}
            onCheckedChange={(checked) => {
              IF checked:
                onChange([...selected, type.id])
              ELSE:
                onChange(selected.filter(t => t !== type.id))
            }}
          />
          <Label htmlFor={type.id}>{type.label}</Label>
        </div>
      ))}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
```

### VideoPlayer Component
```typescript
// Pseudocode: YouTube video player with custom subtitles
COMPONENT VideoPlayer:
  PROPS:
    videoId: string
    subtitles?: SubtitleData
    showCustomPlayer: boolean
    onPlayerModeChange: (useCustom: boolean) => void
  
  STATE:
    playerReady: boolean = false
    currentTime: number = 0
    duration: number = 0
  
  EFFECTS:
    useEffect(() => {
      IF showCustomPlayer AND subtitles:
        initializeCustomPlayer()
      ELSE:
        initializeStandardPlayer()
    }, [videoId, showCustomPlayer, subtitles])
  
  METHODS:
    FUNCTION initializeCustomPlayer():
      // Initialize Plyr.js with custom subtitle tracks
      playerConfig = {
        source: {
          type: 'video',
          sources: [{
            src: `https://www.youtube.com/watch?v=${videoId}`,
            provider: 'youtube'
          }],
          tracks: Object.entries(subtitles).map(([lang, data]) => ({
            kind: 'captions',
            label: getLanguageName(lang),
            srclang: lang,
            src: createSubtitleBlobUrl(data.content),
            default: data.default
          }))
        },
        captions: { active: true, update: true }
      }
      
      player = new Plyr('#custom-player', playerConfig)
      setPlayerReady(true)
    
    FUNCTION initializeStandardPlayer():
      // Standard YouTube embed
      setPlayerReady(true)
  
  RENDER:
    <div className="space-y-4">
      <div className="aspect-video bg-muted rounded-lg overflow-hidden">
        {showCustomPlayer && subtitles ? (
          <div id="custom-player" className="w-full h-full" />
        ) : (
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            className="w-full h-full"
            allowFullScreen
          />
        )}
      </div>
      
      {subtitles && (
        <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
          <div className="flex items-center space-x-2">
            <Subtitles className="h-4 w-4" />
            <span className="text-sm">
              Subtitles available in: {getAvailableLanguages(subtitles)}
            </span>
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPlayerModeChange(!showCustomPlayer)}
          >
            {showCustomPlayer ? 'Standard Player' : 'Custom Player'}
          </Button>
        </div>
      )}
    </div>
```

### AnalysisResults Component
```typescript
// Pseudocode: Tabbed analysis results display
COMPONENT AnalysisResults:
  PROPS:
    results: AnalysisResult
    onRegenerateContent: (contentType: string, instruction?: string) => void
    isGenerating: Record<string, boolean>
  
  STATE:
    activeTab: string = 'summary'
    customInstructions: Record<string, string> = {}
  
  CONSTANTS:
    TAB_CONFIG = [
      { id: 'summary', label: '📊 Summary', taskKey: 'classify_and_summarize_content' },
      { id: 'action_plan', label: '📋 Action Plan', taskKey: 'analyze_and_plan_content' },
      { id: 'blog_post', label: '📝 Blog Post', taskKey: 'write_blog_post' },
      { id: 'linkedin_post', label: '💼 LinkedIn Post', taskKey: 'write_linkedin_post' },
      { id: 'tweet', label: '🐦 X Tweet', taskKey: 'write_tweet' },
      { id: 'transcript', label: '📜 Transcript', taskKey: 'transcript' }
    ]
  
  RENDER:
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Analysis Results</CardTitle>
      </CardHeader>
      
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-6">
            {TAB_CONFIG.map(tab => (
              <TabsTrigger key={tab.id} value={tab.id}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
          
          {TAB_CONFIG.map(tab => (
            <TabsContent key={tab.id} value={tab.id} className="mt-6">
              {tab.id === 'transcript' ? (
                <TranscriptTab 
                  transcript={results.transcript}
                  segments={results.transcriptSegments}
                  videoId={results.videoId}
                />
              ) : (
                <ContentTab
                  content={results.taskOutputs[tab.taskKey]}
                  contentType={tab.id}
                  taskKey={tab.taskKey}
                  customInstruction={customInstructions[tab.taskKey]}
                  onInstructionChange={(instruction) => 
                    setCustomInstructions(prev => ({
                      ...prev,
                      [tab.taskKey]: instruction
                    }))
                  }
                  onRegenerate={() => 
                    onRegenerateContent(tab.taskKey, customInstructions[tab.taskKey])
                  }
                  isGenerating={isGenerating[tab.taskKey]}
                  canRegenerate={tab.id !== 'summary'}
                />
              )}
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>

COMPONENT ContentTab:
  PROPS:
    content: string | null
    contentType: string
    taskKey: string
    customInstruction: string
    onInstructionChange: (instruction: string) => void
    onRegenerate: () => void
    isGenerating: boolean
    canRegenerate: boolean
  
  RENDER:
    <div className="space-y-6">
      {content ? (
        <>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{cleanMarkdownFences(content)}</ReactMarkdown>
          </div>
          
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="outline" size="sm">
                <FileText className="mr-2 h-4 w-4" />
                View Raw Markdown
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <pre className="mt-2 p-4 bg-muted rounded-lg text-sm overflow-x-auto">
                <code>{content}</code>
              </pre>
            </CollapsibleContent>
          </Collapsible>
          
          {canRegenerate && (
            <RegenerateSection
              instruction={customInstruction}
              onInstructionChange={onInstructionChange}
              onRegenerate={onRegenerate}
              isGenerating={isGenerating}
              contentType={contentType}
            />
          )}
        </>
      ) : (
        <ContentPlaceholder
          contentType={contentType}
          instruction={customInstruction}
          onInstructionChange={onInstructionChange}
          onGenerate={onRegenerate}
          isGenerating={isGenerating}
        />
      )}
    </div>

COMPONENT RegenerateSection:
  PROPS:
    instruction: string
    onInstructionChange: (instruction: string) => void
    onRegenerate: () => void
    isGenerating: boolean
    contentType: string
  
  RENDER:
    <div className="border-t pt-6 space-y-4">
      <h4 className="font-medium">Regenerate with Custom Instructions</h4>
      
      <Textarea
        placeholder={`Example: Focus more on technical aspects, or Add more actionable steps...`}
        value={instruction}
        onChange={(e) => onInstructionChange(e.target.value)}
        rows={3}
      />
      
      <Button 
        onClick={onRegenerate}
        disabled={isGenerating}
        size="sm"
      >
        {isGenerating ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Regenerating...
          </>
        ) : (
          <>
            <RefreshCw className="mr-2 h-4 w-4" />
            Regenerate {contentType}
          </>
        )}
      </Button>
    </div>
```

This component specification provides detailed pseudocode for the core UI components, maintaining feature parity with the Streamlit application while leveraging modern React patterns and TypeScript for type safety.