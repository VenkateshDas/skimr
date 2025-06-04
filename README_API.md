# YouTube Analysis FastAPI Backend

A RESTful API backend for YouTube video analysis and content generation, built with FastAPI and integrated with existing Python services.

## Features

- **Video Analysis**: Analyze YouTube videos with multiple analysis types
- **Content Generation**: Generate blog posts, social media content, and more
- **Authentication**: JWT-based authentication with Supabase integration
- **Guest Access**: Limited access for unauthenticated users
- **Real-time Chat**: Chat about analyzed videos
- **Transcript Extraction**: Get video transcripts with timestamps
- **Clean Architecture**: Modular design with separation of concerns

## Project Structure

```
src/youtube_analysis_api/
├── __init__.py                 # Package initialization
├── app.py                      # FastAPI application factory
├── config.py                   # Configuration management
├── dependencies.py             # FastAPI dependencies
├── exceptions.py               # Custom exception classes
├── middleware.py               # Request/response middleware
├── api/                        # API layer
│   ├── __init__.py
│   ├── models/                 # Pydantic models
│   │   ├── __init__.py
│   │   ├── base.py            # Base response models
│   │   ├── auth.py            # Authentication models
│   │   └── video.py           # Video analysis models
│   └── routers/               # API route handlers
│       ├── __init__.py
│       ├── auth.py            # Authentication endpoints
│       ├── health.py          # Health check endpoints
│       └── video_analysis.py  # Video analysis endpoints
├── auth/                      # Authentication utilities
│   ├── __init__.py
│   ├── jwt_utils.py          # JWT token management
│   └── supabase_client.py    # Supabase integration
└── utils/                     # Utility functions
    ├── __init__.py
    └── youtube_utils.py       # YouTube URL validation
```

## Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Configure environment variables**:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_ANON_KEY`: Supabase anonymous key
   - `JWT_SECRET_KEY`: Secret key for JWT tokens
   - `CORS_ORIGINS`: Allowed CORS origins (JSON array)
   - Other configuration as needed

## Running the API

### Development Mode

```bash
# From the project root
python -m src.youtube_analysis_api.app

# Or using uvicorn directly
uvicorn src.youtube_analysis_api.app:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn src.youtube_analysis_api.app:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
- `GET /health` - Basic health check
- `GET /api/v1/health/detailed` - Detailed health status

### Authentication
- `POST /api/v1/auth/login` - Login with Supabase token
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/profile` - Get user profile
- `PUT /api/v1/auth/profile` - Update user profile
- `POST /api/v1/auth/logout` - Logout user

### Video Analysis
- `POST /api/v1/video/analyze` - Analyze YouTube video
- `POST /api/v1/video/generate-content` - Generate content for video
- `POST /api/v1/video/transcript` - Get video transcript
- `POST /api/v1/video/chat` - Chat about analyzed video

## Configuration

The API uses environment-based configuration with the following key settings:

### API Configuration
- `API_HOST`: Server host (default: 0.0.0.0)
- `API_PORT`: Server port (default: 8000)
- `API_DEBUG`: Debug mode (default: false)
- `API_ENVIRONMENT`: Environment name (development/production)

### Authentication
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Access token expiry (default: 30)
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token expiry (default: 7)

### Supabase Integration
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key

### CORS
- `CORS_ORIGINS`: Allowed origins as JSON array

## Authentication Flow

1. **Frontend Authentication**: User authenticates with Supabase
2. **Token Exchange**: Frontend sends Supabase token to `/api/v1/auth/login`
3. **JWT Generation**: API validates Supabase token and returns JWT tokens
4. **API Access**: Frontend uses JWT access token for API requests
5. **Token Refresh**: Use refresh token to get new access tokens

## Guest Access

Unauthenticated users have limited access:
- Daily request limit (configurable via `GUEST_DAILY_LIMIT`)
- Access to video analysis endpoints
- No access to user-specific features

## Integration with Existing Services

The API integrates with existing services through:
- **ServiceFactory**: Dependency injection for service instances
- **WebAppAdapter**: Interface to existing video analysis logic
- **Configuration**: Shared configuration management

## Error Handling

The API provides structured error responses:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message"
  },
  "request_id": "unique-request-id"
}
```

## Middleware

- **CORS**: Cross-origin resource sharing
- **Request Logging**: Request/response logging with unique IDs
- **Error Handling**: Structured error responses
- **Authentication**: JWT token validation

## Development

### Code Style
- Follow PEP 8 guidelines
- Use type hints throughout
- Keep files under 500 lines
- Use descriptive variable and function names

### Testing
```bash
# Run tests (when implemented)
pytest tests/
```

### Linting
```bash
# Format code
black src/
isort src/

# Check style
flake8 src/
```

## Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY .env .env

EXPOSE 8000
CMD ["uvicorn", "src.youtube_analysis_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables in Production
- Set `API_DEBUG=false`
- Use strong `JWT_SECRET_KEY`
- Configure proper `CORS_ORIGINS`
- Set up monitoring and logging

## API Documentation

When running in debug mode, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Security Considerations

- JWT tokens are stateless and self-contained
- Supabase handles user authentication and management
- CORS is configured to allow specific origins only
- Guest users have rate limiting
- All configuration is environment-based (no hardcoded secrets)

## Monitoring and Logging

- Request/response logging with unique request IDs
- Structured error handling
- Health check endpoints for monitoring
- Performance metrics (to be implemented)

## Future Enhancements

- Rate limiting middleware
- Caching layer (Redis)
- WebSocket support for real-time features
- Metrics and monitoring integration
- Database integration for user data
- Advanced authentication features