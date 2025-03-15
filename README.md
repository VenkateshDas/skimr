# YouTube Video Analyzer

A powerful AI-powered application that analyzes YouTube videos to provide insights, summaries, and action plans.

## Features

- **Video Classification**: Automatically categorize videos into topics like Technology, Business, Education, and more.
- **Comprehensive Summary**: Get a TL;DR and key points to quickly understand the video's content.
- **In-depth Analysis**: Understand the main concepts, target audience, and value propositions.
- **Action Plan**: Receive practical, actionable steps to implement the knowledge from the video.
- **Full Report**: Get a complete markdown report combining all analyses.
- **Enhanced RAG Chatbot**: Chat with the video content and ask specific questions about the material. The chatbot is aware of the video title and description for more contextual responses.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/youtube-video-analyzer.git
   cd youtube-video-analyzer
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   Create a `.env` file in the root directory with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   LLM_MODEL=gpt-4o-mini  # or gpt-4o
   LLM_TEMPERATURE=0.2
   LOG_LEVEL=INFO
   YOUTUBE_API_KEY=your_youtube_api_key  # Optional, for fetching video metadata
   ```

## Usage

### Web Application

Run the Streamlit web application for video analysis:

```bash
streamlit run youtube_analysis_webapp.py
```

This will start the web application, which you can access at http://localhost:8501.

### RAG Chatbot

Run the RAG chatbot to chat with video content:

```bash
streamlit run youtube_rag_chatbot.py
```

This will start the chatbot application, which you can access at http://localhost:8501.

### Using the Run Script

For convenience, you can use the run script:

```bash
# Run the web application
python run.py webapp

# Run the RAG chatbot
python run.py chatbot

# Run the command line interface
python run.py cli --url "https://youtu.be/your_video_id"
```

### Command Line Interface

You can also use the command line interface directly:

```bash
python -m src.youtube_analysis --url "https://youtu.be/your_video_id"
```

Additional command line options:
- `--mode`: Analysis mode (default: "full")
- `--model`: LLM model to use (default: from environment)
- `--temperature`: Temperature setting for the LLM (default: from environment)
- `--verbose`: Enable verbose logging
- `--output-format`: Output format (json, text, markdown)
- `--output-dir`: Directory to save results

## Project Structure

```
youtube-video-analyzer/
├── src/
│   └── youtube_analysis/
│       ├── __init__.py
│       ├── __main__.py
│       ├── crew.py
│       ├── main.py
│       ├── config/
│       │   ├── agents.yaml
│       │   └── tasks.yaml
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           └── youtube_utils.py
├── youtube_analysis_webapp.py
├── youtube_rag_chatbot.py
├── run.py
├── requirements.txt
└── README.md
```

## How It Works

### Video Analysis

1. **Transcript Extraction**: The application extracts the transcript from the YouTube video.
2. **Classification**: An AI agent classifies the video content into appropriate categories.
3. **Summarization**: Another agent creates a comprehensive summary of the video content.
4. **Analysis**: The content is analyzed to identify key concepts, target audience, and value propositions.
5. **Action Plan**: Based on the analysis, an actionable plan is created.
6. **Report Generation**: A complete report is generated combining all the analyses.

### Enhanced RAG Chatbot

1. **Transcript Extraction**: The application extracts the transcript from the YouTube video.
2. **Metadata Retrieval**: The system fetches the video title and description for context.
3. **Text Chunking**: The transcript is split into smaller, manageable chunks.
4. **Vector Embedding**: Each chunk is converted into a vector embedding using OpenAI's embedding model.
5. **Agent Creation**: An AI agent is created with tools to search the transcript and access video metadata.
6. **Contextual Responses**: When you ask a question, the agent determines whether to use its general knowledge or search the video content, providing contextually accurate answers.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 