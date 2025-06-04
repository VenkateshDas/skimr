# Configuration Management Endpoints Specification

## Overview

Configuration management endpoints that provide runtime access to application settings, model configurations, and system parameters while maintaining security and environment-based configuration principles.

## Configuration Router

### Base Configuration
```python
# Pseudocode: Configuration router setup
router = APIRouter(prefix="/api/v1/config", tags=["configuration"])
```

## Data Models

### Request Models
```python
# Pseudocode: Configuration request models
CLASS ModelConfigRequest(BaseModel):
    PROPERTY model_name: str = Field(..., description="LLM model name")
    PROPERTY temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    PROPERTY max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)
    PROPERTY top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    PROPERTY frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    PROPERTY presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)

CLASS AnalysisConfigRequest(BaseModel):
    PROPERTY default_analysis_types: List[str] = Field(..., description="Default analysis types")
    PROPERTY max_video_duration: Optional[int] = Field(default=None, ge=60, description="Max video duration in seconds")
    PROPERTY enable_caching: bool = Field(default=True, description="Enable result caching")
    PROPERTY cache_ttl_hours: Optional[int] = Field(default=None, ge=1, le=168, description="Cache TTL in hours")

CLASS SystemConfigRequest(BaseModel):
    PROPERTY max_concurrent_analyses: Optional[int] = Field(default=None, ge=1, le=50)
    PROPERTY rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=1000)
    PROPERTY guest_analysis_limit: Optional[int] = Field(default=None, ge=0, le=10)
    PROPERTY enable_guest_access: bool = Field(default=True, description="Allow guest access")
```

### Response Models
```python
# Pseudocode: Configuration response models
CLASS ModelConfig(BaseModel):
    PROPERTY model_name: str
    PROPERTY provider: str
    PROPERTY temperature: float
    PROPERTY max_tokens: int
    PROPERTY top_p: float
    PROPERTY frequency_penalty: float
    PROPERTY presence_penalty: float
    PROPERTY cost_per_1k_input: float
    PROPERTY cost_per_1k_output: float
    PROPERTY context_window: int
    PROPERTY supports_streaming: bool

CLASS AnalysisConfig(BaseModel):
    PROPERTY available_analysis_types: List[str]
    PROPERTY default_analysis_types: List[str]
    PROPERTY max_video_duration: int
    PROPERTY enable_caching: bool
    PROPERTY cache_ttl_hours: int
    PROPERTY supported_languages: List[str]
    PROPERTY max_transcript_length: int

CLASS SystemConfig(BaseModel):
    PROPERTY version: str
    PROPERTY environment: str
    PROPERTY max_concurrent_analyses: int
    PROPERTY rate_limit_per_minute: int
    PROPERTY guest_analysis_limit: int
    PROPERTY enable_guest_access: bool
    PROPERTY maintenance_mode: bool
    PROPERTY features_enabled: Dict[str, bool]

CLASS AppConfig(BaseModel):
    PROPERTY models: List[ModelConfig]
    PROPERTY analysis: AnalysisConfig
    PROPERTY system: SystemConfig
    PROPERTY ui_settings: Dict[str, Any]
```

## Public Configuration Endpoints

### GET /api/v1/config/public
```python
# Pseudocode: Get public configuration
@router.get("/public", response_model=SuccessResponse[Dict[str, Any]])
ASYNC FUNCTION get_public_config() -> SuccessResponse[Dict[str, Any]]:
    """
    Get public configuration settings that can be safely exposed to frontend.
    
    No authentication required.
    """
    TRY:
        # Get safe configuration values from environment
        public_config = {
            "app": {
                "name": ENV.get("APP_NAME", "YouTube Analysis API"),
                "version": ENV.get("APP_VERSION", "1.0.0"),
                "environment": ENV.get("ENVIRONMENT", "production"),
                "maintenance_mode": ENV.get("MAINTENANCE_MODE", "false").lower() == "true"
            },
            "features": {
                "guest_access": ENV.get("ENABLE_GUEST_ACCESS", "true").lower() == "true",
                "chat_enabled": ENV.get("ENABLE_CHAT", "true").lower() == "true",
                "streaming_enabled": ENV.get("ENABLE_STREAMING", "true").lower() == "true",
                "subtitle_translation": ENV.get("ENABLE_SUBTITLE_TRANSLATION", "false").lower() == "true"
            },
            "limits": {
                "guest_analysis_limit": int(ENV.get("MAX_GUEST_ANALYSES", 1)),
                "max_video_duration": int(ENV.get("MAX_VIDEO_DURATION_SECONDS", 3600)),
                "rate_limit_per_minute": int(ENV.get("RATE_LIMIT_PER_MINUTE", 60))
            },
            "analysis": {
                "available_types": [
                    "Summary & Classification",
                    "Action Plan", 
                    "Blog Post",
                    "LinkedIn Post",
                    "X Tweet"
                ],
                "default_types": ["Summary & Classification"],
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
            },
            "models": {
                "available": get_available_models(),
                "default": ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini")
            }
        }
        
        RETURN SuccessResponse(data=public_config)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting public config: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve public configuration")

FUNCTION get_available_models() -> List[Dict[str, Any]]:
    """Get list of available LLM models with public information."""
    models = [
        {
            "name": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "provider": "OpenAI",
            "context_window": 128000,
            "supports_streaming": True,
            "recommended": True
        },
        {
            "name": "gpt-4o",
            "display_name": "GPT-4o",
            "provider": "OpenAI", 
            "context_window": 128000,
            "supports_streaming": True,
            "recommended": False
        },
        {
            "name": "claude-3-5-sonnet-20241022",
            "display_name": "Claude 3.5 Sonnet",
            "provider": "Anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "recommended": False
        }
    ]
    
    # Filter based on enabled models from environment
    enabled_models = ENV.get("ENABLED_MODELS", "gpt-4o-mini,gpt-4o").split(",")
    RETURN [model FOR model IN models IF model["name"] IN enabled_models]
```

