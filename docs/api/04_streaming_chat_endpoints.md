# Streaming Chat Endpoints Specification

## Overview

Real-time chat endpoints that integrate with the existing [`WebAppAdapter.get_chat_response_stream`](../../../src/youtube_analysis/adapters/webapp_adapter.py:150) method to provide WebSocket and Server-Sent Events (SSE) streaming for interactive video discussions.

## Chat Router

### Base Configuration
```python
# Pseudocode: Chat router setup
router = APIRouter(prefix="/api/v1/video/chat", tags=["chat"])
websocket_router = APIRouter()
```

## Data Models

### Request Models
```python
# Pseudocode: Chat request models
CLASS ChatMessage(BaseModel):
    PROPERTY message: str = Field(..., min_length=1, max_length=2000, description="User message")
    PROPERTY video_id: str = Field(..., description="Video ID for context")
    PROPERTY session_id: Optional[str] = Field(default=None, description="Chat session ID")
    PROPERTY model_name: Optional[str] = Field(default=None, description="LLM model to use")
    PROPERTY temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Generation temperature")
    PROPERTY use_context: bool = Field(default=True, description="Whether to use video context")

CLASS ChatSessionRequest(BaseModel):
    PROPERTY video_id: str = Field(..., description="Video ID")
    PROPERTY session_name: Optional[str] = Field(default=None, description="Custom session name")

CLASS ChatHistoryRequest(BaseModel):
    PROPERTY session_id: str = Field(..., description="Chat session ID")
    PROPERTY limit: int = Field(default=50, ge=1, le=100, description="Number of messages to retrieve")
    PROPERTY offset: int = Field(default=0, ge=0, description="Offset for pagination")
```

### Response Models
```python
# Pseudocode: Chat response models
CLASS ChatMessageResponse(BaseModel):
    PROPERTY message_id: str
    PROPERTY content: str
    PROPERTY role: str  # "user" or "assistant"
    PROPERTY timestamp: datetime
    PROPERTY token_usage: Optional[Dict[str, int]]

CLASS ChatSessionResponse(BaseModel):
    PROPERTY session_id: str
    PROPERTY video_id: str
    PROPERTY session_name: str
    PROPERTY created_at: datetime
    PROPERTY message_count: int
    PROPERTY last_activity: datetime

CLASS StreamingChatChunk(BaseModel):
    PROPERTY chunk_id: str
    PROPERTY content: str
    PROPERTY is_final: bool
    PROPERTY token_usage: Optional[Dict[str, int]]
    PROPERTY error: Optional[str]

CLASS ChatHistoryResponse(BaseModel):
    PROPERTY session_id: str
    PROPERTY messages: List[ChatMessageResponse]
    PROPERTY total_count: int
    PROPERTY has_more: bool
```

## WebSocket Chat Endpoint

