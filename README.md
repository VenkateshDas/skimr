# YouTube Video Analyzer

A Streamlit application that analyzes YouTube videos, extracts transcripts, and provides insights using AI.

## Features

- Extract and display YouTube video transcripts with timestamps
- Analyze video content using AI
- User authentication with Supabase
- Caching system for faster repeated analysis
- Interactive chat interface to ask questions about the video

## Setup

### Prerequisites

- Python 3.8+
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
3. View the analysis results and interact with the video content

## Project Structure

```
├── youtube_analysis_webapp.py  # Main Streamlit application
├── src/
│   ├── youtube_analysis/
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication functionality
│   │   ├── config.py           # Configuration settings
│   │   ├── ui.py               # UI components
│   │   ├── utils/
│   │   │   ├── youtube_utils.py  # YouTube API utilities
│   │   │   └── logging.py        # Logging utilities
```

## Troubleshooting

### YouTube API Issues

If you encounter errors with the pytube library (common due to YouTube API changes), make sure you have set up the YouTube Data API key as described above. The application will fall back to using the official YouTube API when pytube fails.

### Authentication Issues

Make sure your Supabase credentials are correct and that you have set up authentication in your Supabase project.

## License

MIT 