### GET /api/v1/config/models
```python
# Pseudocode: Get model configurations
@router.get("/models", response_model=SuccessResponse[List[ModelConfig]])
ASYNC FUNCTION get_model_configs(
    current_user: Optional[UserProfile] = Depends(get_optional_user)
) -> SuccessResponse[List[ModelConfig]]:
    """
    Get detailed model configurations.
    
    Includes pricing information for authenticated users.
    """
    TRY:
        models = []
        available_models = get_available_models()
        
        FOR model_info IN available_models:
            model_name = model_info["name"]
            
            # Get model configuration from environment
            model_config = ModelConfig(
                model_name=model_name,
                provider=model_info["provider"],
                temperature=float(ENV.get(f"LLM_{model_name.upper().replace('-', '_')}_TEMPERATURE", 0.2)),
                max_tokens=int(ENV.get(f"LLM_{model_name.upper().replace('-', '_')}_MAX_TOKENS", 4096)),
                top_p=float(ENV.get(f"LLM_{model_name.upper().replace('-', '_')}_TOP_P", 1.0)),
                frequency_penalty=float(ENV.get(f"LLM_{model_name.upper().replace('-', '_')}_FREQUENCY_PENALTY", 0.0)),
                presence_penalty=float(ENV.get(f"LLM_{model_name.upper().replace('-', '_')}_PRESENCE_PENALTY", 0.0)),
                cost_per_1k_input=get_model_cost(model_name, "input") IF current_user ELSE 0.0,
                cost_per_1k_output=get_model_cost(model_name, "output") IF current_user ELSE 0.0,
                context_window=model_info["context_window"],
                supports_streaming=model_info["supports_streaming"]
            )
            
            models.append(model_config)
        
        RETURN SuccessResponse(data=models)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting model configs: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve model configurations")

FUNCTION get_model_cost(model_name: str, token_type: str) -> float:
    """Get model pricing from environment configuration."""
    cost_key = f"LLM_{model_name.upper().replace('-', '_')}_COST_{token_type.upper()}_PER_1K"
    RETURN float(ENV.get(cost_key, 0.0))
```

## Administrative Configuration Endpoints

### GET /api/v1/config/system
```python
# Pseudocode: Get system configuration
@router.get("/system", response_model=SuccessResponse[SystemConfig])
ASYNC FUNCTION get_system_config(
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[SystemConfig]:
    """
    Get comprehensive system configuration.
    
    Requires admin privileges.
    """
    TRY:
        system_config = SystemConfig(
            version=ENV.get("APP_VERSION", "1.0.0"),
            environment=ENV.get("ENVIRONMENT", "production"),
            max_concurrent_analyses=int(ENV.get("MAX_CONCURRENT_ANALYSES", 10)),
            rate_limit_per_minute=int(ENV.get("RATE_LIMIT_PER_MINUTE", 60)),
            guest_analysis_limit=int(ENV.get("MAX_GUEST_ANALYSES", 1)),
            enable_guest_access=ENV.get("ENABLE_GUEST_ACCESS", "true").lower() == "true",
            maintenance_mode=ENV.get("MAINTENANCE_MODE", "false").lower() == "true",
            features_enabled={
                "chat": ENV.get("ENABLE_CHAT", "true").lower() == "true",
                "streaming": ENV.get("ENABLE_STREAMING", "true").lower() == "true",
                "caching": ENV.get("ENABLE_CACHING", "true").lower() == "true",
                "analytics": ENV.get("ENABLE_ANALYTICS", "false").lower() == "true",
                "subtitle_translation": ENV.get("ENABLE_SUBTITLE_TRANSLATION", "false").lower() == "true"
            }
        )
        
        logger.info(f"System config accessed by admin {current_user.email}")
        
        RETURN SuccessResponse(data=system_config)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting system config: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve system configuration")
```