### WebSocket Connection Handler
```python
# Pseudocode: WebSocket chat endpoint
@websocket_router.websocket("/api/v1/video/chat/ws")
ASYNC FUNCTION websocket_chat_endpoint(
    websocket: WebSocket,
    video_id: str = Query(..., description="Video ID"),
    session_id: Optional[str] = Query(default=None, description="Chat session ID"),
    token: Optional[str] = Query(default=None, description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time chat streaming.
    
    Integrates with WebAppAdapter.get_chat_response_stream method.
    """
    
    # Accept WebSocket connection
    AWAIT websocket.accept()
    
    TRY:
        # Authenticate user (optional for guest access)
        current_user = None
        IF token:
            current_user = AWAIT authenticate_websocket_user(token)
        
        # Initialize chat session
        chat_service = get_chat_service()
        IF NOT session_id:
            session_id = AWAIT chat_service.create_session(video_id, current_user)
        
        # Get video context for chat
        webapp_adapter = get_webapp_adapter()
        video_context = AWAIT webapp_adapter.get_video_context(video_id)
        
        IF NOT video_context:
            AWAIT websocket.send_json({
                "error": "Video context not found. Please analyze the video first.",
                "type": "error"
            })
            AWAIT websocket.close(code=4004)
            RETURN
        
        logger.info(f"WebSocket chat session started: {session_id} for video {video_id}")
        
        # Send session confirmation
        AWAIT websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "video_id": video_id
        })
        
        # Message handling loop
        WHILE True:
            # Receive message from client
            data = AWAIT websocket.receive_json()
            
            IF data.get("type") == "chat_message":
                AWAIT handle_chat_message(
                    websocket=websocket,
                    message_data=data,
                    session_id=session_id,
                    video_id=video_id,
                    video_context=video_context,
                    current_user=current_user,
                    webapp_adapter=webapp_adapter
                )
            
            ELIF data.get("type") == "ping":
                AWAIT websocket.send_json({"type": "pong"})
            
            ELSE:
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": "Unknown message type"
                })
    
    EXCEPT WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    EXCEPT Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        TRY:
            AWAIT websocket.send_json({
                "type": "error",
                "error": "Internal server error"
            })
            AWAIT websocket.close(code=1011)
        EXCEPT:
            PASS

ASYNC FUNCTION handle_chat_message(
    websocket: WebSocket,
    message_data: Dict[str, Any],
    session_id: str,
    video_id: str,
    video_context: Dict[str, Any],
    current_user: Optional[UserProfile],
    webapp_adapter: WebAppAdapter
):
    """Handle individual chat message with streaming response."""
    
    TRY:
        message = message_data.get("message", "").strip()
        IF NOT message:
            AWAIT websocket.send_json({
                "type": "error",
                "error": "Message cannot be empty"
            })
            RETURN
        
        # Check rate limiting for guests
        IF current_user IS None:
            rate_limit_key = f"chat_rate_limit:{websocket.client.host}"
            IF NOT check_rate_limit(rate_limit_key, max_requests=10, window_seconds=60):
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": "Rate limit exceeded. Please slow down."
                })
                RETURN
        
        # Prepare chat settings
        settings = {
            "model": message_data.get("model_name") OR ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
            "temperature": message_data.get("temperature") OR float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2)),
            "use_context": message_data.get("use_context", True)
        }
        
        # Save user message
        chat_service = get_chat_service()
        user_message_id = AWAIT chat_service.save_message(
            session_id=session_id,
            content=message,
            role="user",
            user_id=current_user.id IF current_user ELSE None
        )
        
        # Send user message confirmation
        AWAIT websocket.send_json({
            "type": "user_message_saved",
            "message_id": user_message_id,
            "content": message
        })
        
        # Start streaming response
        AWAIT websocket.send_json({
            "type": "assistant_response_start"
        })
        
        # Get streaming response from WebAppAdapter
        response_content = ""
        total_token_usage = None
        
        ASYNC FOR chunk IN webapp_adapter.get_chat_response_stream(
            message=message,
            video_id=video_id,
            session_id=session_id,
            video_context=video_context,
            settings=settings
        ):
            IF chunk.get("error"):
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": chunk["error"]
                })
                RETURN
            
            IF chunk.get("content"):
                response_content += chunk["content"]
                AWAIT websocket.send_json({
                    "type": "assistant_response_chunk",
                    "content": chunk["content"],
                    "is_final": False
                })
            
            IF chunk.get("token_usage"):
                total_token_usage = chunk["token_usage"]
        
        # Save assistant response
        assistant_message_id = AWAIT chat_service.save_message(
            session_id=session_id,
            content=response_content,
            role="assistant",
            token_usage=total_token_usage
        )
        
        # Send final response
        AWAIT websocket.send_json({
            "type": "assistant_response_complete",
            "message_id": assistant_message_id,
            "content": response_content,
            "token_usage": total_token_usage
        })
        
        logger.info(f"Chat message processed for session {session_id}")
        
    EXCEPT Exception as e:
        logger.error(f"Error handling chat message: {str(e)}", exc_info=True)
        AWAIT websocket.send_json({
            "type": "error",
            "error": "Failed to process message"
        })
```

