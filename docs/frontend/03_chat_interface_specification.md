# Chat Interface Specification

## Overview

This specification defines the real-time chat interface components that provide interactive video discussion capabilities with WebSocket streaming, maintaining feature parity with the Streamlit chat implementation.

## Chat Components Architecture

### ChatInterface Component
```typescript
// Pseudocode: Main chat interface container
COMPONENT ChatInterface:
  PROPS:
    videoId: string
    analysisResults: AnalysisResult
    onMessageSent: (message: string) => void
    onChatReset: () => void
  
  STATE:
    sessionId: string | null = null
    messages: ChatMessage[] = []
    isConnected: boolean = false
    isStreaming: boolean = false
    connectionError: string | null = null
  
  HOOKS:
    chatSession = useQuery(['chatSession', videoId], () => 
      createChatSession(videoId)
    )
    
    webSocket = useWebSocket({
      url: `${ENV.NEXT_PUBLIC_WS_URL}/chat/${sessionId}`,
      onMessage: handleWebSocketMessage,
      onError: handleWebSocketError,
      onConnect: () => setIsConnected(true),
      onDisconnect: () => setIsConnected(false)
    })
  
  EFFECTS:
    useEffect(() => {
      IF chatSession.data?.sessionId:
        setSessionId(chatSession.data.sessionId)
        loadChatHistory(chatSession.data.sessionId)
    }, [chatSession.data])
  
  METHODS:
    FUNCTION handleWebSocketMessage(event: MessageEvent):
      data = JSON.parse(event.data)
      
      SWITCH data.type:
        CASE 'message_start':
          setIsStreaming(true)
          addMessage({
            id: data.messageId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isStreaming: true
          })
        
        CASE 'message_chunk':
          updateStreamingMessage(data.messageId, data.chunk)
        
        CASE 'message_complete':
          completeStreamingMessage(data.messageId, data.tokenUsage)
          setIsStreaming(false)
        
        CASE 'error':
          handleChatError(data.error)
          setIsStreaming(false)
    
    FUNCTION handleSendMessage(content: string):
      IF NOT isConnected OR isStreaming:
        RETURN
      
      userMessage = {
        id: generateId(),
        role: 'user',
        content,
        timestamp: new Date()
      }
      
      addMessage(userMessage)
      
      webSocket.send(JSON.stringify({
        type: 'chat_message',
        message: content,
        sessionId,
        videoId,
        settings: getCurrentSettings()
      }))
      
      onMessageSent(content)
    
    FUNCTION handleResetChat():
      setMessages([])
      IF sessionId:
        webSocket.send(JSON.stringify({
          type: 'reset_session',
          sessionId
        }))
      onChatReset()
  
  RENDER:
    <Card className="h-full flex flex-col">
      <CardHeader className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <MessageCircle className="h-5 w-5" />
            <span>Chat with Video</span>
          </CardTitle>
          
          <div className="flex items-center space-x-2">
            <ConnectionStatus isConnected={isConnected} />
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetChat}
              disabled={isStreaming}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {connectionError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{connectionError}</AlertDescription>
          </Alert>
        )}
      </CardHeader>
      
      <CardContent className="flex-1 flex flex-col min-h-0">
        <MessageList 
          messages={messages}
          isStreaming={isStreaming}
          className="flex-1"
        />
        
        <MessageInput
          onSendMessage={handleSendMessage}
          disabled={!isConnected || isStreaming}
          placeholder="Ask questions about the video..."
        />
      </CardContent>
    </Card>

COMPONENT ConnectionStatus:
  PROPS:
    isConnected: boolean
  
  RENDER:
    <div className="flex items-center space-x-1">
      <div className={cn(
        "w-2 h-2 rounded-full",
        isConnected ? "bg-green-500" : "bg-red-500"
      )} />
      <span className="text-xs text-muted-foreground">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
```

