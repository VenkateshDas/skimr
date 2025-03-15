import os
import sys
import re
import time
import streamlit as st
from typing import Optional, Dict, Any, Tuple, List, Sequence, TypedDict, Annotated
import pandas as pd
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the YouTube Analysis modules
from src.youtube_analysis.utils.youtube_utils import get_transcript, extract_video_id, get_video_info
from src.youtube_analysis.crew import YouTubeAnalysisCrew
from src.youtube_analysis.utils.logging import setup_logger

# LangGraph and LangChain imports for chat functionality
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage
from langgraph.prebuilt import create_react_agent

# Configure logging
logger = setup_logger("streamlit_app", log_level="INFO")

# App version
__version__ = "1.0.0"

# Define the state for our chat agent
class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    video_id: Annotated[str, "The YouTube video ID"]
    youtube_url: Annotated[str, "The YouTube video URL"]
    title: Annotated[str, "The title of the video"]
    description: Annotated[str, "The description of the video"]

# Set page configuration
st.set_page_config(
    page_title="YouTube Video Analyzer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_css():
    """Load custom CSS for better styling."""
    st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    
    /* Main Styles */
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        color: #FF0000;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #FFFFFF;
        margin: 2rem 0 1rem 0;
        text-align: center;
    }
    .info-text {
        font-size: 1.1rem;
        color: #CCCCCC;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    /* Card Styles */
    .card {
        border-radius: 12px;
        border: none;
        padding: 1.8rem;
        background-color: #1E1E1E;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        margin-bottom: 1.5rem;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 100%;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
    }
    .card h3 {
        font-size: 1.4rem;
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 1rem;
    }
    .card p {
        color: #BBBBBB;
        font-size: 1rem;
        line-height: 1.5;
    }
    .card-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        display: block;
    }
    
    /* Status Indicators */
    .success-box {
        padding: 1rem;
        background-color: rgba(52, 168, 83, 0.15);
        border-radius: 8px;
        border-left: 4px solid #34A853;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    .warning-box {
        padding: 1rem;
        background-color: rgba(249, 168, 37, 0.15);
        border-radius: 8px;
        border-left: 4px solid #F9A825;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    .error-box {
        padding: 1rem;
        background-color: rgba(229, 57, 53, 0.15);
        border-radius: 8px;
        border-left: 4px solid #E53935;
        margin: 1rem 0;
        color: #FFFFFF;
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #FF0000;
    }
    
    /* Category Badge */
    .category-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .category-technology {
        background-color: rgba(21, 101, 192, 0.2);
        color: #64B5F6;
    }
    .category-business {
        background-color: rgba(46, 125, 50, 0.2);
        color: #81C784;
    }
    .category-education {
        background-color: rgba(230, 81, 0, 0.2);
        color: #FFB74D;
    }
    .category-health {
        background-color: rgba(123, 31, 162, 0.2);
        color: #CE93D8;
    }
    .category-science {
        background-color: rgba(0, 131, 143, 0.2);
        color: #4DD0E1;
    }
    .category-finance {
        background-color: rgba(57, 73, 171, 0.2);
        color: #9FA8DA;
    }
    .category-personal {
        background-color: rgba(216, 67, 21, 0.2);
        color: #FFAB91;
    }
    .category-entertainment {
        background-color: rgba(130, 119, 23, 0.2);
        color: #DCE775;
    }
    .category-other {
        background-color: rgba(69, 90, 100, 0.2);
        color: #B0BEC5;
    }
    
    /* Metadata */
    .metadata {
        font-size: 0.85rem;
        color: #999999;
        margin-top: 1rem;
        text-align: right;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 8px 8px 0px 0px;
        padding: 0px 16px;
        background-color: #2A2A2A;
        color: #CCCCCC;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FF0000 !important;
        color: white !important;
    }
    
    /* Button styling */
    .stButton button {
        background-color: #FF0000;
        color: white;
        font-weight: 600;
        border-radius: 30px;
        padding: 0.6rem 2rem;
        border: none;
        transition: all 0.3s ease;
        font-size: 1.1rem;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #D50000;
        box-shadow: 0 4px 12px rgba(255, 0, 0, 0.3);
        transform: translateY(-2px);
    }
    
    /* Input field styling */
    .stTextInput input {
        border-radius: 30px;
        border: 2px solid #333333;
        padding: 1rem 1.5rem;
        background-color: #1A1A1A;
        color: #FFFFFF;
        transition: all 0.3s ease;
        font-size: 1.1rem;
    }
    .stTextInput input:focus {
        border-color: #FF0000;
        box-shadow: 0 0 0 2px rgba(255, 0, 0, 0.2);
    }
    .stTextInput input::placeholder {
        color: #777777;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1A1A1A;
        border-right: 1px solid #333333;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #FFFFFF;
    }
    
    /* Text area styling */
    .stTextArea textarea {
        background-color: #1A1A1A;
        color: #CCCCCC;
        border: 1px solid #333333;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #FF0000 #FF0000 transparent !important;
    }
    
    /* Feature grid */
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin: 2rem 0;
    }
    
    /* Step grid */
    .step-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin: 2rem 0;
    }
    
    /* Chat container */
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 60vh;
        overflow-y: auto;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #1A1A1A;
        border-radius: 12px;
        border: 1px solid #333333;
    }
    
    /* Chat message */
    .chat-message {
        display: flex;
        margin-bottom: 1rem;
    }
    
    .chat-message.user {
        justify-content: flex-end;
    }
    
    .chat-message.bot {
        justify-content: flex-start;
    }
    
    .message-content {
        padding: 0.8rem 1.2rem;
        border-radius: 18px;
        max-width: 80%;
        word-wrap: break-word;
    }
    
    .user .message-content {
        background-color: #FF0000;
        color: white;
        border-bottom-right-radius: 4px;
    }
    
    .bot .message-content {
        background-color: #2A2A2A;
        color: white;
        border-bottom-left-radius: 4px;
    }
    
    /* Streamlit chat specific styling */
    [data-testid="stChatMessage"] {
        margin-bottom: 1rem;
    }
    
    /* Make sure the chat input is always visible at the bottom */
    [data-testid="stChatInput"] {
        position: sticky;
        bottom: 0;
        background-color: #121212;
        padding: 1rem 0;
        z-index: 100;
        margin-top: 1rem;
        border-top: 1px solid #333333;
    }
    
    /* Ensure the chat container scrolls properly */
    [data-testid="stVerticalBlock"] > div:has([data-testid="stChatMessage"]) {
        overflow-y: auto;
        max-height: 60vh;
        padding-right: 1rem;
    }
    
    @media (max-width: 768px) {
        .feature-grid {
            grid-template-columns: 1fr;
        }
        .step-grid {
            grid-template-columns: 1fr 1fr;
        }
    }