## REST Chat Endpoints

### POST /api/v1/video/chat/sessions
```python
# Pseudocode: Create chat session endpoint
@router.post("/sessions", response_model=SuccessResponse[ChatSessionResponse])
ASYNC FUNCTION create_chat_session(
    request: ChatSessionRequest,
    current_user: Optional[UserProfile] = Depends(get_optional_user)
) -> SuccessResponse[ChatSessionResponse]:
    """Create a new chat session for a video."""
    
    TRY:
        # Verify video exists and has been analyzed
        cache_repo = get_cache_repository()
        analysis_result = AWAIT cache_repo.get_analysis_result(request.video_id)
        
        IF NOT analysis_result:
            RAISE NotFoundError("Video analysis not found. Please analyze the video first.")
        
        # Create chat session
        chat_service = get_chat_service()
        session = AWAIT chat_service.create_session(
            video_id=request.video_id,
            user=current_user,
            session_name=request.session_name
        )
        
        response = ChatSessionResponse(
            session_id=session.session_id,
            video_id=session.video_id,
            session_name=session.session_name,
            created_at=session.created_at,
            message_count=0,
            last_activity=session.created_at
        )
        
        logger.info(f"Chat session created: {session.session_id}")
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT NotFoundError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error creating chat session: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to create chat session")
```

### GET /api/v1/video/chat/sessions/{session_id}/history
```python
# Pseudocode: Get chat history endpoint
@router.get("/sessions/{session_id}/history", response_model=SuccessResponse[ChatHistoryResponse])
ASYNC FUNCTION get_chat_history(
    session_id: str = Path(..., description="Chat session ID"),
    limit: int = Query(50, ge=1, le=100, description="Number of messages"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Optional[UserProfile] = Depends(get_optional_user)
) -> SuccessResponse[ChatHistoryResponse]:
    """Get chat history for a session."""
    
    TRY:
        chat_service = get_chat_service()
        
        # Verify session access
        session = AWAIT chat_service.get_session(session_id)
        IF NOT session:
            RAISE NotFoundError("Chat session not found")
        
        # For authenticated users, verify ownership
        IF current_user AND session.user_id != current_user.id:
            RAISE ForbiddenError("Access denied to this chat session")
        
        # Get messages
        messages, total_count = AWAIT chat_service.get_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        # Transform to response format
        message_responses = [
            ChatMessageResponse(
                message_id=msg.message_id,
                content=msg.content,
                role=msg.role,
                timestamp=msg.timestamp,
                token_usage=msg.token_usage
            )
            FOR msg IN messages
        ]
        
        response = ChatHistoryResponse(
            session_id=session_id,
            messages=message_responses,
            total_count=total_count,
            has_more=(offset + len(messages)) < total_count
        )
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT NotFoundError:
        RAISE
    EXCEPT ForbiddenError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error getting chat history: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve chat history")
```

### GET /api/v1/video/chat/sessions
```python
# Pseudocode: List user chat sessions
@router.get("/sessions", response_model=SuccessResponse[List[ChatSessionResponse]])
ASYNC FUNCTION list_chat_sessions(
    video_id: Optional[str] = Query(default=None, description="Filter by video ID"),
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[List[ChatSessionResponse]]:
    """List chat sessions for the authenticated user."""
    
    TRY:
        chat_service = get_chat_service()
        sessions = AWAIT chat_service.get_user_sessions(
            user_id=current_user.id,
            video_id=video_id
        )
        
        session_responses = [
            ChatSessionResponse(
                session_id=session.session_id,
                video_id=session.video_id,
                session_name=session.session_name,
                created_at=session.created_at,
                message_count=session.message_count,
                last_activity=session.last_activity
            )
            FOR session IN sessions
        ]
        
        RETURN SuccessResponse(data=session_responses)
        
    EXCEPT Exception as e:
        logger.error(f"Error listing chat sessions: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve chat sessions")
```

## Utility Functions