### PUT /api/v1/config/system
```python
# Pseudocode: Update system configuration
@router.put("/system", response_model=SuccessResponse[SystemConfig])
ASYNC FUNCTION update_system_config(
    request: SystemConfigRequest,
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[SystemConfig]:
    """
    Update system configuration settings.
    
    Requires admin privileges. Updates runtime configuration only.
    """
    TRY:
        config_manager = get_config_manager()
        
        # Update runtime configuration
        updates = {}
        IF request.max_concurrent_analyses IS NOT None:
            updates["MAX_CONCURRENT_ANALYSES"] = str(request.max_concurrent_analyses)
        
        IF request.rate_limit_per_minute IS NOT None:
            updates["RATE_LIMIT_PER_MINUTE"] = str(request.rate_limit_per_minute)
        
        IF request.guest_analysis_limit IS NOT None:
            updates["MAX_GUEST_ANALYSES"] = str(request.guest_analysis_limit)
        
        updates["ENABLE_GUEST_ACCESS"] = str(request.enable_guest_access).lower()
        
        # Apply updates to runtime configuration
        FOR key, value IN updates.items():
            config_manager.set_runtime_config(key, value)
        
        # Get updated configuration
        updated_config = AWAIT get_system_config(current_user)
        
        logger.info(f"System config updated by admin {current_user.email}: {updates}")
        
        RETURN updated_config
        
    EXCEPT Exception as e:
        logger.error(f"Error updating system config: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to update system configuration")
```

### GET /api/v1/config/analysis
```python
# Pseudocode: Get analysis configuration
@router.get("/analysis", response_model=SuccessResponse[AnalysisConfig])
ASYNC FUNCTION get_analysis_config() -> SuccessResponse[AnalysisConfig]:
    """
    Get analysis configuration settings.
    """
    TRY:
        analysis_config = AnalysisConfig(
            available_analysis_types=[
                "Summary & Classification",
                "Action Plan",
                "Blog Post", 
                "LinkedIn Post",
                "X Tweet"
            ],
            default_analysis_types=ENV.get("DEFAULT_ANALYSIS_TYPES", "Summary & Classification").split(","),
            max_video_duration=int(ENV.get("MAX_VIDEO_DURATION_SECONDS", 3600)),
            enable_caching=ENV.get("ENABLE_CACHING", "true").lower() == "true",
            cache_ttl_hours=int(ENV.get("CACHE_TTL_HOURS", 24)),
            supported_languages=ENV.get("SUPPORTED_LANGUAGES", "en,es,fr,de,it,pt,ru,ja,ko,zh").split(","),
            max_transcript_length=int(ENV.get("MAX_TRANSCRIPT_LENGTH", 50000))
        )
        
        RETURN SuccessResponse(data=analysis_config)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting analysis config: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve analysis configuration")
```

