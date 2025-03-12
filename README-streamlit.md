# YouTube Analysis Streamlit App

A beautiful web interface for analyzing YouTube videos using AI, powered by CrewAI and Streamlit.

![YouTube Analysis App Screenshot](https://i.imgur.com/example.png)

## Features

- **User-friendly Interface**: Clean, intuitive design for easy interaction
- **Real-time Progress Tracking**: Visual feedback during the analysis process
- **Beautiful Results Display**: Well-formatted output with tabs for different sections
- **Token Usage Visualization**: Charts and tables showing LLM token consumption
- **Customizable Settings**: Choose different models and parameters
- **Video Thumbnail Preview**: Visual identification of the analyzed video
- **Markdown Rendering**: Properly formatted output for better readability

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/youtube-analysis-app.git
   cd youtube-analysis-app
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements-streamlit.txt
   ```

3. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```
   
   Or create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

1. Start the Streamlit app:
   ```bash
   streamlit run youtube_analysis_streamlit.py
   ```

2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. Enter a YouTube URL in the input field and click "Analyze Video"

4. Wait for the analysis to complete - you'll see a progress bar and status updates

5. Explore the results in the tabbed interface:
   - **Summary**: Overview of the video content
   - **Analysis**: Detailed analysis of the video
   - **Action Plan**: Suggested actions based on the video content
   - **Transcript**: Full transcript of the video
   - **Raw Output**: Unformatted output from the AI analysis

## Customization

You can customize the analysis by adjusting the settings in the sidebar:

- **LLM Model**: Choose between different OpenAI models
- **Temperature**: Adjust the creativity/randomness of the AI responses
- **Debug Mode**: Enable for more detailed logging

## Requirements

- Python 3.9+
- OpenAI API key
- Internet connection for accessing YouTube videos

## How It Works

1. The app extracts the video ID from the provided YouTube URL
2. It fetches the transcript of the video using the YouTube Transcript API
3. The transcript is processed by a CrewAI crew of specialized AI agents
4. Each agent performs a specific task (transcription, summarization, analysis, action planning)
5. The results are formatted and displayed in the Streamlit interface

## Troubleshooting

- **API Key Issues**: Ensure your OpenAI API key is correctly set and has sufficient credits
- **Transcript Errors**: Some YouTube videos may not have available transcripts
- **Connection Problems**: Check your internet connection if the app fails to fetch video data

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewAI) for the AI agent framework
- [Streamlit](https://streamlit.io/) for the web interface
- [YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api) for transcript extraction 