# YouTube Video Analyzer

A Streamlit application that analyzes YouTube videos, extracts transcripts, and provides AI-powered insights using Crewai and Langgraph agents.

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

## Scope

This application is designed for:
- Researchers and students gathering information from educational videos
- Content creators analyzing competitor videos
- Professionals seeking to quickly extract insights from lengthy presentations
- Anyone looking to save time by getting a comprehensive overview before watching
- Users who want to interact with video content via a conversational interface

## Features

- Extract and display YouTube video transcripts with time-stamped navigation
- Analyze video content using AI-powered CrewAI agents
- Category classification with visual color coding
- Context tagging (Tutorial, Review, How-To Guide, etc.)
- Comprehensive video summarization with key points
- Deep content analysis with actionable insights
- Interactive chat interface to ask questions about the video
- User authentication with Supabase
- Caching system for faster repeated analysis
- Modern, responsive UI with dark mode
- Embedded video player alongside analysis
- Streaming responses for enhanced user experience
- Full report generation with formatted sections

## Setup

### Prerequisites

- Python 3.8+
- OpenAI API key for language models
- A Google account for YouTube Data API access
- A Supabase account for authentication (optional)

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
   # OpenAI API key
   OPENAI_API_KEY=your_openai_api_key
   
   # YouTube API settings
   YOUTUBE_API_KEY=your_youtube_api_key
   
   # Supabase settings (for authentication)
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   
   # Optional settings
   CACHE_EXPIRY_DAYS=7
   LOG_LEVEL=INFO
   ```

### Getting a YouTube API Key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the YouTube Data API v3
4. Create credentials (API Key)
5. Copy the API key to your `.env` file

### Running the Application

```bash
streamlit run youtube_analysis_webapp.py
```

## Usage

1. Enter a YouTube URL in the input field
2. Click "Analyze Video" to process the transcript
3. View the analysis results across five tabs:
   - Full Report (comprehensive overview)
   - Summary (concise video summary)
   - Analysis (detailed content breakdown) 
   - Action Plan (recommended next steps)
   - Transcript (full transcript with timestamps)
4. Use the chat interface to ask questions about the video content
5. Click on timestamps to navigate to specific parts of the video

## CrewAI Integration

This application uses CrewAI to create a team of AI agents that work together to analyze YouTube videos:

- **Classifier Agent**: Determines the video category and content context type
- **Summarizer Agent**: Creates a concise summary of the video content
- **Analyzer Agent**: Performs in-depth analysis of the video content
- **Advisor Agent**: Generates actionable insights and recommendations
- **Report Writer Agent**: Produces a comprehensive report combining all analysis

## Project Structure

```
├── youtube_analysis_webapp.py  # Main Streamlit application
├── src/
│   ├── youtube_analysis/
│   │   ├── __init__.py         # Package initialization
│   │   ├── main.py             # Command-line interface for the analyzer
│   │   ├── analysis.py         # Video analysis functionality
│   │   ├── auth.py             # Authentication functionality
│   │   ├── chat.py             # Interactive chat implementation
│   │   ├── config.py           # Configuration settings
│   │   ├── crew.py             # CrewAI agent definitions and tasks
│   │   ├── transcript.py       # Transcript processing
│   │   ├── ui.py               # UI components and styling
│   │   ├── api/                # API integrations
│   │   ├── config/             # Configuration files (agents.yaml, tasks.yaml)
│   │   ├── tools/              # Custom tools for agents
│   │   ├── tests/              # Unit and integration tests
│   │   ├── utils/
│   │   │   ├── youtube_utils.py  # YouTube API utilities
│   │   │   ├── cache_utils.py    # Caching functionality
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

### YouTube API Issues

If you encounter errors with the pytube library (common due to YouTube API changes), make sure you have set up the YouTube Data API key as described above. The application will fall back to using the official YouTube API when pytube fails.

### Authentication Issues

Make sure your Supabase credentials are correct and that you have set up authentication in your Supabase project.

### LLM Connection Issues

If you experience issues with OpenAI API connections, verify your API key and check your rate limits.

### Chat Functionality Unavailable

If the chat interface shows "Chat Unavailable," check that your OpenAI API key is properly configured and that the transcript was successfully processed.

## License

MIT

## Docker Deployment

This application can be easily deployed using Docker, which ensures consistent environments and simplifies the setup process.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Quick Start

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd youtube-video-analyzer
   ```

2. Create an environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file with your API keys and configuration.

4. Deploy the application:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

5. Access the application at http://localhost:8501

### Development Mode

To run the application in development mode with live logs:

```bash
chmod +x dev.sh
./dev.sh
```

### Docker Image Details

The application uses a multi-stage build process to keep the Docker image slim:
- Base image: Python 3.10 slim
- Virtual environment for dependency isolation
- Persistent volumes for database and output files
- Proper handling of environment variables

### Volume Mounts

- `./output:/app/output`: Stores generated analysis results
- `./db:/app/db`: Stores database files
- `./.env:/app/.env`: Mounts your environment configuration

### Customizing the Deployment

You can customize the deployment by editing the `docker-compose.yml` file. For example, to change the port mapping:

```yaml
ports:
  - "8080:8501"  # Map container port 8501 to host port 8080
``` 