### MessageList Component
```typescript
// Pseudocode: Chat message list with auto-scroll
COMPONENT MessageList:
  PROPS:
    messages: ChatMessage[]
    isStreaming: boolean
    className?: string
  
  STATE:
    autoScroll: boolean = true
    messagesEndRef: RefObject<HTMLDivElement> = useRef(null)
  
  EFFECTS:
    useEffect(() => {
      IF autoScroll:
        scrollToBottom()
    }, [messages, isStreaming])
    
    useEffect(() => {
      // Check if user has scrolled up
      FUNCTION handleScroll():
        container = messagesEndRef.current?.parentElement
        IF container:
          isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 100
          setAutoScroll(isAtBottom)
      
      container?.addEventListener('scroll', handleScroll)
      RETURN () => container?.removeEventListener('scroll', handleScroll)
    }, [])
  
  METHODS:
    FUNCTION scrollToBottom():
      messagesEndRef.current?.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      })
    
    FUNCTION formatTimestamp(timestamp: Date): string:
      RETURN timestamp.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      })
  
  RENDER:
    <div className={cn(
      "flex-1 overflow-y-auto space-y-4 p-4",
      className
    )}>
      {messages.length === 0 ? (
        <EmptyState />
      ) : (
        messages.map(message => (
          <MessageBubble
            key={message.id}
            message={message}
            isStreaming={message.isStreaming}
          />
        ))
      )}
      
      {isStreaming && <TypingIndicator />}
      
      <div ref={messagesEndRef} />
      
      {!autoScroll && (
        <Button
          variant="outline"
          size="sm"
          className="fixed bottom-20 right-4"
          onClick={scrollToBottom}
        >
          <ChevronDown className="h-4 w-4" />
        </Button>
      )}
    </div>

COMPONENT EmptyState:
  RENDER:
    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
      <MessageCircle className="h-12 w-12 text-muted-foreground" />
      <div>
        <h3 className="font-medium">Start a conversation</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Ask questions about the video content, request summaries, or discuss key points.
        </p>
      </div>
      
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">Try asking:</p>
        <div className="space-y-1">
          {SUGGESTED_QUESTIONS.map(question => (
            <Badge key={question} variant="secondary" className="text-xs">
              {question}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  
  CONSTANTS:
    SUGGESTED_QUESTIONS = [
      "What are the main points?",
      "Summarize the key takeaways",
      "What actions should I take?",
      "Explain this concept further"
    ]
```

### MessageBubble Component
```typescript
// Pseudocode: Individual chat message display
COMPONENT MessageBubble:
  PROPS:
    message: ChatMessage
    isStreaming?: boolean
  
  STATE:
    showRawContent: boolean = false
    copied: boolean = false
  
  METHODS:
    FUNCTION handleCopyMessage():
      navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    
    FUNCTION formatContent(content: string): string:
      // Clean markdown fences and format content
      RETURN cleanMarkdownFences(content)
  
  RENDER:
    <div className={cn(
      "flex w-full",
      message.role === 'user' ? "justify-end" : "justify-start"
    )}>
      <div className={cn(
        "max-w-[80%] rounded-lg px-4 py-2 space-y-2",
        message.role === 'user' 
          ? "bg-primary text-primary-foreground ml-12"
          : "bg-muted mr-12"
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {message.role === 'user' ? (
              <User className="h-4 w-4" />
            ) : (
              <Bot className="h-4 w-4" />
            )}
            <span className="text-sm font-medium">
              {message.role === 'user' ? 'You' : 'AI Assistant'}
            </span>
          </div>
          
          <div className="flex items-center space-x-1">
            <span className="text-xs opacity-70">
              {formatTimestamp(message.timestamp)}
            </span>
            
            {message.role === 'assistant' && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <MoreVertical className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleCopyMessage}>
                    <Copy className="mr-2 h-4 w-4" />
                    {copied ? 'Copied!' : 'Copy'}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setShowRawContent(!showRawContent)}>
                    <FileText className="mr-2 h-4 w-4" />
                    {showRawContent ? 'Hide' : 'Show'} Raw
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
        
        <div className="prose prose-sm max-w-none dark:prose-invert">
          {isStreaming ? (
            <StreamingContent content={message.content} />
          ) : (
            <ReactMarkdown>{formatContent(message.content)}</ReactMarkdown>
          )}
        </div>
        
        {showRawContent && (
          <Collapsible>
            <CollapsibleContent>
              <pre className="text-xs bg-background/50 p-2 rounded border overflow-x-auto">
                <code>{message.content}</code>
              </pre>
            </CollapsibleContent>
          </Collapsible>
        )}
        
        {message.tokenUsage && (
          <div className="text-xs opacity-70 border-t pt-2">
            Tokens: {message.tokenUsage.total} 
            (prompt: {message.tokenUsage.prompt}, completion: {message.tokenUsage.completion})
          </div>
        )}
      </div>
    </div>

COMPONENT StreamingContent:
  PROPS:
    content: string
  
  STATE:
    displayedContent: string = ''
    cursorVisible: boolean = true
  
  EFFECTS:
    useEffect(() => {
      setDisplayedContent(content)
    }, [content])
    
    useEffect(() => {
      // Blinking cursor effect
      interval = setInterval(() => {
        setCursorVisible(prev => !prev)
      }, 500)
      
      RETURN () => clearInterval(interval)
    }, [])
  
  RENDER:
    <div className="relative">
      <ReactMarkdown>{displayedContent}</ReactMarkdown>
      {cursorVisible && (
        <span className="inline-block w-2 h-4 bg-current ml-1 animate-pulse" />
      )}
    </div>

COMPONENT TypingIndicator:
  RENDER:
    <div className="flex items-center space-x-2 text-muted-foreground">
      <Bot className="h-4 w-4" />
      <div className="flex space-x-1">
        <div className="w-2 h-2 bg-current rounded-full animate-bounce" />
        <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
        <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
      </div>
      <span className="text-sm">AI is thinking...</span>
    </div>
```