### GET /api/v1/config/health
```python
# Pseudocode: Configuration health check
@router.get("/health", response_model=SuccessResponse[Dict[str, Any]])
ASYNC FUNCTION get_config_health() -> SuccessResponse[Dict[str, Any]]:
    """
    Get configuration health status and validation.
    """
    TRY:
        health_status = {
            "status": "healthy",
            "checks": {},
            "warnings": [],
            "errors": []
        }
        
        # Check required environment variables
        required_vars = [
            "LLM_OPENAI_API_KEY",
            "SUPABASE_URL", 
            "SUPABASE_ANON_KEY",
            "JWT_SECRET_KEY"
        ]
        
        FOR var IN required_vars:
            IF ENV.get(var):
                health_status["checks"][var] = "present"
            ELSE:
                health_status["checks"][var] = "missing"
                health_status["errors"].append(f"Missing required environment variable: {var}")
                health_status["status"] = "unhealthy"
        
        # Check model configurations
        available_models = get_available_models()
        IF len(available_models) == 0:
            health_status["errors"].append("No models configured")
            health_status["status"] = "unhealthy"
        ELSE:
            health_status["checks"]["models"] = f"{len(available_models)} configured"
        
        # Check numeric configurations
        TRY:
            int(ENV.get("MAX_CONCURRENT_ANALYSES", 10))
            health_status["checks"]["max_concurrent_analyses"] = "valid"
        EXCEPT ValueError:
            health_status["warnings"].append("Invalid MAX_CONCURRENT_ANALYSES value")
        
        TRY:
            float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2))
            health_status["checks"]["default_temperature"] = "valid"
        EXCEPT ValueError:
            health_status["warnings"].append("Invalid LLM_DEFAULT_TEMPERATURE value")
        
        # Check feature flags
        feature_flags = [
            "ENABLE_GUEST_ACCESS",
            "ENABLE_CHAT", 
            "ENABLE_STREAMING",
            "ENABLE_CACHING"
        ]
        
        FOR flag IN feature_flags:
            value = ENV.get(flag, "true").lower()
            IF value IN ["true", "false"]:
                health_status["checks"][flag] = value
            ELSE:
                health_status["warnings"].append(f"Invalid boolean value for {flag}: {value}")
        
        IF len(health_status["warnings"]) > 0 AND health_status["status"] == "healthy":
            health_status["status"] = "degraded"
        
        RETURN SuccessResponse(data=health_status)
        
    EXCEPT Exception as e:
        logger.error(f"Error checking config health: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to check configuration health")
```

## Utility Functions

### Configuration Manager
```python
# Pseudocode: Runtime configuration manager
CLASS ConfigManager:
    FUNCTION __init__(self):
        self.runtime_config = {}
    
    FUNCTION set_runtime_config(self, key: str, value: str):
        """Set runtime configuration value."""
        self.runtime_config[key] = value
        # In production, this might update a Redis cache or database
    
    FUNCTION get_runtime_config(self, key: str, default: str = None) -> str:
        """Get runtime configuration value with fallback to environment."""
        RETURN self.runtime_config.get(key, ENV.get(key, default))
    
    FUNCTION get_all_runtime_config(self) -> Dict[str, str]:
        """Get all runtime configuration values."""
        RETURN self.runtime_config.copy()

# Global configuration manager instance
config_manager = ConfigManager()

FUNCTION get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    RETURN config_manager
```

## TDD Test Anchors

### Public Configuration Tests
```python
# Test anchor: Public configuration access
TEST test_get_public_config():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/config/public")
        ASSERT response.status_code == 200
        data = response.json()["data"]
        ASSERT "app" IN data
        ASSERT "features" IN data
        ASSERT "limits" IN data
        ASSERT "analysis" IN data

# Test anchor: Model configurations
TEST test_get_model_configs():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/config/models")
        ASSERT response.status_code == 200
        models = response.json()["data"]
        ASSERT len(models) > 0
        ASSERT "model_name" IN models[0]
        ASSERT "provider" IN models[0]

# Test anchor: Analysis configuration
TEST test_get_analysis_config():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/config/analysis")
        ASSERT response.status_code == 200
        data = response.json()["data"]
        ASSERT "available_analysis_types" IN data
        ASSERT "max_video_duration" IN data
```

### Administrative Configuration Tests
```python
# Test anchor: System configuration (admin only)
TEST test_get_system_config_admin():
    WITH TestClient(app) AS client:
        admin_token = get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = client.get("/api/v1/config/system", headers=headers)
        ASSERT response.status_code == 200
        ASSERT "max_concurrent_analyses" IN response.json()["data"]

# Test anchor: System configuration (non-admin)
TEST test_get_system_config_forbidden():
    WITH TestClient(app) AS client:
        user_token = get_user_token()
        headers = {"Authorization": f"Bearer {user_token}"}
        
        response = client.get("/api/v1/config/system", headers=headers)
        ASSERT response.status_code == 403

# Test anchor: Configuration health check
TEST test_config_health():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/config/health")
        ASSERT response.status_code == 200
        data = response.json()["data"]
        ASSERT "status" IN data
        ASSERT "checks" IN data
        ASSERT data["status"] IN ["healthy", "degraded", "unhealthy"]

# Test anchor: Update system configuration
TEST test_update_system_config():
    WITH TestClient(app) AS client:
        admin_token = get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = client.put("/api/v1/config/system", 
            json={
                "max_concurrent_analyses": 15,
                "enable_guest_access": False
            },
            headers=headers
        )
        ASSERT response.status_code == 200
        ASSERT response.json()["data"]["max_concurrent_analyses"] == 15
```

This specification provides comprehensive configuration management that maintains security while offering flexible runtime configuration capabilities for both public and administrative use cases.