</style>
""", unsafe_allow_html=True)

def get_category_class(category: str) -> str:
    """
    Get the CSS class for a category badge.
    
    Args:
        category: The category name
        
    Returns:
        The CSS class for the category badge
    """
    category = category.lower()
    if "technology" in category:
        return "category-technology"
    elif "business" in category:
        return "category-business"
    elif "education" in category:
        return "category-education"
    elif "health" in category:
        return "category-health"
    elif "science" in category:
        return "category-science"
    elif "finance" in category:
        return "category-finance"
    elif "personal" in category:
        return "category-personal"
    elif "entertainment" in category:
        return "category-entertainment"
    else:
        return "category-other"

def extract_youtube_thumbnail(video_id: str) -> str:
    """
    Get the thumbnail URL for a YouTube video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The URL of the video thumbnail
    """
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def validate_youtube_url(url: str) -> bool:
    """
    Validate if the provided URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if the URL is valid, False otherwise
    """
    if not url:
        return False
    
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+'
    return bool(re.match(youtube_pattern, url))

def extract_category(output: str) -> str:
    """
    Extract the category from the classification output.
    
    Args:
        output: The classification output
        
    Returns:
        The extracted category
    """
    # Look for category names in the output
    categories = [
        "Technology", "Business", "Education", "Health & Wellness", 
        "Science", "Finance", "Personal Development", "Entertainment"
    ]
    
    for category in categories:
        if category in output:
            return category
    
    # If no category is found, check for "Other"
    if "Other" in output:
        # Try to extract the specified category
        match = re.search(r"Other \(([^)]+)\)", output)
        if match:
            return f"Other: {match.group(1)}"
        return "Other"
    
    return "Uncategorized"

# Functions for chat functionality
def create_vectorstore(text: str) -> FAISS:
    """
    Create a vector store from the text.
    
    Args:
        text: The text to create the vector store from
        
    Returns:
        A FAISS vector store
    """
    # Split the text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_text(text)
    
    # Create embeddings
    embeddings = OpenAIEmbeddings()
    
    # Create a FAISS vector store (in-memory)
    vectorstore = FAISS.from_texts(
        texts=chunks,
        embedding=embeddings
    )
    
    logger.info(f"Created FAISS vector store with {len(chunks)} chunks")
    
    return vectorstore

def create_agent_graph(vectorstore: FAISS, video_metadata: Dict[str, Any]):
    """
    Create a LangGraph agent with tools for handling YouTube content queries.
    
    Args:
        vectorstore: The vector store to use for retrieval
        video_metadata: Metadata about the YouTube video
        
    Returns:
        A LangGraph agent
    """
    # Create language model
    model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(temperature=0.2, model_name=model_name)
    
    # Create retriever tool
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    
    # Define the search tool with updated retriever usage
    search_tool = Tool(
        name="YouTube_Video_Search",
        description=f"Useful for searching information in the YouTube video transcript. Use this tool when the user asks about the content of the video with ID {video_metadata['video_id']}.",
        func=lambda query: "\n\n".join([doc.page_content for doc in retriever.invoke(query)])
    )
    
    # Define the video info tool
    video_info_tool = Tool(
        name="YouTube_Video_Info",
        description="Provides basic information about the YouTube video being analyzed.",
        func=lambda _: f"Video URL: {video_metadata['youtube_url']}\nVideo ID: {video_metadata['video_id']}\nTitle: {video_metadata.get('title', 'Unknown')}\nDescription: {video_metadata.get('description', 'No description available')}"
    )
    
    # Create tools list
    tools = [search_tool, video_info_tool]
    
    # Create system message with video description
    video_title = video_metadata.get('title', 'Unknown')
    video_description = video_metadata.get('description', 'No description available')
    
    system_message_content = f"""You are an AI assistant that helps users understand YouTube video content.
