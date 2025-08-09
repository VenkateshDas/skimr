import os
import sys
import re
import streamlit as st
from typing import List, Dict, Any, Optional, TypedDict, Annotated, Sequence
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from dotenv import load_dotenv
import traceback
import json

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the YouTube Analysis modules
from src.youtube_analysis.utils.youtube_utils import get_transcript, extract_video_id, get_video_info
from src.youtube_analysis.utils.logging import setup_logger
from src.youtube_analysis.core.config import CHAT_PROMPT_TEMPLATE

# Load environment variables
load_dotenv()

# Configure logging
logger = setup_logger("yt_rag_langgraph", log_level="INFO")  # Changed back to INFO for minimal logging

# App version
__version__ = "1.0.0"

# Define the state for our agent
class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    video_id: Annotated[str, "The YouTube video ID"]
    youtube_url: Annotated[str, "The YouTube video URL"]
    title: Annotated[str, "The title of the video"]
    description: Annotated[str, "The description of the video"]

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
    
    # Create system message with video description using template from config
    video_title = video_metadata.get('title', 'Unknown')
    video_description = video_metadata.get('description', 'No description available')
    
    system_message_content = CHAT_PROMPT_TEMPLATE.format(
        video_title=video_title,
        video_description=video_description
    )
    
    # Create a proper prompt template with the system message
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message_content),
        ("placeholder", "{messages}"),
    ])
    
    # Create the agent using LangGraph's current API
    try:
        agent_executor = create_react_agent(llm, tools, prompt=prompt, version="v2")
        logger.info("Created agent with prompt template (v2)")
    except Exception as e:
        logger.error(f"Unexpected error creating agent: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    
    # Return the agent executor
    return agent_executor

def process_youtube_video(youtube_url: str) -> Optional[Dict[str, Any]]:
    """
    Process a YouTube video and return its details.
    
    Args:
        youtube_url: The URL of the YouTube video
        
    Returns:
        A dictionary containing the video details or None if an error occurred
    """
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        logger.info(f"Processing video with ID: {video_id}")
        
        # Get transcript
        try:
            transcript = get_transcript(youtube_url)
            logger.info(f"Successfully retrieved transcript for video {video_id}")
        except Exception as e:
            logger.error(f"Error retrieving transcript: {str(e)}")
            return None
        
        # Get video information (title, description, etc.)
        try:
            video_info = get_video_info(video_id)
            logger.info(f"Retrieved video info: {video_info['title']}")
        except Exception as e:
            logger.error(f"Error retrieving video info: {str(e)}")
            # Provide default video info if retrieval fails
            video_info = {
                "title": f"YouTube Video {video_id}",
                "description": "No description available due to API error."
            }
            logger.info(f"Using default video info for {video_id}")
        
        # Create vector store
        try:
            vectorstore = create_vectorstore(transcript)
            logger.info("Successfully created vector store")
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            return None
        
        # Create video metadata
        video_metadata = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available")
        }
        
        # Create agent
        try:
            agent = create_agent_graph(vectorstore, video_metadata)
            logger.info("Successfully created agent")
        except Exception as e:
            logger.error(f"Error creating agent: {str(e)}")
            return None
        
        # Create thread ID for persistence
        thread_id = f"thread_{video_id}_{int(os.path.getmtime(__file__))}"
        
        # Return video details
        return {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": transcript,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available"),
            "vectorstore": vectorstore,
            "agent": agent,
            "thread_id": thread_id
        }
    except Exception as e:
        logger.error(f"Error processing YouTube video: {str(e)}")
        return None

