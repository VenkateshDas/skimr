# Configuration System Documentation

The YouTube Analysis Application uses a comprehensive, centralized configuration system that eliminates hardcoded values and provides flexible environment-based configuration.

## Overview

All configuration is managed through:
- **Environment variables** (`.env` file or system environment)
- **Centralized config module** (`src/youtube_analysis/core/config.py`)
- **Configuration validation** and helper utilities
- **Backward compatibility** for existing deployments

## Quick Start

### 1. Generate Configuration Template

```bash
# Generate a template .env file
python scripts/config_manager.py --template

# Or use interactive setup
python scripts/config_manager.py --setup
```

### 2. Configure Your Settings

Copy the generated `.env.template` to `.env` and configure your settings:

```bash
cp .env.template .env
# Edit .env with your API keys and preferences
```

### 3. Validate Configuration

```bash
# Check if your configuration is complete
python scripts/config_manager.py --validate

# See full configuration status
python scripts/config_manager.py --all
```

## Configuration Categories

### Core Application Settings

```env
APP_VERSION=0.1.0
DEBUG=false
ENVIRONMENT=development
```

### LLM Configuration

```env
# Default model settings
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_DEFAULT_TEMPERATURE=0.2
LLM_DEFAULT_MAX_TOKENS=0
LLM_DEFAULT_TIMEOUT=60

# Available models for UI selection
LLM_AVAILABLE_MODELS=gpt-4o-mini,gpt-4o,gpt-4-turbo,gemini-2.0-flash,claude-3-5-sonnet

# Model costs (JSON format, per 1K tokens)
LLM_MODEL_COSTS={"gpt-4o-mini": 0.00015, "gpt-4o": 0.005}
```

### Cache Configuration

```env
CACHE_EXPIRY_DAYS=7
CACHE_MAX_SIZE_MB=1000
ENABLE_CACHE=true
CACHE_AUTO_CLEANUP=true
```

### Network Settings

```env
HTTP_TIMEOUT_TOTAL=30
HTTP_TIMEOUT_CONNECT=10
HTTP_KEEPALIVE_TIMEOUT=30
VIDEO_DOWNLOAD_TIMEOUT=300
```

### Authentication & User Settings

```env
MAX_GUEST_ANALYSES=1
ENABLE_AUTH=true
SESSION_TIMEOUT_HOURS=24
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### API Keys

```env
# At least one LLM API key is required
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
GEMINI_API_KEY=your_gemini_key

# Optional APIs
YOUTUBE_API_KEY=your_youtube_key
TAVILY_API_KEY=your_tavily_key
```

### UI Configuration

```env
UI_DEFAULT_USE_CACHE=true
UI_DEFAULT_USE_OPTIMIZED=true
UI_DEFAULT_ANALYSIS_TYPES=Summary & Classification
UI_TEMPERATURE_MIN=0.0
UI_TEMPERATURE_MAX=1.0
UI_PAGE_TITLE=Skimr Summarizer
UI_PAGE_ICON=:material/movie:
```

### Chat Configuration

```env
CHAT_MAX_HISTORY=50
CHAT_ENABLE_STREAMING=true
```

### Analysis Configuration

```env
ANALYSIS_AVAILABLE_TYPES=Summary & Classification,Action Plan,Blog Post,LinkedIn Post,X Tweet
ANALYSIS_ENABLE_CONCURRENT=true
ANALYSIS_MAX_CONCURRENT_TASKS=3
```

## Configuration Management Utility

The `scripts/config_manager.py` utility provides comprehensive configuration management:

### Commands

```bash
# Validate current configuration
python scripts/config_manager.py --validate

# Generate .env template
python scripts/config_manager.py --template

# Show configuration summary
python scripts/config_manager.py --summary

# Check API key status
python scripts/config_manager.py --api-keys

# Check model availability
python scripts/config_manager.py --models

# Interactive setup
python scripts/config_manager.py --setup

# Run all checks
python scripts/config_manager.py --all
```

### Example Output

```
🔍 Validating Current Configuration...
==================================================
✅ Configuration is valid!
All required environment variables are set.

🔑 API Key Status
==================================================
OpenAI          ✅ Configured
Anthropic       ❌ Missing
Google/Gemini   ✅ Configured
YouTube         ✅ Configured

🤖 Model Availability
==================================================
OpenAI Models: gpt-4o-mini, gpt-4o, gpt-4-turbo
Google Models: gemini-2.0-flash, gemini-1.5-pro

✅ 5 models available
✅ Default model 'gpt-4o-mini' is available
```

## Programmatic Access

### Using the Configuration in Code

```python
from src.youtube_analysis.core.config import config