You have access to the transcript of a YouTube video titled "{video_title}" with the following description:

DESCRIPTION:
{video_description}

You can answer questions about this video and also handle general questions not related to the video.

For questions about the video content, use the YouTube_Video_Search tool to find relevant information in the transcript.
For questions about the video itself (URL, ID, title, description), use the YouTube_Video_Info tool.
For general questions not related to the video, use your own knowledge to answer.

Always be helpful, accurate, and concise in your responses.
If you don't know the answer to a question about the video, say so rather than making up information.

IMPORTANT: Use the chat history to maintain context of the conversation. Refer back to previous questions and answers when relevant.
"""
    
    # Create a proper prompt template with the system message
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message_content),
        ("placeholder", "{messages}"),
    ])
    
    # Create the agent using LangGraph's create_react_agent with the correct signature
    try:
        # First attempt: Try with llm and tools as positional, prompt as keyword
        agent_executor = create_react_agent(llm, tools, prompt=prompt)
        logger.info("Created agent with prompt as keyword argument")
    except TypeError as e:
        try:
            # Second attempt: Try with just llm and tools
            agent_executor = create_react_agent(llm, tools)
            logger.info("Created agent without prompt template")
        except Exception as e:
            # If that fails too, log the error and try a different approach
            logger.error(f"Error creating agent with just llm and tools: {str(e)}")
            # Final attempt: Try with a dictionary of all parameters
            agent_executor = create_react_agent(
                llm=llm, 
                tools=tools
            )
            logger.info("Created agent with named parameters")
    except Exception as e:
        logger.error(f"Unexpected error creating agent: {str(e)}")
        raise
    
    # Return the agent executor
    return agent_executor

def setup_chat_for_video(youtube_url: str, transcript: str) -> Dict[str, Any]:
    """
    Set up the chat functionality for a YouTube video.
    
    Args:
        youtube_url: The URL of the YouTube video
        transcript: The transcript of the video
        
    Returns:
        A dictionary containing the chat setup details
    """
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        
        # Get video information (title, description, etc.)
        try:
            video_info = get_video_info(video_id)
            logger.info(f"Retrieved video info for chat: {video_info['title']}")
        except Exception as e:
            logger.error(f"Error retrieving video info for chat: {str(e)}")
            # Provide default video info if retrieval fails
            video_info = {
                "title": f"YouTube Video {video_id}",
                "description": "No description available due to API error."
            }
            logger.info(f"Using default video info for chat with {video_id}")
        
        # Create vector store
        vectorstore = create_vectorstore(transcript)
        logger.info("Successfully created vector store for chat")
        
        # Create video metadata
        video_metadata = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available")
        }
        
        # Create agent
        agent = create_agent_graph(vectorstore, video_metadata)
        logger.info("Successfully created agent for chat")
        
        # Create thread ID for persistence
        thread_id = f"thread_{video_id}_{int(time.time())}"
        
        # Initialize chat messages with a welcome message
        if "chat_messages" not in st.session_state or not st.session_state.chat_messages:
            st.session_state.chat_messages = [
                {
                    "role": "assistant", 
                    "content": f"Hello! I'm your AI assistant for the video \"{video_info.get('title', 'this YouTube video')}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                }
            ]
        
        # Return chat setup details
        return {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available"),
            "agent": agent,
            "thread_id": thread_id
        }
    except Exception as e:
        logger.error(f"Error setting up chat: {str(e)}")
        return None

def display_chat_interface(chat_details: Dict[str, Any]):
    """
    Display the chat interface for interacting with the video content.
    
    Args:
        chat_details: The chat setup details
    """
    # Initialize chat messages if not exists
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Create a container for the chat interface
    chat_container = st.container()
    
    # Create a container for the input at the bottom
    input_container = st.container()
    
    # Chat input (at the bottom)
    with input_container:
        prompt = st.chat_input("Ask a question about the video...", key="chat_input")
    
    # Display chat messages in the chat container
    with chat_container:
        # Display existing messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Handle new message
        if prompt:
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                try:
                    # Get the agent and thread ID
                    agent = chat_details["agent"]
                    thread_id = chat_details["thread_id"]
                    
                    # Convert previous messages to the format expected by LangGraph
                    messages = []
                    for msg in st.session_state.chat_messages:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            messages.append(AIMessage(content=msg["content"]))
                    
                    # Add the current user message if not already added
                    if not messages or messages[-1].type != "human":
                        messages.append(HumanMessage(content=prompt))
                    
                    # Invoke the agent with the thread ID for memory persistence
                    response = agent.invoke(
                        {"messages": messages},
                        config={"configurable": {"thread_id": thread_id}},
                    )
                    
                    # Extract the final answer
                    final_message = response["messages"][-1]
                    answer = final_message.content
                    
                    # Display response
                    message_placeholder.markdown(answer)
                    
                    # Add AI response to chat history
                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    logger.error(f"Error getting chat response: {str(e)}")
                    message_placeholder.markdown("Sorry, I encountered an error while processing your question. Please try again.")

def format_transcript_with_clickable_timestamps(transcript_list, video_id, jump_in_embedded=False):
    """
    Format transcript with clickable timestamps that jump to specific points in the video.
    
    Args:
        transcript_list: List of transcript items with start times and text
        video_id: YouTube video ID
        jump_in_embedded: Whether to jump to timestamp in embedded video or open in new tab
        
    Returns:
        HTML string with clickable timestamps
    """
    html_parts = []
    html_parts.append('<div class="transcript-container" style="height: 400px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; padding: 10px; background-color: #1A1A1A; border-radius: 8px; border: 1px solid #333;">')
    
    for item in transcript_list:
        # Convert seconds to MM:SS format
        seconds = int(item['start'])
        minutes, seconds = divmod(seconds, 60)
        timestamp = f"{minutes:02d}:{seconds:02d}"
        
        # Create clickable timestamp that jumps to that point in the video
        timestamp_seconds = int(item['start'])
        html_parts.append(f'<div class="transcript-line" style="margin-bottom: 8px;">')
        
        if jump_in_embedded:
            # Create a link that uses JavaScript to control the embedded player
            html_parts.append(f'<a href="javascript:void(0)" onclick="document.querySelector(\'iframe\').contentWindow.postMessage(\'{{\"event\":\"command\",\"func\":\"seekTo\",\"args\":[{timestamp_seconds},true]}}\', \'*\')" style="color: #FF0000; text-decoration: none; font-weight: bold;">[{timestamp}]</a> {item["text"]}')
        else:
            # Create a link that opens in a new tab
            html_parts.append(f'<a href="https://www.youtube.com/watch?v={video_id}&t={timestamp_seconds}" target="_blank" style="color: #FF0000; text-decoration: none; font-weight: bold;">[{timestamp}]</a> {item["text"]}')
        
        html_parts.append('</div>')
    
    html_parts.append('</div>')
    return ''.join(html_parts)

def get_transcript_with_timestamps(youtube_url: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Get the transcript of a YouTube video with timestamps.
    
    Args:
        youtube_url: The URL of the YouTube video
        
    Returns:
        A tuple containing:
        - The formatted transcript as a string with timestamps
        - The raw transcript list for further processing
        
    Raises:
        ValueError: If the transcript cannot be retrieved
    """
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        
        # Fetch transcript with timestamps
        logger.info(f"Fetching transcript with timestamps for video {video_id}")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Format transcript with timestamps
        formatted_transcript = []
        for item in transcript_list:
            # Convert seconds to MM:SS format
            seconds = int(item['start'])
            minutes, seconds = divmod(seconds, 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            
            # Add timestamp and text
            formatted_transcript.append(f"[{timestamp}] {item['text']}")
        
        # Join transcript segments with newlines
        transcript_text = "\n".join(formatted_transcript)
        
        return transcript_text, transcript_list
        
    except Exception as e:
        error_msg = f"Error retrieving transcript with timestamps: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def run_analysis(youtube_url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube Analysis Crew with the provided YouTube URL.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        
    Returns:
        A tuple containing the analysis results and any error message
    """
    try:
        # Extract video ID for thumbnail
        video_id = extract_video_id(youtube_url)
        
        # Create progress placeholder
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # Initialize progress bar
        progress_bar = progress_placeholder.progress(0)
        status_placeholder.info("Fetching video transcript...")
        
        # Get the transcript
        transcript = get_transcript(youtube_url)
        progress_bar.progress(15)
        
        # Get transcript with timestamps
        try:
            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
            st.session_state.timestamped_transcript = timestamped_transcript
            st.session_state.transcript_list = transcript_list
        except Exception as e:
            logger.warning(f"Could not get transcript with timestamps: {str(e)}")
            st.session_state.timestamped_transcript = None
        
        progress_bar.progress(20)
        status_placeholder.info("Creating analysis crew...")
        
        # Set up chat functionality
        chat_details = setup_chat_for_video(youtube_url, transcript)
        if chat_details:
            st.session_state.chat_details = chat_details
            st.session_state.chat_enabled = True
            progress_bar.progress(30)
            status_placeholder.info("Chat functionality enabled!")
        else:
            st.session_state.chat_enabled = False
            logger.warning("Could not set up chat functionality")
        
        # Create and run the crew
        crew_instance = YouTubeAnalysisCrew()
        crew = crew_instance.crew()
        
        # Update progress
        progress_bar.progress(40)
        status_placeholder.info("Classifying video content...")
        
        # Start the crew execution
        inputs = {"youtube_url": youtube_url, "transcript": transcript}
        crew_output = crew.kickoff(inputs=inputs)
        
        # Extract task outputs
        task_outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                task_outputs[task_name] = task.output.raw
                
                # Update progress based on task completion
                if task_name == "classify_video":
                    progress_bar.progress(50)
                    status_placeholder.info("Summarizing video content...")
                elif task_name == "summarize_content":
                    progress_bar.progress(70)
                    status_placeholder.info("Analyzing video content...")
                elif task_name == "analyze_content":
                    progress_bar.progress(85)
                    status_placeholder.info("Creating action plan...")
                elif task_name == "create_action_plan":
                    progress_bar.progress(95)
                    status_placeholder.info("Generating final report...")
        
        # Update progress
        progress_bar.progress(100)
        status_placeholder.success("Analysis completed successfully!")
        
        # Get token usage
        token_usage = crew_output.token_usage if hasattr(crew_output, 'token_usage') else None
        
        # Extract category from classification output
        category = "Uncategorized"
        if "classify_video" in task_outputs:
            category = extract_category(task_outputs["classify_video"])
        
        # Prepare results
        results = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": transcript,
            "output": str(crew_output),
            "task_outputs": task_outputs,
            "category": category,
            "token_usage": token_usage,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Store results in session state to persist across reruns
        st.session_state.analysis_results = results
        st.session_state.analysis_complete = True
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        return None, str(e)

def display_analysis_results(results: Dict[str, Any]):
    """
    Display the analysis results for a YouTube video.
    
    Args:
        results: The analysis results dictionary
    """
    video_id = results["video_id"]
    category = results["category"]
    
    # Create columns for video and chat
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Display embedded YouTube video with enablejsapi=1 to allow JavaScript control
        st.markdown(f'<iframe width="100%" height="315" src="https://www.youtube.com/embed/{video_id}?enablejsapi=1" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>', unsafe_allow_html=True)
        
        # Display category badge
        category_class = get_category_class(category)
        st.markdown(f"<div class='category-badge {category_class}'>{category}</div>", unsafe_allow_html=True)
        
        # Analysis tabs
        tabs = st.tabs(["Summary", "Analysis", "Action Plan", "Full Report", "Transcript"])
        
        task_outputs = results["task_outputs"]
        
        # Display content in tabs
        with tabs[0]:
            if "summarize_content" in task_outputs:
                st.markdown(task_outputs["summarize_content"])
            else:
                st.info("Summary not available.")
        
        with tabs[1]:
            if "analyze_content" in task_outputs:
                st.markdown(task_outputs["analyze_content"])
            else:
                st.info("Analysis not available.")
        
        with tabs[2]:
            if "create_action_plan" in task_outputs:
                st.markdown(task_outputs["create_action_plan"])
            else:
                st.info("Action plan not available.")
        
        with tabs[3]:
            if "write_report" in task_outputs:
                st.markdown(task_outputs["write_report"])
            else:
                st.info("Full report not available.")
        
        with tabs[4]:
            st.markdown("### Video Transcript")
            
            # Add toggles for timestamps
            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                show_timestamps = st.checkbox("Show timestamps", value=True)
            with col_b:
                clickable_timestamps = st.checkbox("Enable clickable timestamps", value=True)
            with col_c:
                jump_in_embedded = st.checkbox("Jump in embedded video", value=False, 
                                              help="When enabled, clicking timestamps will jump to that point in the embedded video instead of opening a new tab")
            
            # Add JavaScript to enable communication with the YouTube iframe
            if jump_in_embedded:
                st.markdown("""
                <script>
                function onYouTubeIframeAPIReady() {
                    console.log('YouTube iframe API ready');
                }
                </script>
                <script src="https://www.youtube.com/iframe_api"></script>
                """, unsafe_allow_html=True)
            
            if show_timestamps:
                # Check if we have a timestamped transcript in session state
                if "timestamped_transcript" in st.session_state and st.session_state.timestamped_transcript:
                    if clickable_timestamps and "transcript_list" in st.session_state:
                        # Display transcript with clickable timestamps
                        html = format_transcript_with_clickable_timestamps(st.session_state.transcript_list, video_id, jump_in_embedded)
                        st.markdown(html, unsafe_allow_html=True)
                    else:
                        # Display plain text transcript with timestamps
                        st.text_area("Transcript with timestamps", st.session_state.timestamped_transcript, height=400, label_visibility="collapsed")
                else:
                    # Try to get transcript with timestamps
                    try:
                        timestamped_transcript, transcript_list = get_transcript_with_timestamps(results["youtube_url"])
                        st.session_state.timestamped_transcript = timestamped_transcript
                        st.session_state.transcript_list = transcript_list
                        
                        if clickable_timestamps:
                            # Display transcript with clickable timestamps
                            html = format_transcript_with_clickable_timestamps(transcript_list, video_id, jump_in_embedded)
                            st.markdown(html, unsafe_allow_html=True)
                        else:
                            # Display plain text transcript with timestamps
                            st.text_area("Transcript with timestamps", timestamped_transcript, height=400, label_visibility="collapsed")
                    except Exception as e:
                        st.error(f"Error retrieving transcript with timestamps: {str(e)}")
                        st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
            else:
                # Show regular transcript
                st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
    
    with col2:
        # Display chat interface
        st.markdown("<h3>Chat with this Video</h3>", unsafe_allow_html=True)
        st.markdown("<p>Ask questions about the video content and get detailed answers based on the transcript.</p>", unsafe_allow_html=True)
        
        # Create a container with fixed height for the chat interface
        chat_area = st.container()
        
        with chat_area:
            if st.session_state.chat_enabled and st.session_state.chat_details:
                display_chat_interface(st.session_state.chat_details)
            else:
                st.warning("Chat functionality could not be enabled for this video. Please try again.")

def main():
    """
    Main function to run the Streamlit app.
    """
    # Load custom CSS
    load_css()
    
    # Initialize session state variables if they don't exist
    if "chat_enabled" not in st.session_state:
        st.session_state.chat_enabled = False
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    if "chat_details" not in st.session_state:
        st.session_state.chat_details = None
    
    if "analysis_complete" not in st.session_state:
        st.session_state.analysis_complete = False
    
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
    
    if "timestamped_transcript" not in st.session_state:
        st.session_state.timestamped_transcript = None
    
    if "transcript_list" not in st.session_state:
        st.session_state.transcript_list = None
    
    # Sidebar
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png", width=180)
        st.markdown("## Settings")
        
        # Model selection
        model = st.selectbox(
            "Select LLM Model",
            ["gpt-4o-mini", "gpt-4o"],
            index=0
        )
        
        # Temperature setting
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.1,
            help="Higher values make output more random, lower values more deterministic"
        )
        
        # Set environment variables based on settings
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_TEMPERATURE"] = str(temperature)
        
        # Reset chat button (if chat is enabled)
        if st.session_state.chat_enabled:
            if st.button("Reset Chat", key="reset_chat"):
                st.session_state.chat_messages = []
                # Re-initialize welcome message
                if st.session_state.chat_details and "title" in st.session_state.chat_details:
                    st.session_state.chat_messages = [
                        {
                            "role": "assistant", 
                            "content": f"Hello! I'm your AI assistant for the video \"{st.session_state.chat_details.get('title', 'this YouTube video')}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                        }
                    ]
                st.rerun()
        
        # Reset analysis button (if analysis is complete)
        if st.session_state.analysis_complete:
            if st.button("New Analysis", key="new_analysis"):
                # Reset all relevant state
                st.session_state.chat_enabled = False
                st.session_state.chat_messages = []
                st.session_state.chat_details = None
                st.session_state.analysis_complete = False
                st.session_state.analysis_results = None
                st.session_state.timestamped_transcript = None
                st.session_state.transcript_list = None
                st.rerun()
        
        st.markdown("---")
        st.markdown(f"**App Version:** {__version__}")
        st.markdown("Made with ❤️ using CrewAI & LangGraph")

    # Main content
    st.markdown("<h1 class='main-header'>YouTube Video Analyzer & Chat</h1>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>Extract insights, summaries, and action plans from any YouTube video. Chat with the video content to learn more!</p>", unsafe_allow_html=True)
    
    # Check if analysis is already complete (retained from session state)
    if st.session_state.analysis_complete and st.session_state.analysis_results:
        # Display results from session state
        display_analysis_results(st.session_state.analysis_results)
    else:
        # URL input and analysis button
        youtube_url = st.text_input("YouTube URL", placeholder="Enter YouTube URL (e.g., https://youtu.be/...)", label_visibility="collapsed")
        analyze_button = st.button("Analyze Video", use_container_width=True)
        
        # Run analysis when button is clicked
        if analyze_button:
            if not youtube_url:
                st.error("Please enter a YouTube URL.")
            elif not validate_youtube_url(youtube_url):
                st.error("Please enter a valid YouTube URL.")
            else:
                with st.spinner("Analyzing video..."):
                    try:
                        # Get transcript with timestamps
                        try:
                            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
                            st.session_state.timestamped_transcript = timestamped_transcript
                            st.session_state.transcript_list = transcript_list
                        except Exception as e:
                            logger.warning(f"Could not get transcript with timestamps: {str(e)}")
                            st.session_state.timestamped_transcript = None
                            st.session_state.transcript_list = None
                            
                        # Run the analysis
                        results, error = run_analysis(youtube_url)
                        
                        if error:
                            st.markdown(f"<div class='error-box'>Error: {error}</div>", unsafe_allow_html=True)
                        elif results:
                            # Display the analysis results
                            display_analysis_results(results)
                    except Exception as e:
                        st.error(f"Error analyzing video: {str(e)}")
                        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
                
        # Display information about the app when no analysis is running or complete
        else:
            # Display features in cards
            st.markdown("<h2 class='sub-header'>Features</h2>", unsafe_allow_html=True)
            
            # Feature cards with improved styling
            st.markdown("""
            <div class="feature-grid">
                <div class="card">
                    <span class="card-icon">🔎</span>
                    <h3>Video Classification</h3>
                    <p>Automatically categorize videos into topics like Technology, Business, Education, and more.</p>
                </div>
                <div class="card">
                    <span class="card-icon">📋</span>
                    <h3>Comprehensive Summary</h3>
                    <p>Get a TL;DR and key points to quickly understand the video's content without watching it entirely.</p>
                </div>
                <div class="card">
                    <span class="card-icon">💬</span>
                    <h3>Chat Interface</h3>
                    <p>Ask questions about the video content and get answers based on the transcript in real-time.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # How it works section
            st.markdown("<h2 class='sub-header'>How It Works</h2>", unsafe_allow_html=True)
            
            # Steps with improved styling
            st.markdown("""
            <div class="step-grid">
                <div class="card">
                    <h3>Step 1</h3>
                    <p>Paste any YouTube URL in the input field above.</p>
                </div>
                <div class="card">
                    <h3>Step 2</h3>
                    <p>Our AI extracts and processes the video transcript.</p>
                </div>
                <div class="card">
                    <h3>Step 3</h3>
                    <p>Multiple specialized AI agents analyze the content.</p>
                </div>
                <div class="card">
                    <h3>Step 4</h3>
                    <p>Chat with the video and explore the insights and summary.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 