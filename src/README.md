# YouTube Analysis Application - Source Code Documentation

## Overview

This directory contains the complete source code for the YouTube Analysis application - a sophisticated tool for analyzing YouTube videos using AI-powered transcript analysis, content summarization, and interactive chat capabilities.

## Architecture

The application follows **Clean Architecture** principles with clear separation of concerns:

- **Core**: Fundamental business logic and infrastructure
- **Services**: Application-specific business logic
- **Repositories**: Data access abstraction layer
- **Models**: Domain entities and data structures
- **UI**: User interface components and session management
- **Workflows**: Complex business processes orchestration
- **Utils**: Shared utilities and helper functions

## Directory Structure

### 📁 `youtube_analysis/` - Main Application Package

The core application package organized in clean architecture layers.

#### 🏗️ **Core Infrastructure** (`core/`)

**Purpose**: Contains fundamental infrastructure components that the entire application depends on.

- **`cache_manager.py`** - Redis/file-based caching implementation
- **`config.py`** - Application configuration management
- **`llm_manager.py`** - Large Language Model interaction manager
- **`youtube_client.py`** - YouTube API client with rate limiting

**When to modify**:
- ✅ Adding new configuration parameters
- ✅ Changing caching strategies
- ✅ Integrating new LLM providers
- ✅ Modifying YouTube API integration

#### 📊 **Data Models** (`models/`)

**Purpose**: Domain entities and data structures representing business concepts.

- **`analysis_result.py`** - Video analysis results, task outputs, token usage
- **`video_data.py`** - YouTube video metadata and transcript data
- **`chat_session.py`** - Chat conversation management

**When to modify**:
- ✅ Adding new analysis result fields
- ✅ Extending video metadata
- ✅ Modifying chat session structure
- ✅ Adding new enums (categories, status types)

#### 🗄️ **Data Access Layer** (`repositories/`)

**Purpose**: Abstracts data persistence and external API calls.

- **`cache_repository.py`** - Caching operations for analysis results
- **`youtube_repository.py`** - YouTube data fetching and transcript retrieval

**When to modify**:
- ✅ Adding new caching strategies
- ✅ Implementing new data sources
- ✅ Modifying data persistence logic
- ✅ Adding database integration

#### 🔧 **Business Services** (`services/`)

**Purpose**: Application-specific business logic and use cases.

- **`analysis_service.py`** - Core video analysis orchestration
- **`auth_service.py`** - User authentication and authorization
- **`chat_service.py`** - Interactive chat with video content
- **`content_service.py`** - Content management and retrieval
- **`cost_service.py`** - Dynamic LLM cost calculation using Glama.ai API
- **`transcript_service.py`** - Transcript processing and management
- **`user_stats_service.py`** - User analytics and statistics

**When to modify**:
- ✅ Adding new analysis types
- ✅ Implementing new business rules
- ✅ Adding authentication providers
- ✅ Modifying chat behavior
- ✅ Adding content filters

#### 🔄 **Workflows** (`workflows/`)

**Purpose**: Orchestrates complex multi-step business processes.

- **`crew.py`** - CrewAI agent configuration and setup
- **`video_analysis_workflow.py`** - End-to-end video analysis process

**When to modify**:
- ✅ Adding new AI agents
- ✅ Modifying analysis steps
- ✅ Changing workflow orchestration
- ✅ Adding parallel processing

#### 🎨 **User Interface** (`ui/`)

**Purpose**: Streamlit-based UI components and session management.

- **`components.py`** - Reusable UI components
- **`helpers.py`** - UI utility functions
- **`session_manager.py`** - Streamlit session state management
- **`streamlit_callbacks.py`** - Progress and status callbacks

**When to modify**:
- ✅ Adding new UI components
- ✅ Modifying styling and themes
- ✅ Changing user interaction flows
- ✅ Adding new progress indicators

#### 🔧 **Utilities** (`utils/`)

**Purpose**: Shared utilities and helper functions used across the application.

- **`cache_utils.py`** - Caching helper functions
- **`chat_utils.py`** - Chat processing utilities
- **`logging.py`** - Centralized logging configuration
- **`transcript_utils.py`** - Transcript processing helpers
- **`video_highlights.py`** - Video highlight extraction
- **`youtube_utils.py`** - YouTube URL validation and processing

**When to modify**:
- ✅ Adding new utility functions
- ✅ Improving logging configuration
- ✅ Adding data validation helpers
- ✅ Optimizing common operations

#### 🛠️ **Tools** (`tools/`)

**Purpose**: External tools and integrations for AI agents.

- **`youtube_tools.py`** - YouTube-specific tools for AI agents

**When to modify**:
- ✅ Adding new AI tools
- ✅ Integrating external APIs
- ✅ Adding specialized processing tools

#### 🔌 **Adapters** (`adapters/`)

**Purpose**: Interface adapters for external frameworks and systems.

- **`webapp_adapter.py`** - Streamlit web application adapter

**When to modify**:
- ✅ Adding new UI frameworks
- ✅ Creating API adapters
- ✅ Integrating with external systems

#### ⚙️ **Configuration** (`config/`)

**Purpose**: YAML configuration files for AI agents and tasks.

- **`agents.yaml`** - AI agent definitions and roles
- **`tasks.yaml`** - Task specifications for analysis workflows

**When to modify**:
- ✅ Adding new AI agents
- ✅ Modifying agent behaviors
- ✅ Creating new analysis tasks
- ✅ Adjusting agent prompts

#### 🖼️ **Assets** (`logo/`)

**Purpose**: Static assets like logos and images.

- **`logo_v2.png`** - Application logo (current version)
- **`original.png`** - Original logo file