### WebSocket Authentication
```python
# Pseudocode: WebSocket authentication helper
ASYNC FUNCTION authenticate_websocket_user(token: str) -> Optional[UserProfile]:
    """Authenticate user from WebSocket token."""
    TRY:
        auth_service = get_auth_service()
        user = AWAIT auth_service.verify_token(token)
        RETURN user
    EXCEPT Exception:
        RETURN None
```

### Rate Limiting
```python
# Pseudocode: Simple in-memory rate limiting
rate_limit_store = {}

FUNCTION check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Check if request is within rate limit."""
    now = time.time()
    window_start = now - window_seconds
    
    # Clean old entries
    IF key IN rate_limit_store:
        rate_limit_store[key] = [
            timestamp FOR timestamp IN rate_limit_store[key]
            IF timestamp > window_start
        ]
    ELSE:
        rate_limit_store[key] = []
    
    # Check limit
    IF len(rate_limit_store[key]) >= max_requests:
        RETURN False
    
    # Add current request
    rate_limit_store[key].append(now)
    RETURN True
```

## TDD Test Anchors

### WebSocket Tests
```python
# Test anchor: WebSocket connection and chat
TEST test_websocket_chat_flow():
    WITH TestClient(app) AS client:
        WITH client.websocket_connect("/api/v1/video/chat/ws?video_id=test_video") AS websocket:
            # Receive session start confirmation
            data = websocket.receive_json()
            ASSERT data["type"] == "session_started"
            session_id = data["session_id"]
            
            # Send chat message
            websocket.send_json({
                "type": "chat_message",
                "message": "What is this video about?"
            })
            
            # Receive user message confirmation
            data = websocket.receive_json()
            ASSERT data["type"] == "user_message_saved"
            
            # Receive assistant response start
            data = websocket.receive_json()
            ASSERT data["type"] == "assistant_response_start"
            
            # Receive response chunks
            response_content = ""
            WHILE True:
                data = websocket.receive_json()
                IF data["type"] == "assistant_response_chunk":
                    response_content += data["content"]
                ELIF data["type"] == "assistant_response_complete":
                    BREAK
            
            ASSERT len(response_content) > 0

# Test anchor: WebSocket authentication
TEST test_websocket_with_auth():
    WITH TestClient(app) AS client:
        # Get auth token
        auth_response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        token = auth_response.json()["data"]["access_token"]
        
        WITH client.websocket_connect(f"/api/v1/video/chat/ws?video_id=test_video&token={token}") AS websocket:
            data = websocket.receive_json()
            ASSERT data["type"] == "session_started"

# Test anchor: Chat session creation
TEST test_create_chat_session():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/video/chat/sessions", json={
            "video_id": "test_video_id"
        })
        ASSERT response.status_code == 200
        ASSERT "session_id" IN response.json()["data"]

# Test anchor: Chat history retrieval
TEST test_get_chat_history():
    WITH TestClient(app) AS client:
        # Create session first
        session_response = client.post("/api/v1/video/chat/sessions", json={
            "video_id": "test_video_id"
        })
        session_id = session_response.json()["data"]["session_id"]
        
        # Get history
        response = client.get(f"/api/v1/video/chat/sessions/{session_id}/history")
        ASSERT response.status_code == 200
        ASSERT "messages" IN response.json()["data"]

# Test anchor: Rate limiting
TEST test_websocket_rate_limiting():
    WITH TestClient(app) AS client:
        WITH client.websocket_connect("/api/v1/video/chat/ws?video_id=test_video") AS websocket:
            # Send multiple messages rapidly
            FOR i IN range(15):  # Exceed rate limit
                websocket.send_json({
                    "type": "chat_message",
                    "message": f"Message {i}"
                })
                
                data = websocket.receive_json()
                IF i >= 10:  # Should hit rate limit
                    ASSERT data.get("type") == "error"
                    ASSERT "rate limit" IN data.get("error", "").lower()
                    BREAK
```

This specification provides comprehensive streaming chat functionality that integrates with the existing WebAppAdapter while offering both WebSocket and REST interfaces for flexible frontend integration.