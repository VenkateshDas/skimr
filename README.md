# YouTube Analysis Crew

A CrewAI implementation for analyzing YouTube videos. This project uses a team of AI agents to fetch, summarize, analyze, and create action plans based on YouTube video content.

## Features

- **Transcription Fetching**: Automatically extracts the transcription from any YouTube video URL
- **Content Summarization**: Creates a comprehensive summary of the video content
- **In-depth Analysis**: Analyzes the video focusing on products, audience, value propositions, and technical details
- **Actionable Advice**: Provides a practical action plan based on the video content
- **Comprehensive Logging**: Detailed logging system for debugging and monitoring
- **Transcription Caching**: Caches transcriptions to improve performance for repeated analyses
- **Robust Error Handling**: Gracefully handles various error scenarios with specific error messages

## Project Structure

This project follows the CrewAI project structure pattern:

```
youtube_analysis/
├── src/
│   └── youtube_analysis/
│       ├── __init__.py
│       ├── crew.py
│       ├── main.py
│       ├── config/
│       │   ├── agents.yaml
│       │   └── tasks.yaml
│       ├── tools/
│       │   ├── __init__.py
│       │   └── youtube_tools.py
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── run_tests.py
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── test_youtube_tools.py
│       │       └── test_youtube_tools_unittest.py
│       └── utils/
│           ├── __init__.py
│           └── logging.py
├── setup.py
├── requirements.txt
└── youtube_analysis_app.py
```

## Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

Run the main script:

```bash
python youtube_analysis_app.py

# Enable debug logging
python youtube_analysis_app.py --debug

# Enable logging to file
python youtube_analysis_app.py --log-to-file

# Train the crew for a specific number of iterations
python youtube_analysis_app.py --train 5

# Directly analyze a specific URL (coming soon)
python youtube_analysis_app.py --url "https://youtu.be/TCGXT7ySco8"

# Display version information
python youtube_analysis_app.py --version
```

When prompted, enter a YouTube URL. The crew will then:

1. Fetch the video transcription
2. Generate a summary
3. Analyze the content
4. Create an actionable plan

The final result will be displayed in the console.

### Supported YouTube URL Formats

The application supports the following YouTube URL formats:

1. Standard format: `https://www.youtube.com/watch?v=TCGXT7ySco8`
2. Short format: `https://youtu.be/TCGXT7ySco8`
3. Mobile format: `https://m.youtube.com/watch?v=TCGXT7ySco8`
4. Embed format: `https://www.youtube.com/embed/TCGXT7ySco8`
5. Shared format: `https://www.youtube.com/v/TCGXT7ySco8`

You can test the URL extraction and transcription fetching with the test script:

```bash
# Test URL extraction only
python -m src.youtube_analysis.tests.tools.test_youtube_tools --extract-only

# Test URL extraction and transcription fetching
python -m src.youtube_analysis.tests.tools.test_youtube_tools

# Test with a specific URL
python -m src.youtube_analysis.tests.tools.test_youtube_tools --url "https://youtu.be/TCGXT7ySco8"
```

## Logging

The application uses a comprehensive logging system that logs information to both the console and optionally to log files:

- Log files are stored in the `logs/` directory (when enabled with `--log-to-file`)
- Each log file is named with the module name and timestamp
- Log levels can be controlled via the `LOG_LEVEL` environment variable or the `--debug` flag
- Available log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- Console output uses color-coding for different log levels for better readability

To set a custom log level:

```bash
# In your .env file
LOG_LEVEL=DEBUG

# Or as an environment variable
export LOG_LEVEL=DEBUG
python youtube_analysis_app.py
```

## Performance Improvements

The application includes several performance optimizations:

1. **Transcription Caching**: Transcriptions are cached in memory to avoid redundant API calls when analyzing the same video multiple times. The cache expires after 1 hour.

2. **Optimized Video ID Extraction**: The URL parsing uses an improved regex pattern that efficiently handles various YouTube URL formats in a single pass.

3. **Efficient Logging**: The logging system prevents duplicate log handlers and uses a dictionary to track configured loggers, reducing memory usage and improving performance.

4. **Type Hints**: The codebase uses type hints throughout, which improves code readability and enables better IDE support and static type checking.

5. **Error Handling**: Specific exception types are caught and handled appropriately, providing better error messages and preventing application crashes.

## Development

### Customizing Agents and Tasks

The agents and tasks are defined in YAML configuration files:

- `src/youtube_analysis/config/agents.yaml`: Defines the roles, goals, and backstories of the agents
- `src/youtube_analysis/config/tasks.yaml`: Defines the tasks assigned to each agent

You can modify these files to customize the behavior of the crew.

### Running Tests

The project includes tests for various components. There are several ways to run the tests:

```bash
# Using the test runner script (recommended)
python -m src.youtube_analysis.tests.run_tests

# Run a specific test module with the test runner
python -m src.youtube_analysis.tests.run_tests --module src.youtube_analysis.tests.tools.test_youtube_tools_unittest

# Using unittest directly
python -m unittest discover -s src/youtube_analysis/tests

# Run a specific test module directly
python -m src.youtube_analysis.tests.tools.test_youtube_tools_unittest

# Run the command-line test script
python -m src.youtube_analysis.tests.tools.test_youtube_tools
```

## Requirements

- Python 3.8+
- OpenAI API key
- Internet connection to access YouTube

## Notes

- The YouTube transcription API may not work for all videos, especially those without captions
- For long videos, the analysis may take some time to complete
- The quality of the analysis depends on the quality of the video transcription
- The transcription cache is in-memory only and will be cleared when the application is restarted 