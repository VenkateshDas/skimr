# Skimr - AI-Powered YouTube Video Analyzer

<div align="center">

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/yourusername/skimr)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/streamlit-1.44+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

*Transform hours of video content into actionable insights in minutes*

[🚀 Quick Start](#quick-start) • [📖 Documentation](#documentation) • [🏗️ Architecture](#architecture) • [🤝 Contributing](#contributing)

</div>

## 🎯 Overview

Skimr is an enterprise-grade YouTube video analysis platform that leverages cutting-edge AI to transform video content consumption. Built with a robust service-oriented architecture, it provides intelligent video analysis, interactive chat capabilities, and automated content generation tools.

### 🎬 Problem Statement

In today's content-rich environment, professionals and researchers face significant challenges:

- **Time Inefficiency**: Watching hours of video content to extract key insights
- **Information Discovery**: Determining video relevance without full consumption  
- **Context Navigation**: Finding specific information within lengthy videos
- **Knowledge Extraction**: Converting educational content into actionable insights
- **Content Repurposing**: Adapting video content for different platforms and formats

### ✨ Solution

Skimr addresses these challenges through an intelligent AI-driven approach:

- **🤖 AI-Powered Analysis**: Multi-agent CrewAI system for comprehensive content understanding
- **💬 Interactive Q&A**: LangGraph-powered chat interface for video exploration
- **📊 Smart Categorization**: Automated classification with context-aware tagging
- **⚡ Real-time Insights**: Streaming analysis with live progress tracking
- **🎨 Content Generation**: Automated blog posts, social media content, and summaries
- **🔍 Semantic Search**: Vector-based transcript exploration with timestamp navigation
- **🏗️ Enterprise Architecture**: Scalable, maintainable design with comprehensive caching

## 🌟 Key Features

### Core Analysis Engine
- **Multi-Modal Transcript Processing** with automated extraction and timestamping
- **Intelligent Content Categorization** using specialized AI agents
- **Context-Aware Classification** (Tutorial, Review, Interview, Educational, etc.)
- **Comprehensive Video Summarization** with key point extraction
- **Actionable Insights Generation** with recommended next steps

### Interactive Intelligence
- **Real-time Chat Interface** powered by LangGraph and RAG (Retrieval-Augmented Generation)
- **Vector-Based Semantic Search** through video transcripts using FAISS
- **Timestamp-Synchronized Navigation** with clickable transcript segments
- **Streaming AI Responses** for enhanced user experience

### Content Generation Suite
- **Professional Blog Post Creation** with web research integration
- **LinkedIn Content Optimization** for professional networking
- **Twitter Thread Generation** with influencer-style adaptation
- **SEO-Optimized Summaries** for content marketing

### Enterprise Features
- **Multi-Tenant Authentication** with Supabase integration
- **Advanced Caching System** with TTL and memory management
- **Performance Analytics** with detailed metrics and monitoring
- **Docker-Ready Deployment** with multi-stage builds
- **Comprehensive API Integration** (OpenAI, Anthropic, Google Gemini)

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** with pip package manager
- **API Keys** for at least one LLM provider:
  - OpenAI API key (recommended for optimal performance)
  - Anthropic API key (optional, for Claude models)  
  - Google API key (optional, for Gemini models)
- **Tavily API key** (optional, for enhanced web search capabilities)
- **Supabase credentials** (optional, for user authentication)

### 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/skimr.git
   cd skimr
   ```

2. **Set up Python environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env with your API keys
   nano .env
   ```

   **Required Environment Variables:**
   ```env
   # Core LLM API (choose at least one)
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # Optional: Enhanced search capabilities
   TAVILY_API_KEY=your_tavily_api_key_here
   
   # Optional: User authentication
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   
   # Application Configuration
   CACHE_EXPIRY_DAYS=7
   LOG_LEVEL=INFO
   MAX_GUEST_ANALYSES=1
   ```

5. **Launch the application**
   ```bash
   streamlit run src/youtube_analysis_webapp.py
   ```

6. **Access the interface**
   - Open your browser to `http://localhost:8501`
   - Enter a YouTube URL and start analyzing!

### 🐳 Docker Deployment

```bash
# Build the Docker image
docker build -t skimr .

# Run the container
docker run -p 8501:8501 --env-file .env skimr
```

## 📖 Documentation

### 🎯 Basic Usage

1. **Video Analysis**
   - Enter any YouTube URL in the input field
   - Click "Analyze Video" to start processing
   - Monitor real-time progress through the status indicators
   - Explore results across organized tabs (Summary, Analysis, Transcript, etc.)

2. **Interactive Chat**
   - Use the chat interface to ask specific questions about the video
   - Leverage semantic search to find relevant content segments
   - Click on timestamp references to navigate directly to video moments

3. **Content Generation**
   - Generate blog posts, LinkedIn content, or tweets on-demand
   - Utilize web search integration for current information enhancement
   - Customize content style and tone through the settings

4. **Settings Configuration**
   - Select preferred AI model (GPT-4, Gemini, Claude)
   - Adjust creativity level with temperature controls
   - Enable/disable caching for performance optimization
   - Toggle Phase 2 architecture features

### 🔧 Advanced Configuration

#### Model Selection
```python
# Supported models with recommended use cases:
models = {
    "gpt-4o-mini": "Fast, cost-effective for most analyses",
    "gemini-2.0-flash": "Balanced performance and quality", 
    "gemini-2.0-flash-lite": "Ultra-fast responses",
    "claude-3-haiku": "Creative content generation"
}
```

#### Cache Management
- **Automatic TTL**: Configurable expiry (default: 7 days)
- **Memory Limits**: Intelligent cleanup of old entries
- **Selective Clearing**: Per-video cache management
- **Background Refresh**: Proactive cache updates for popular content

#### Performance Tuning
```env
# Optimize for your deployment environment
CACHE_EXPIRY_DAYS=7          # Adjust based on storage capacity
MAX_GUEST_ANALYSES=1         # Control guest user limits
USE_OPTIMIZED_ANALYSIS=true  # Enable Phase 2 architecture
CONNECTION_POOL_SIZE=10      # YouTube API connection pooling
```

## 🏗️ Architecture

Skimr implements a sophisticated **Phase 2 Service-Oriented Architecture** designed for scalability, maintainability, and performance.

### 🧩 System Design Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        UI[Streamlit WebApp]
        Auth[Authentication UI]
        Chat[Chat Interface]
    end
    
    subgraph "Adapter Layer"
        WA[WebApp Adapter]
    end
    
    subgraph "Service Layer"
        AS[Analysis Service]
        CS[Chat Service]
        TS[Transcript Service]
        CTS[Content Service]
        US[User Stats Service]
        AUS[Auth Service]
    end
    
    subgraph "Workflow Layer"
        VAW[Video Analysis Workflow]
        CC[CrewAI Orchestrator]
        LG[LangGraph Agent]
    end
    
    subgraph "Core Layer"
        YC[YouTube Client]
        LM[LLM Manager]
        CM[Cache Manager]
    end
    
    subgraph "Repository Layer"
        CR[Cache Repository]
        AR[Analysis Repository]
    end
    
    subgraph "External APIs"
        YT[YouTube API]
        OAI[OpenAI API]
        SB[Supabase]
        TV[Tavily Search]
    end
    
    UI --> WA
    Auth --> AUS
    Chat --> WA
    WA --> AS
    WA --> CS
    WA --> TS
    WA --> CTS
    AS --> VAW
    CS --> LG
    VAW --> CC
    CC --> LM
    LG --> LM
    TS --> YC
    AS --> CR
    YC --> YT
    LM --> OAI
    AUS --> SB
    CC --> TV
    CR --> AR
```

### 📁 Project Structure

```
skimr/
├── 📁 src/                          # Source code root
│   └── 📁 youtube_analysis/         # Main application package
│       ├── 📁 adapters/             # Interface adapters (Hexagonal Architecture)
│       │   └── webapp_adapter.py    # WebApp interface adapter
│       ├── 📁 core/                 # Core business entities and utilities
│       │   ├── config.py           # Application configuration
│       │   ├── cache_manager.py    # Smart caching implementation
│       │   ├── youtube_client.py   # YouTube API client with pooling
│       │   └── llm_manager.py      # Multi-provider LLM management
│       ├── 📁 services/             # Business logic layer (Domain Services)
│       │   ├── analysis_service.py # Video analysis orchestration
│       │   ├── chat_service.py     # Interactive chat management
│       │   ├── content_service.py  # Content generation services
│       │   ├── transcript_service.py # Transcript processing
│       │   ├── auth_service.py     # Authentication services
│       │   └── user_stats_service.py # User analytics
│       ├── 📁 workflows/            # Business process orchestration
│       │   ├── video_analysis_workflow.py # Main analysis pipeline
│       │   └── crew.py             # CrewAI agent orchestration
│       ├── 📁 repositories/         # Data access layer
│       │   └── cache_repository.py # Cache data persistence
│       ├── 📁 models/              # Domain models and DTOs
│       ├── 📁 ui/                  # User interface components
│       │   ├── components.py       # Streamlit UI components
│       │   ├── helpers.py          # UI utility functions
│       │   └── session_manager.py  # Session state management
│       ├── 📁 utils/               # Shared utilities
│       │   ├── youtube_utils.py    # YouTube-specific utilities
│       │   ├── logging.py          # Centralized logging
│       │   └── cache_utils.py      # Cache utilities
│       ├── 📁 tools/               # Custom AI tools
│       │   └── youtube_tools.py    # CrewAI custom tools
│       └── 📁 config/              # Configuration files
│           ├── agents.yaml         # CrewAI agent definitions
│           └── tasks.yaml          # CrewAI task configurations
├── 📁 analysis_cache/              # Persistent analysis cache
├── 📁 transcript_cache/            # Transcript storage cache
├── 📄 youtube_analysis_webapp.py   # Main Streamlit application
├── 📄 youtube_rag_langgraph.py     # Simplified RAG-only version
├── 📄 requirements.txt             # Python dependencies
├── 📄 Dockerfile                   # Container configuration
└── 📄 .env                         # Environment configuration
```

### 🎨 Design Patterns

#### 1. **Hexagonal Architecture (Ports and Adapters)**
- **Core Domain**: Pure business logic without external dependencies
- **Adapters**: Interface implementations for external systems
- **Ports**: Abstract interfaces defining contracts

#### 2. **Service Layer Pattern**
- **Single Responsibility**: Each service handles specific business domain
- **Dependency Injection**: Services receive dependencies through constructors
- **Interface Segregation**: Clear boundaries between service responsibilities

#### 3. **Repository Pattern**
- **Data Abstraction**: Abstract data access behind repository interfaces
- **Caching Strategy**: Intelligent caching with TTL and memory management
- **Multiple Backends**: Support for different storage mechanisms

#### 4. **Factory Pattern**
- **Service Creation**: Centralized service instantiation
- **Configuration Management**: Dynamic service configuration
- **Dependency Resolution**: Automatic dependency injection

### 🔄 Data Flow Architecture

1. **Request Processing**
   ```
   UI Component → WebApp Adapter → Service Layer → Workflow → Core Services → External APIs
   ```

2. **Caching Strategy**
   ```
   Request → Cache Check → Service Logic → Data Persistence → Response
   ```

3. **Error Handling**
   ```
   Exception → Service Handler → Adapter Translation → UI Display
   ```

### ⚡ Performance Optimizations

#### 1. **Smart Caching System**
- **Multi-Level Caching**: Memory + Persistent storage
- **TTL Management**: Configurable time-to-live
- **Background Refresh**: Proactive cache updates
- **Memory Limits**: Automatic cleanup of old entries

#### 2. **Connection Pooling**
- **HTTP Session Reuse**: Persistent connections to YouTube API
- **Concurrent Requests**: Parallel processing capabilities
- **Rate Limiting**: Intelligent request throttling

#### 3. **Asynchronous Processing**
- **Streaming Responses**: Real-time UI updates
- **Background Tasks**: Non-blocking operations
- **Concurrent Analysis**: Parallel agent execution

## 🛠️ Technology Stack

### 🧠 AI & Machine Learning
- **CrewAI** (0.121.1): Multi-agent orchestration framework
- **LangGraph** (0.4.7): Stateful agent workflow management
- **LangChain** (0.3.25): LLM application development framework
- **OpenAI GPT Models**: Primary language models
- **Anthropic Claude**: Alternative LLM provider
- **Google Gemini**: Additional LLM options
- **FAISS** (1.10.0): Vector similarity search

### 🖥️ Backend & Infrastructure
- **FastAPI** (0.115.12): High-performance async API framework
- **Streamlit** (1.44.1): Interactive web application framework
- **Supabase** (2.15.2): Backend-as-a-Service with authentication
- **Pydantic** (2.11.5): Data validation and settings management

### 🔧 Data Processing
- **youtube-transcript-api** (1.0.3): Transcript extraction
- **yt-dlp** (2025.5.22): Advanced YouTube data extraction
- **pandas** (2.2.3): Data manipulation and analysis
- **numpy** (2.2.6): Numerical computing

### 📊 Search & Analytics
- **Tavily Search**: Web search integration
- **FAISS Vector Store**: Semantic search capabilities
- **Custom Analytics**: User behavior tracking

### 🐳 Deployment & DevOps
- **Docker**: Containerized deployment
- **Multi-stage Builds**: Optimized container images
- **Environment Configuration**: Flexible deployment settings

## 🔧 Configuration Guide

### 📋 Environment Variables Reference

```env
# === Core API Keys ===
OPENAI_API_KEY=sk-...                    # Required for OpenAI models
GEMINI_API_KEY=AI...                     # Required for Google models
ANTHROPIC_API_KEY=sk-ant-...             # Required for Claude models
TAVILY_API_KEY=tvly-...                  # Optional: Enhanced search

# === Authentication (Optional) ===
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJ...                      # Supabase anonymous key

# === Application Settings ===
APP_VERSION=2.0.0                        # Application version
CACHE_EXPIRY_DAYS=7                      # Cache TTL in days
MAX_GUEST_ANALYSES=1                     # Free tier limit
LOG_LEVEL=INFO                           # Logging verbosity

# === Performance Tuning ===
USE_OPTIMIZED_ANALYSIS=true              # Enable Phase 2 features
CONNECTION_POOL_SIZE=10                  # API connection pooling
ENABLE_BACKGROUND_REFRESH=true           # Proactive cache updates

# === Feature Flags ===
ENABLE_AUTH=true                         # User authentication
ENABLE_YOUTUBE_API=true                  # YouTube API integration
ENABLE_WEB_SEARCH=true                   # Tavily search integration
```

### 🎛️ Model Configuration

```python
# Model performance characteristics
MODEL_CONFIGS = {
    "gpt-4.1-mini": {
        "cost": "low",
        "speed": "fast", 
        "quality": "medium",
        "use_case": "General analysis and chat"
    },
    "gemini-2.5-flash": {
        "cost": "low",
        "speed": "very_fast",
        "quality": "medium", 
        "use_case": "General analysis and chat"
    },
    "gemini-2.5-pro": {
        "cost": "high",
        "speed": "slow",
        "quality": "high",
        "use_case": "Content generation and analysis"
    }
}
```

## 📊 API Reference

### 🔌 Core Service Interfaces

#### VideoAnalysisService
```python
class VideoAnalysisService:
    async def analyze_video(
        self, 
        youtube_url: str, 
        settings: AnalysisSettings
    ) -> AnalysisResult:
        """Perform comprehensive video analysis"""
        
    async def get_analysis_status(
        self, 
        video_id: str
    ) -> AnalysisStatus:
        """Get real-time analysis progress"""
```

#### ChatService  
```python
class ChatService:
    async def stream_response(
        self,
        video_id: str,
        user_message: str,
        chat_history: List[Message]
    ) -> AsyncIterator[str]:
        """Stream chat response with RAG context"""
        
    async def clear_agent_cache(self, video_id: str) -> None:
        """Clear cached chat agent for video"""
```

#### ContentService
```python
class ContentService:
    async def generate_single_content(
        self,
        content_type: str,
        analysis_result: AnalysisResult,
        settings: ContentSettings
    ) -> ContentOutput:
        """Generate specific content type on-demand"""
```

### 📝 Data Models

```python
@dataclass
class AnalysisResult:
    video_id: str
    title: str
    category: str
    context_type: str
    summary: str
    analysis: str
    action_plan: Optional[str] = None
    blog_post: Optional[str] = None
    linkedin_post: Optional[str] = None
    tweet: Optional[str] = None
    transcript_data: Optional[TranscriptData] = None
    
@dataclass  
class PerformanceMetrics:
    analysis_time: float
    cache_hit_rate: float
    token_usage: TokenUsage
    active_connections: int
```

## 🤝 Contributing

We welcome contributions from the community! Please follow our contribution guidelines to ensure smooth collaboration.

### 🚀 Getting Started for Contributors

1. **Fork the repository** and create a feature branch
2. **Set up development environment** following the installation guide
3. **Read the architecture documentation** to understand the codebase
4. **Review open issues** for contribution opportunities

### 📋 Development Guidelines

#### Code Style
- **PEP 8 compliance** for Python code formatting
- **Type hints** required for all function signatures
- **Docstrings** for all public methods and classes
- **Comprehensive logging** for debugging and monitoring

#### Testing Requirements
```bash
# Run unit tests
pytest tests/unit/

# Run integration tests  
pytest tests/integration/

# Run performance tests
pytest tests/performance/

# Check code coverage
pytest --cov=src/ tests/
```

#### Pull Request Process
1. **Create feature branch** from `main`
2. **Implement changes** with appropriate tests
3. **Update documentation** as needed
4. **Ensure all tests pass** and coverage is maintained
5. **Submit pull request** with detailed description

### 🏗️ Architecture Contribution Guidelines

When contributing to the architecture:

1. **Follow Service Layer Pattern**: Keep business logic in services
2. **Maintain Interface Contracts**: Don't break existing APIs
3. **Add Comprehensive Tests**: Cover new functionality thoroughly
4. **Update Documentation**: Keep architecture diagrams current
5. **Performance Considerations**: Ensure changes don't degrade performance

### 🐛 Bug Reports

Please include:
- **Detailed reproduction steps**
- **Expected vs actual behavior**
- **Environment information** (Python version, OS, etc.)
- **Relevant log outputs**
- **Screenshots** if applicable

### 💡 Feature Requests

For new features:
- **Describe the problem** being solved
- **Outline the proposed solution**
- **Consider architectural impact**
- **Estimate complexity and effort**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[CrewAI](https://github.com/joaomdmoura/crewAI)**: Revolutionary multi-agent orchestration framework
- **[LangGraph](https://github.com/langchain-ai/langgraph)**: Powerful stateful agent framework
- **[LangChain](https://github.com/langchain-ai/langchain)**: Comprehensive LLM application toolkit
- **[Streamlit](https://streamlit.io/)**: Exceptional rapid web application development
- **[OpenAI](https://openai.com/)**: Advanced language model capabilities
- **[Supabase](https://supabase.com/)**: Outstanding backend-as-a-service platform

## 📞 Support

For support and questions:

- **📚 Documentation**: Check this README and inline code documentation
- **🐛 Issues**: Report bugs via GitHub Issues
- **💬 Discussions**: Join GitHub Discussions for questions
- **📧 Email**: [support@tryskimr.site](mailto:support@tryskimr.site)

## TODO

- [] Optimize the Cache storage (Learn the best way to do this)
- [] Improve the Langgraph agent --> Multi step RAG agent

---

<div align="center">

**Made with ❤️ by Venkatesh**

[🌟 Star us on GitHub](https://github.com/VenkateshDas/crewai_yt_agent) • [🐛 Report a Bug](https://github.com/VenkateshDas/crewai_yt_agent/issues) • [💡 Request a Feature](https://github.com/VenkateshDas/crewai_yt_agent/issues)

</div>