**When to modify**:
- ✅ Updating branding assets
- ✅ Adding new images

### 📄 Core Files

#### `main.py` (900 lines)
**Purpose**: Application entry point and main orchestration logic.

**When to modify**:
- ✅ Adding new command-line options
- ✅ Changing application startup sequence
- ✅ Adding environment-specific configurations

#### `service_factory.py` (159 lines)
**Purpose**: Dependency injection container implementing the Service Locator pattern.

**When to modify**:
- ✅ Adding new services
- ✅ Changing service dependencies
- ✅ Implementing service lifecycle management

#### `__init__.py` (47 lines)
**Purpose**: Package initialization and public API exports.

**When to modify**:
- ✅ Exposing new public APIs
- ✅ Adding backward compatibility
- ✅ Managing package imports

### 📄 `youtube_analysis_webapp.py` (876 lines)
**Purpose**: Streamlit web application entry point and main UI orchestration.

**When to modify**:
- ✅ Adding new pages
- ✅ Modifying app layout
- ✅ Changing navigation structure
- ✅ Adding global UI components

## Development Guidelines

### 🎯 **Common Development Scenarios**

#### Adding a New Analysis Type
1. **Models** → Update `analysis_result.py` with new enum values
2. **Config** → Add task definition in `tasks.yaml`
3. **Workflows** → Update `crew.py` or workflow logic
4. **Services** → Modify `analysis_service.py` for new logic
5. **UI** → Update components to display new analysis type

#### Adding a New UI Component
1. **UI** → Create component in `components.py`
2. **UI** → Add helper functions in `helpers.py` if needed
3. **Adapters** → Update `webapp_adapter.py` if needed
4. **Main** → Integrate into `youtube_analysis_webapp.py`

#### Integrating a New Data Source
1. **Core** → Add client in `core/` directory
2. **Repositories** → Create new repository class
3. **Services** → Update relevant services
4. **Factory** → Add to `service_factory.py`

#### Adding Authentication Provider
1. **Services** → Extend `auth_service.py`
2. **Core** → Add configuration in `config.py`
3. **UI** → Update authentication components
4. **Models** → Extend user models if needed

#### Performance Optimization
1. **Core** → Improve caching in `cache_manager.py`
2. **Utils** → Optimize functions in `utils/`
3. **Repositories** → Add query optimization
4. **Services** → Implement async patterns

### 🔍 **Debugging Guidelines**

#### Analysis Issues
- **Check**: `services/analysis_service.py` for orchestration logic
- **Check**: `workflows/` for step-by-step execution
- **Check**: `repositories/youtube_repository.py` for data fetching
- **Logs**: Enable debug logging in `utils/logging.py`

#### UI Issues
- **Check**: `ui/components.py` for component logic
- **Check**: `ui/session_manager.py` for state management
- **Check**: `adapters/webapp_adapter.py` for integration issues

#### Performance Issues
- **Check**: `core/cache_manager.py` for caching effectiveness
- **Check**: `repositories/cache_repository.py` for data access patterns
- **Monitor**: Service factory for dependency creation

#### Authentication Issues
- **Check**: `services/auth_service.py` for auth logic
- **Check**: `core/config.py` for configuration
- **Verify**: Environment variables and API keys

### 📝 **Best Practices**

1. **Follow Clean Architecture**: Maintain dependency direction (UI → Services → Repositories → Core)
2. **Use Dependency Injection**: Always use `service_factory.py` for service creation
3. **Async/Await**: Use async patterns for I/O operations
4. **Error Handling**: Implement comprehensive error handling with logging
5. **Type Hints**: Use type hints throughout the codebase
6. **Testing**: Write tests for business logic in `services/` and `workflows/`

### 🧪 **Testing Strategy**

- **Unit Tests**: Focus on `services/`, `utils/`, and `models/`
- **Integration Tests**: Test `repositories/` and `workflows/`
- **E2E Tests**: Test complete user flows through `adapters/`

## Getting Started

1. **Read**: Start with `main.py` to understand application flow
2. **Explore**: Check `service_factory.py` to understand dependencies
3. **Understand**: Review `models/` to understand data structures
4. **Navigate**: Use this documentation to find the right location for your changes

## New Features

### 💰 **Dynamic Cost Calculation System**

The application now includes a sophisticated cost calculation system that uses the [Glama.ai Cost Calculator API](https://dev.to/punkpeye/api-for-calculating-openai-and-other-llm-costs-28i2) for real-time LLM cost estimation:

#### Key Features:
- **Real-time Pricing**: Get up-to-date costs from 30+ LLM providers
- **Accurate Token Counting**: Precise cost breakdown for input/output tokens
- **Smart Caching**: Reduces API calls with intelligent caching strategies
- **Fallback Support**: Gracefully falls back to static costs if API is unavailable
- **Wide Model Support**: OpenAI, Anthropic, Google, Meta, and more

#### Quick Setup:
1. Get your API key from [glama.ai](https://glama.ai/settings/api-keys)
2. Add to your `.env` file:
   ```env
   GLAMA_API_KEY=your_api_key_here
   ENABLE_DYNAMIC_COSTS=true
   ```
3. Test the integration:
   ```bash
   python scripts/test_cost_api.py
   ```

#### Documentation:
- **Full Guide**: See `docs/COST_CALCULATION.md` for complete documentation
- **Test Script**: Use `scripts/test_cost_api.py` to verify setup
- **Integration**: Automatically integrated into both WebApp and CLI interfaces

The system maintains full backward compatibility and will automatically fall back to static costs if the API is unavailable.

## Support

For questions about the architecture or where to make specific changes, refer to this documentation or contact the development team. 