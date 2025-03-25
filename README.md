# YouTube Video Analyzer

A Streamlit application that analyzes YouTube videos, extracts transcripts, and provides AI-powered insights using CrewAI and LangGraph agents.

## Problem Statement

Content creators and viewers face several challenges when consuming YouTube videos:
- Videos are time-consuming to watch completely
- It's difficult to determine if a video has the information you need without watching it
- Finding specific information within a video requires manual scrubbing
- Extracting actionable insights from educational content can be challenging
- There's no easy way to interact with video content via natural language

## Solution

YouTube Video Analyzer addresses these challenges by providing:
- AI-powered analysis of video content for quick understanding
- Intelligent categorization and context tagging
- Interactive chat interface that allows asking questions about the video
- Time-stamped transcripts for easy navigation
- Actionable insights and summaries that distill key information
- Content generation tools for blog posts, LinkedIn posts, and tweets

## Features

- Extract and display YouTube video transcripts with time-stamped navigation
- Analyze video content using AI-powered CrewAI agents
- Category classification with visual color coding
- Context tagging (Tutorial, Review, How-To Guide, etc.)
- Comprehensive video summarization with key points
- Deep content analysis with actionable insights
- Interactive chat interface using LangGraph agents to ask questions about the video
- Video highlights generation with thumbnails and time markers
- Content repurposing tools (blog post, LinkedIn post, tweet generation)
- Search tool integration for adding current information to content
- Caching system for faster repeated analysis
- Modern, responsive UI with dark mode support
- Embedded video player alongside analysis
- Streaming responses for enhanced user experience

## Technologies Used

- **Streamlit**: Web application framework
- **CrewAI**: Framework for orchestrating role-playing AI agents
- **LangGraph**: Framework for building stateful, multi-agent applications with LLMs
- **LangChain**: Framework for developing applications powered by language models
- **OpenAI GPT Models**: Default language models for analysis and chat
- **Anthropic Claude Models**: Alternative language models (configurable)
- **Google Gemini Models**: Alternative language models (configurable)
- **Tavily Search**: Web search tool for gathering current information
- **YouTube Transcript API**: For extracting video transcripts
- **FAISS**: Vector database for semantic search in chat functionality

## Agent Architecture

This application uses two main AI frameworks:

### CrewAI Agents

The CrewAI team analyzes YouTube videos with these specialized agents:

- **Classifier Agent**: Determines video category and content context type
- **Analyzer Agent**: Performs in-depth analysis and creates actionable plans
- **Blog Writer Agent**: Creates comprehensive blog posts with web search integration
- **LinkedIn Post Writer Agent**: Crafts professional LinkedIn posts 
- **Tweet Writer Agent**: Generates engaging tweets in the style of relevant influencers

### LangGraph Agents

For interactive chat capabilities, the application uses LangGraph with:

- **RAG-enabled Chat Agent**: Retrieves relevant transcript segments to answer questions about the video content
- **ReAct Agent**: Uses reasoning and action to explore video content interactively

## Setup

### Prerequisites

- Python 3.8+
- OpenAI API key for language models
- (Optional) Anthropic API key for Claude models
- (Optional) Google API key for Gemini models
- A Tavily API key for search functionality

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/youtube-video-analyzer.git
   cd youtube-video-analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with the following variables:
   ```
   # OpenAI API key (required)
   OPENAI_API_KEY=your_openai_api_key
   
   # Alternative model API keys (optional)
   GEMINI_API_KEY=your_gemini_api_key
   
   # Search API key (optional but recommended)
   TAVILY_API_KEY=your_tavily_api_key
   
   # Optional settings
   CACHE_EXPIRY_DAYS=7
   LOG_LEVEL=INFO
   ```

### Running the Application

```bash
streamlit run youtube_analysis_webapp.py
```

For the simplified RAG-only version:
```bash
streamlit run youtube_rag_langgraph.py
```

## Usage

1. Enter a YouTube URL in the input field
2. Click "Analyze Video" to process the transcript
3. View the analysis results across tabs:
   - Full Report (comprehensive overview)
   - Summary (concise video summary)
   - Analysis (detailed content breakdown) 
   - Action Plan (recommended next steps)
   - Transcript (full transcript with timestamps)
   - Highlights (key moments with thumbnails)
4. Use the chat interface to ask questions about the video content
5. Click on timestamps to navigate to specific parts of the video
6. Generate additional content like blog posts, LinkedIn posts, or tweets

## Project Structure

```
├── youtube_analysis_webapp.py    # Main Streamlit application
├── youtube_rag_langgraph.py      # Simplified RAG-only version
├── src/
│   ├── youtube_analysis/
│   │   ├── __init__.py           # Package initialization
│   │   ├── main.py               # Command-line interface
│   │   ├── analysis.py           # Video analysis functionality
│   │   ├── auth.py               # Authentication functionality
│   │   ├── chat.py               # Interactive chat implementation
│   │   ├── config.py             # Configuration settings
│   │   ├── crew.py               # CrewAI agent definitions and tasks
│   │   ├── transcript.py         # Transcript processing
│   │   ├── ui.py                 # UI components and styling
│   │   ├── api/                  # API integrations
│   │   ├── config/               # Configuration files (agents.yaml, tasks.yaml)
│   │   ├── tools/                # Custom tools for agents
│   │   ├── tests/                # Unit and integration tests
│   │   ├── utils/
│   │   │   ├── youtube_utils.py  # YouTube API utilities
│   │   │   ├── cache_utils.py    # Caching functionality
│   │   │   ├── video_highlights.py # Video highlights extraction
│   │   │   └── logging.py        # Logging utilities
```

## Advanced Features

### Context-Aware Chat with Vector Search

The chat functionality uses FAISS vectorstore to index the video transcript, enabling context-aware responses to user questions. When timestamps are available in the transcript, the chat interface can also reference specific moments in the video.

### Visual Category and Context Tagging

Videos are categorized into primary categories (Technology, Business, Education, etc.) and context types (Tutorial, Review, Interview, etc.), each with distinctive color coding for easy visual identification.

### Time-Synchronized Transcript Navigation

The transcript display includes timestamps that can be clicked to navigate directly to that point in the embedded video player.

### AI Streaming Responses

The application supports streaming responses from compatible LLMs, providing a more interactive experience when analyzing videos or chatting with the AI.

### Custom Agents and Tasks

The CrewAI configuration can be customized through YAML files in the config directory to adjust agent behaviors and task definitions.

## Troubleshooting

The CrewAI agents and tasks can be customized through YAML files:

- `src/youtube_analysis/config/agents.yaml`: Agent definitions with roles, goals, and backstories
- `src/youtube_analysis/config/tasks.yaml`: Task definitions with detailed instructions and expected outputs

## Models and Configuration

The application supports multiple LLM providers:

- OpenAI GPT models (default: gpt-4o-mini)
- Anthropic Claude models
- Google Gemini models

Change the model in the web interface or modify the default in `src.youtube_analysis.crew.py`.

## Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewAI) for the agent orchestration framework
- [LangGraph](https://github.com/langchain-ai/langgraph) for the interactive agent framework
- [LangChain](https://github.com/langchain-ai/langchain) for LLM application tools
- [Streamlit](https://streamlit.io/) for the web application framework

## License

MIT