# Access configuration sections
print(f"Default model: {config.llm.default_model}")
print(f"Cache enabled: {config.cache.enable_cache}")
print(f"Max guest analyses: {config.auth.max_guest_analyses}")

# Helper functions
from src.youtube_analysis.core.config import (
    get_model_cost, 
    is_model_available,
    get_default_settings
)

cost = get_model_cost("gpt-4o-mini")  # Returns 0.00015
available = is_model_available("gpt-4o")  # Returns True/False
defaults = get_default_settings()  # Returns default UI settings
```

### Configuration Validation

```python
from src.youtube_analysis.core.config import validate_config

is_valid, missing_vars = validate_config()
if not is_valid:
    print(f"Missing: {missing_vars}")
```

## Environment Variable Reference

### Required Variables

These variables are required for the application to function:

- **At least one LLM API key**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`/`GEMINI_API_KEY`
- **Supabase credentials** (if auth enabled): `SUPABASE_URL`, `SUPABASE_KEY`
- **YouTube API key** (if YouTube API enabled): `YOUTUBE_API_KEY`

### Optional Variables

All other variables have sensible defaults and are optional.

### JSON Format Variables

Some variables accept JSON format for complex data:

```env
# Model costs (per 1K tokens)
LLM_MODEL_COSTS={"gpt-4o-mini": 0.00015, "gpt-4o": 0.005}

# Model descriptions
LLM_MODEL_DESCRIPTIONS={"gpt-4o-mini": "Fast and economical", "gpt-4o": "Most capable"}
```

### List Format Variables

Some variables accept comma-separated lists:

```env
# Available models
LLM_AVAILABLE_MODELS=gpt-4o-mini,gpt-4o,gemini-2.0-flash

# Analysis types
ANALYSIS_AVAILABLE_TYPES=Summary & Classification,Action Plan,Blog Post
```

## Migration from Hardcoded Values

The new configuration system maintains backward compatibility. Existing deployments will continue to work with default values.

### What Changed

- **Removed hardcoded values** from all modules
- **Centralized configuration** in `config.py`
- **Environment variable support** for all settings
- **Configuration validation** and utilities

### Benefits

1. **Flexibility**: Easy to customize without code changes
2. **Environment-specific configs**: Different settings for dev/staging/prod
3. **Security**: API keys and secrets in environment variables
4. **Maintainability**: Single source of truth for all configuration
5. **Validation**: Built-in validation and error reporting

## Troubleshooting

### Common Issues

1. **"Configuration incomplete" error**
   ```bash
   python scripts/config_manager.py --validate
   ```

2. **Model not available**
   ```bash
   python scripts/config_manager.py --models
   ```

3. **Invalid JSON in environment variable**
   - Check JSON syntax in variables like `LLM_MODEL_COSTS`
   - Use online JSON validators

4. **Permission errors with config files**
   ```bash
   chmod 644 .env
   ```

### Debug Configuration

```python
# Print current configuration
from src.youtube_analysis.core.config import print_config_summary
print_config_summary()

# Check specific values
from src.youtube_analysis.core.config import config
print(f"Cache dir: {config.cache.cache_dir}")
print(f"Available models: {config.llm.available_models}")
```

## Best Practices

1. **Use .env files** for local development
2. **Set environment variables** in production
3. **Validate configuration** before deployment
4. **Keep API keys secure** - never commit them to version control
5. **Use the config utility** for setup and validation
6. **Test configuration changes** with `--validate` flag

## Advanced Configuration

### Custom Chat Prompts

```env
CHAT_PROMPT_TEMPLATE=Your custom prompt template with {video_title} placeholder...
CHAT_WELCOME_TEMPLATE=Custom welcome message for {video_title}...
```

### Performance Tuning

```env
# Network timeouts
HTTP_TIMEOUT_TOTAL=60
HTTP_TIMEOUT_CONNECT=15

# Concurrent processing
ANALYSIS_MAX_CONCURRENT_TASKS=5

# Cache settings
CACHE_MAX_SIZE_MB=2000
CACHE_EXPIRY_DAYS=14
```

### Development vs Production

**Development (.env.dev)**:
```env
DEBUG=true
LOG_LEVEL=DEBUG
CACHE_EXPIRY_DAYS=1
```

**Production (.env.prod)**:
```env
DEBUG=false
LOG_LEVEL=INFO
CACHE_EXPIRY_DAYS=7
ENABLE_CACHE=true
```

## Support

For configuration issues:

1. Run `python scripts/config_manager.py --all` for complete status
2. Check the logs for configuration warnings
3. Validate your .env file syntax
4. Ensure all required API keys are set

The configuration system is designed to be robust and provide clear error messages to help you resolve any issues quickly. 