### MessageInput Component
```typescript
// Pseudocode: Chat message input with send functionality
COMPONENT MessageInput:
  PROPS:
    onSendMessage: (message: string) => void
    disabled?: boolean
    placeholder?: string
  
  STATE:
    message: string = ''
    isComposing: boolean = false
  
  METHODS:
    FUNCTION handleSubmit(e: FormEvent):
      e.preventDefault()
      
      trimmedMessage = message.trim()
      IF trimmedMessage AND NOT disabled:
        onSendMessage(trimmedMessage)
        setMessage('')
    
    FUNCTION handleKeyDown(e: KeyboardEvent):
      IF e.key === 'Enter' AND NOT e.shiftKey AND NOT isComposing:
        e.preventDefault()
        handleSubmit(e)
  
  RENDER:
    <form onSubmit={handleSubmit} className="flex space-x-2 pt-4 border-t">
      <div className="flex-1 relative">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder={placeholder || "Type your message..."}
          disabled={disabled}
          rows={1}
          className="min-h-[40px] max-h-32 resize-none pr-12"
        />
        
        <Button
          type="submit"
          size="icon"
          disabled={disabled || !message.trim()}
          className="absolute right-2 top-1/2 transform -translate-y-1/2 h-8 w-8"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </form>
```

## WebSocket Integration

### useWebSocket Hook
```typescript
// Pseudocode: WebSocket management hook
HOOK useWebSocket:
  PARAMS:
    url: string
    onMessage: (event: MessageEvent) => void
    onError: (error: Event) => void
    onConnect: () => void
    onDisconnect: () => void
    reconnectAttempts: number = 5
    reconnectDelay: number = 1000
  
  STATE:
    socket: WebSocket | null = null
    isConnected: boolean = false
    reconnectCount: number = 0
  
  METHODS:
    FUNCTION connect():
      TRY:
        newSocket = new WebSocket(url)
        
        newSocket.onopen = () => {
          setIsConnected(true)
          setReconnectCount(0)
          onConnect()
        }
        
        newSocket.onmessage = onMessage
        
        newSocket.onerror = (error) => {
          onError(error)
          attemptReconnect()
        }
        
        newSocket.onclose = () => {
          setIsConnected(false)
          onDisconnect()
          attemptReconnect()
        }
        
        setSocket(newSocket)
      CATCH error:
        onError(error)
        attemptReconnect()
    
    FUNCTION attemptReconnect():
      IF reconnectCount < reconnectAttempts:
        setTimeout(() => {
          setReconnectCount(prev => prev + 1)
          connect()
        }, reconnectDelay * Math.pow(2, reconnectCount))
    
    FUNCTION send(data: string):
      IF socket AND socket.readyState === WebSocket.OPEN:
        socket.send(data)
      ELSE:
        throw new Error('WebSocket not connected')
    
    FUNCTION disconnect():
      IF socket:
        socket.close()
        setSocket(null)
        setIsConnected(false)
  
  EFFECTS:
    useEffect(() => {
      connect()
      RETURN () => disconnect()
    }, [url])
  
  RETURN:
    socket: socket,
    isConnected: isConnected,
    send: send,
    disconnect: disconnect
```

This chat interface specification provides comprehensive real-time chat functionality with WebSocket streaming, maintaining feature parity with the Streamlit implementation while leveraging modern React patterns for optimal user experience.