def display_chat_messages():
    """Display chat messages from session state."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def main():
    """Main function for the Streamlit app."""
    
    # Set page configuration
    st.set_page_config(
        page_title="YouTube Video Chat",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Custom CSS for better styling
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
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
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
        }
        .stButton button:hover {
            background-color: #D50000;
            box-shadow: 0 4px 12px rgba(255, 0, 0, 0.3);
            transform: translateY(-2px);
        }
        
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background-color: #1A1A1A;
            border-right: 1px solid #333333;
        }
        section[data-testid="stSidebar"] .stMarkdown h2 {
            color: #FFFFFF;
        }
        
        /* Spinner */
        .stSpinner > div {
            border-color: #FF0000 #FF0000 transparent !important;
        }
        
        /* Video title */
        .video-title {
            font-size: 1.4rem;
            font-weight: 600;
            margin: 1rem 0;
            color: #FFFFFF;
        }
        
        /* Status message */
        .status-message {
            padding: 0.8rem;
            border-radius: 8px;
            margin: 1rem 0;
            text-align: center;
        }
        
        .status-message.info {
            background-color: rgba(33, 150, 243, 0.1);
            border: 1px solid rgba(33, 150, 243, 0.3);
            color: #64B5F6;
        }
        
        .status-message.success {
            background-color: rgba(76, 175, 80, 0.1);
            border: 1px solid rgba(76, 175, 80, 0.3);
            color: #81C784;
        }
        
        .status-message.error {
            background-color: rgba(244, 67, 54, 0.1);
            border: 1px solid rgba(244, 67, 54, 0.3);
            color: #E57373;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "video_processed" not in st.session_state:
        st.session_state.video_processed = False
    
    if "video_details" not in st.session_state:
        st.session_state.video_details = None
    
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
        
        # Reset chat button
        if st.button("Reset Chat", key="reset_chat"):
            st.session_state.messages = []
            st.session_state.video_processed = False
            st.session_state.video_details = None
            st.rerun()
        
        st.markdown("---")
        st.markdown(f"**App Version:** {__version__}")
        st.markdown("Made with ❤️ using LangGraph, LangGraph-Community & OpenAI")
        
    # Main content
    st.markdown("<h1 class='main-header'>YouTube Video Chat</h1>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>Chat with any YouTube video! Ask questions about the content and get detailed answers.</p>", unsafe_allow_html=True)
    
    # URL input
    youtube_url = st.text_input("YouTube URL", placeholder="Enter YouTube URL (e.g., https://youtu.be/...)", label_visibility="collapsed")
    
    # Process button
    process_button = st.button("Process Video", use_container_width=True, key="process_video")
    
    # Process video when button is clicked
    if process_button:
        if not youtube_url:
            st.error("Please enter a YouTube URL.")
        elif not validate_youtube_url(youtube_url):
            st.error("Please enter a valid YouTube URL.")
        else:
            with st.spinner("Processing video..."):
                video_details = process_youtube_video(youtube_url)
                
                if video_details is None:
                    st.error("Failed to process the video. Please try again.")
                else:
                    st.session_state.video_details = video_details
                    st.session_state.video_processed = True
                    st.session_state.messages = []
                    st.success("Video processed successfully! You can now chat with the content.")
                    st.rerun()
    
    # Display video and chat interface if video is processed
    if st.session_state.video_processed and st.session_state.video_details is not None:
        # Display video
        video_details = st.session_state.video_details
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.video(video_details["youtube_url"])
        
        with col2:
            st.markdown("<div class='card'><h3>Video Chat</h3><p>Ask questions about the video content and get detailed answers based on the transcript. You can also ask general questions!</p></div>", unsafe_allow_html=True)
        
        # Chat interface
        st.markdown("<h2 class='sub-header'>Chat with the Video</h2>", unsafe_allow_html=True)
        
        # Display chat messages
        display_chat_messages()
        
        # Chat input
        if prompt := st.chat_input("Ask a question about the video or anything else...", key="chat_input"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                try:
                    # Get the agent and thread ID
                    agent = video_details["agent"]
                    thread_id = video_details["thread_id"]
                    
                    # Convert previous messages to the format expected by LangGraph
                    messages = []
                    for msg in st.session_state.messages:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            messages.append(AIMessage(content=msg["content"]))
                    
                    # Add the current user message
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
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    logger.error(f"Error getting response: {str(e)}")
                    message_placeholder.markdown("Sorry, I encountered an error while processing your question. Please try again.")
    else:
        # Display information about the app when no video is processed
        st.markdown("<div class='status-message info'>Enter a YouTube URL above and click 'Process Video' to start chatting with the content.</div>", unsafe_allow_html=True)
        
        # How it works section
        st.markdown("<h2 class='sub-header'>How It Works</h2>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="card">
                <h3>Step 1: Process Video</h3>
                <p>Enter a YouTube URL and click 'Process Video'. We'll extract the transcript and prepare it for conversation.</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="card">
                <h3>Step 2: Ask Questions</h3>
                <p>Once the video is processed, you can ask questions about its content or any general topic in the chat interface.</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="card">
                <h3>Step 3: Get Answers</h3>
                <p>Our AI will analyze the video transcript or use its general knowledge to provide detailed answers to your questions.</p>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    logger.info(f"Starting YouTube RAG LangGraph application v{__version__}")
    main() 