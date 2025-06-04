"""Configuration management for FastAPI backend."""

import os
from dataclasses import dataclass
from typing import List, Optional
from functools import lru_cache


@dataclass
class APIConfig:
    """API configuration settings."""
    
    # Core API settings
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    debug: bool = os.getenv("API_DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("API_SECRET_KEY", "")
    
    # CORS settings
    cors_origins: List[str] = None
    
    # JWT Token settings
    jwt_secret_key: str = os.getenv("API_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Legacy token settings for backward compatibility
    access_token_expire_minutes: int = int(os.getenv("API_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Application metadata
    title: str = os.getenv("API_TITLE", "YouTube Analysis API")
    description: str = "Backend API for YouTube video analysis and chat"
    version: str = os.getenv("APP_VERSION", "1.0.0")
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Usage limits
    max_guest_analyses: int = int(os.getenv("MAX_GUEST_ANALYSES", "1"))
    
    # Request settings
    request_timeout: int = int(os.getenv("API_REQUEST_TIMEOUT", "30"))
    max_request_size: int = int(os.getenv("API_MAX_REQUEST_SIZE", "10485760"))  # 10MB
    
    # Rate limiting
    rate_limit_requests: int = int(os.getenv("API_RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window: int = int(os.getenv("API_RATE_LIMIT_WINDOW", "60"))
    
    # Logging
    log_level: str = os.getenv("API_LOG_LEVEL", "INFO")
    log_format: str = os.getenv("API_LOG_FORMAT", "json")
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.cors_origins is None:
            origins_str = os.getenv("API_CORS_ORIGINS", "http://localhost:3000")
            self.cors_origins = [origin.strip() for origin in origins_str.split(",")]
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.secret_key:
            errors.append("API_SECRET_KEY is required")
        
        if self.access_token_expire_minutes < 1:
            errors.append("API_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        
        if self.port < 1 or self.port > 65535:
            errors.append("API_PORT must be between 1 and 65535")
        
        if self.max_guest_analyses < 0:
            errors.append("MAX_GUEST_ANALYSES must be non-negative")
        
        if self.request_timeout < 1:
            errors.append("API_REQUEST_TIMEOUT must be positive")
        
        if self.rate_limit_requests < 1:
            errors.append("API_RATE_LIMIT_REQUESTS must be positive")
        
        if self.rate_limit_window < 1:
            errors.append("API_RATE_LIMIT_WINDOW must be positive")
        
        return errors


@dataclass
class SupabaseConfig:
    """Supabase configuration settings."""
    
    url: str = os.getenv("SUPABASE_URL", "")
    anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    def validate(self) -> List[str]:
        """Validate Supabase configuration."""
        errors = []
        
        if not self.url:
            errors.append("SUPABASE_URL is required")
        
        if not self.anon_key:
            errors.append("SUPABASE_ANON_KEY is required")
        
        return errors


@dataclass
class LLMConfig:
    """LLM configuration settings (inherited from existing config)."""
    
    default_model: str = os.getenv("LLM_DEFAULT_MODEL", "gpt-4o-mini")
    default_temperature: float = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0.2"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    
    def validate(self) -> List[str]:
        """Validate LLM configuration."""
        errors = []
        
        if self.default_temperature < 0.0 or self.default_temperature > 1.0:
            errors.append("LLM_DEFAULT_TEMPERATURE must be between 0.0 and 1.0")
        
        if self.max_tokens < 1:
            errors.append("LLM_MAX_TOKENS must be positive")
        
        return errors


@dataclass
class AppConfig:
    """Complete application configuration."""
    
    api: APIConfig
    supabase: SupabaseConfig
    llm: LLMConfig
    
    def validate(self) -> List[str]:
        """Validate all configuration sections."""
        errors = []
        errors.extend(self.api.validate())
        errors.extend(self.supabase.validate())
        errors.extend(self.llm.validate())
        return errors


@lru_cache()
def get_config() -> AppConfig:
    """Get validated application configuration."""
    config = AppConfig(
        api=APIConfig(),
        supabase=SupabaseConfig(),
        llm=LLMConfig()
    )
    
    errors = config.validate()
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return config


def get_api_config() -> APIConfig:
    """Get API configuration."""
    return get_config().api


def get_supabase_config() -> SupabaseConfig:
    """Get Supabase configuration."""
    return get_config().supabase


def get_llm_config() -> LLMConfig:
    """Get LLM configuration."""
    return get_config().llm