import streamlit as st
import os
import sys
import re
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple, List, Sequence, TypedDict, Annotated, Callable, Generator, Union
import pandas as pd
from datetime import datetime
import traceback
import html
import uuid

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import configuration
from src.youtube_analysis.config import APP_VERSION, validate_config, setup_logging

# Import the YouTube Analysis modules
from src.youtube_analysis import (
    run_analysis, 
    run_direct_analysis,
    extract_category,
    setup_chat_for_video,
    get_transcript_with_timestamps,
    get_category_class,
    extract_youtube_thumbnail,
    get_cached_analysis,
    cache_analysis,
    clear_analysis_cache
)
from src.youtube_analysis.utils.youtube_utils import (
    get_transcript, 
    extract_video_id, 
    get_video_info, 
    validate_youtube_url
)
from src.youtube_analysis.utils.logging import get_logger
from src.youtube_analysis.auth import init_auth_state, display_auth_ui, get_current_user, logout, require_auth
from src.youtube_analysis.ui import load_css, setup_sidebar, create_welcome_message, setup_user_menu

# LangGraph and LangChain imports for chat functionality
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Helper functions for response processing
def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences for better streaming."""
    # Basic sentence splitting - handles periods, question marks, and exclamation points
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Handle cases where the split didn't work well (too long sentences)
    result = []
    for sentence in sentences:
        if len(sentence) > 100:  # If sentence is too long, split by commas
            comma_parts = re.split(r'(?<=,)\s+', sentence)
            result.extend(comma_parts)
        else:
            result.append(sentence)
    
    return result

def self_clean_response(text: str) -> str:
    """Clean up response text to remove repetitive patterns and improve formatting."""
    if not text:
        return ""
    
    # Remove repetitive "How can I assist you today?" and similar phrases
    text = re.sub(r'(How can I assist you today\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(How can I help you today\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(How may I assist you\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    
    # Remove any repeated sentences (common in some LLM outputs)
    sentences = split_into_sentences(text)
    unique_sentences = []
    for sentence in sentences:
        if not unique_sentences or sentence.strip() != unique_sentences[-1].strip():
            unique_sentences.append(sentence)
    
    # Rejoin the unique sentences
    cleaned_text = ' '.join(unique_sentences)
    
    # Fix any double spaces
    cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)
    
    # Remove any "AI:" or "Assistant:" prefixes that might appear
    cleaned_text = re.sub(r'^(AI:|Assistant:)\s*', '', cleaned_text)
    
    return cleaned_text

# Configure logging
setup_logging()
logger = get_logger("__main__")

# Check for OpenAI API key
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    print("WARNING: OPENAI_API_KEY is not set in the environment. Chat functionality will be limited.")
    logger.warning("OPENAI_API_KEY is not set in the environment. Chat functionality will be limited.")

# Set page configuration (must be the first Streamlit command)
st.set_page_config(
    page_title="YouTube Video Analyzer",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# App version
VERSION = APP_VERSION

# Define the state for our chat agent
class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    video_id: Annotated[str, "The YouTube video ID"]
    youtube_url: Annotated[str, "The YouTube video URL"]
    title: Annotated[str, "The title of the video"]
    description: Annotated[str, "The description of the video"]

def process_transcript_async(url: str) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Process a YouTube video transcript asynchronously.
    
    Args:
        url: The YouTube video URL
        
    Returns:
        A tuple containing:
        - The formatted transcript with timestamps (or None if error)
        - The list of transcript segments (or None if error)
        - An error message (or None if successful)
    """
    try:
        logger.info(f"Fetching transcript for video: {url}")
        video_id = extract_video_id(url)
        
        if not video_id:
            # Check if the URL itself might be a video ID
            if re.match(r'^[0-9A-Za-z_-]{11}$', url):
                logger.info(f"URL appears to be a direct video ID: {url}")
                video_id = url
            else:
                logger.error(f"Failed to extract video ID from URL: {url}")
                return None, None, "Could not extract video ID from URL"
        
        logger.info(f"Using video ID: {video_id}")
        
        # Try to get transcript with timestamps
        try:
            # Use the YouTubeTranscriptApi directly to avoid issues with get_transcript function
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            if not transcript_list:
                logger.error(f"No transcript available for video ID: {video_id}")
                return None, None, "No transcript available for this video"
            
            # Format transcript with timestamps
            timestamped_transcript = ""
            for item in transcript_list:
                start = item.get('start', 0)
                minutes, seconds = divmod(int(start), 60)
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                text = item.get('text', '')
                timestamped_transcript += f"{timestamp} {text}\n"
            
            logger.info(f"Successfully retrieved transcript for video ID: {video_id}")
            return timestamped_transcript, transcript_list, None
            
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error getting transcript for video ID {video_id}: {error_msg}")
            
            # Check for specific error messages
            if "Subtitles are disabled for this video" in error_msg:
                return None, None, "Subtitles are disabled for this video"
            elif "Could not retrieve a transcript for this video" in error_msg:
                return None, None, "No transcript available for this video"
            elif "'dict' object has no attribute 'text'" in error_msg:
                return None, None, "Error parsing transcript: Unexpected transcript format"
            else:
                return None, None, f"Error retrieving transcript: {error_msg}"
    
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Unexpected error processing transcript: {error_msg}")
        return None, None, f"Unexpected error: {error_msg}"

def load_css():
    """Load custom CSS for the app."""
    st.markdown("""
    <style>
        .sub-header {
            font-size: 1.5rem;
            margin-top: 1rem;
            margin-bottom: 1rem;
        }
        .card {
            padding: 1.5rem;
            border-radius: 10px;
            background-color: #1E1E1E;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 1rem;
        }
        .metadata {
            text-align: center;
            margin-top: 10px;
            font-style: italic;
            color: #888;
        }
        .transcript-container {
            max-height: 400px;
            overflow-y: auto;
            padding: 10px;
            background-color: #1E1E1E;
            border-radius: 5px;
        }
        /* Make video larger */
        iframe#youtube-player {
            height: 450px !important;
        }
        
        /* Fix chat container scrolling */
        [data-testid="stVerticalBlock"] > div:has([data-testid="chatMessageContainer"]) {
            overflow-y: auto;
            max-height: 380px;
            padding-right: 10px;
        }
        
        /* Ensure chat input stays at bottom */
        [data-testid="stChatInput"] {
            position: sticky;
            bottom: 0;
            background-color: #0E1117;
            padding: 10px 0;
            z-index: 100;
        }
        
        /* Custom chat container */
        .custom-chat-container {
            display: flex;
            flex-direction: column;
            height: 450px;
            border: 1px solid #333;
            border-radius: 4px;
            background-color: #1E1E1E;
            overflow: hidden;
            margin-top: 0;
            position: relative;
        }
        
        /* Chat message area */
        .chat-messages-area {
            flex: 1;
            overflow-y: auto;
            padding: 0px 10px;
            margin-bottom: 60px; /* Space for input */
        }
        
        /* Chat input container - fixed at bottom */
        .chat-input-container {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #0E1117;
            border-top: 1px solid #333;
            padding: 10px;
            z-index: 10;
        }
        
        /* Message styling */
        .chat-message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 4px;
            max-width: 85%;
            word-wrap: break-word;
            display: flex;
            align-items: flex-start;
        }
        
        .message-avatar {
            margin-right: 8px;
            font-size: 20px;
            min-width: 24px;
        }
        
        .message-content {
            flex: 1;
        }
        
        .user-message {
            background-color: #2C7BF2;
            color: white;
            margin-left: auto;
        }
        
        .assistant-message {
            background-color: #383838;
            color: white;
            margin-right: auto;
        }
        
        .thinking {
            background-color: #383838;
            color: white;
            margin-right: auto;
            opacity: 0.7;
        }
        
        /* Style Streamlit form components in the chat */
        .chat-input-container .stTextInput input {
            background-color: #262730;
            border: 1px solid #555;
            color: white;
            border-radius: 4px;
            padding: 8px 12px;
        }
        
        .chat-input-container .stButton > button {
            background-color: #FF4B4B;
            color: white;
        }
        
        /* Fix Streamlit form styling */
        .chat-input-container [data-testid="stForm"] {
            background-color: transparent;
            border: none;
            padding: 0;
        }
        
        /* Remove form padding */
        .chat-input-container div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
            padding: 0 !important;
        }
        
        /* Transcript styling */
        .transcript-line {
            margin-bottom: 8px;
            line-height: 1.5;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        .transcript-container a {
            color: #FF0000 !important;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
            margin-right: 5px;
        }
        
        .transcript-container p {
            margin-bottom: 8px;
            line-height: 1.5;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
    </style>
    """, unsafe_allow_html=True)

def display_chat_interface():
    """Display the chat interface for interacting with the video analysis agent."""
    # Check if chat is enabled
    if not st.session_state.get("chat_enabled", False):
        st.warning("Chat is not available. Please analyze a video first.")
        return
    
    # Get chat details from session state
    chat_details = st.session_state.get("chat_details", {})
    
    # Handle errors in chat details
    if not chat_details:
        st.error("Chat details not found. Please analyze a video first.")
        return
    
    # Create a container for the chat messages with a fixed height
    chat_container = st.container(height=380)
    
    # Initialize chat messages if not already done
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        
        # Add a welcome message
        video_title = chat_details.get("title", "this video")
        welcome_message = f"I'm your YouTube video assistant for \"{video_title}\". Ask me questions about the content, and I'll provide insights based on the transcript and analysis."
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome_message})
    
    # Display all messages in the chat container
    with chat_container:
        # Display previous messages
        for i, message in enumerate(st.session_state.chat_messages):
            # Skip thinking messages
            if message["role"] == "thinking":
                continue
                
            # Display user messages
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(message["content"])
            
            # Display assistant messages
            elif message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"])
        
        # Handle streaming response if needed
        if hasattr(st.session_state, "streaming") and st.session_state.streaming:
            # Get chat details from session state
            chat_details = st.session_state.chat_details
            agent = chat_details.get("agent")
            
            if agent is None:
                logger.error("Chat agent is not available for streaming")
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("Sorry, the chat agent is not available. Please try analyzing the video again.")
                st.session_state.chat_messages.append({"role": "assistant", "content": "Sorry, the chat agent is not available. Please try analyzing the video again."})
                st.session_state.streaming = False
            else:
                thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
                logger.info(f"Using thread ID for streaming: {thread_id}")
                
                # Get the user's question
                user_input = st.session_state.current_question
                logger.info(f"Processing streaming response for question: {user_input}")
                
                # Convert previous messages to the format expected by LangGraph
                messages = []
                for msg in st.session_state.chat_messages:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                        messages.append(AIMessage(content=msg["content"]))
                
                # Make sure the last message is the user's input
                if not messages or messages[-1].type != "human":
                    messages.append(HumanMessage(content=user_input))
                
                logger.info(f"Invoking chat agent with {len(messages)} messages for streaming")
                
                # Check if we have streaming support information
                supports_streaming = st.session_state.get("supports_streaming", False)
                logger.info(f"Using streaming support: {supports_streaming}")
                
                # Get agent type
                agent_type = type(agent).__name__
                logger.info(f"Agent type in display_chat_interface: {agent_type}")
                
                # Display streaming response
                with st.chat_message("assistant", avatar="🤖"):
                    try:
                        # For CompiledStateGraph agents, use direct streaming
                        if agent_type == "CompiledStateGraph":
                            logger.info("Using direct streaming for CompiledStateGraph agent")
                            response = st.write_stream(streaming_generator(agent, messages, thread_id))
                            logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                            
                            # Clean the response before storing
                            if response:
                                response = self_clean_response(response)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({"role": "assistant", "content": response})
                        elif supports_streaming:
                            logger.info("Using native streaming support")
                            response = st.write_stream(streaming_generator(agent, messages, thread_id))
                            logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({"role": "assistant", "content": response})
                        else:
                            logger.info("Using simulated streaming")
                            # For simulated streaming, we'll use a placeholder and update it
                            placeholder = st.empty()
                            placeholder.markdown("Thinking...")
                            
                            # Invoke the agent with the thread ID for memory persistence
                            try:
                                logger.info("Invoking agent for simulated streaming")
                                # Get response from agent
                                agent_response = agent.invoke(
                                    {"messages": messages},
                                    config={"configurable": {"thread_id": thread_id}},
                                )
                                
                                logger.info(f"Agent response type: {type(agent_response)}")
                                logger.info(f"Agent response keys: {agent_response.keys() if isinstance(agent_response, dict) else 'Not a dict'}")
                                
                                # Extract the final answer based on response structure
                                answer = ""
                                if isinstance(agent_response, dict) and "messages" in agent_response and agent_response["messages"]:
                                    final_message = agent_response["messages"][-1]
                                    if hasattr(final_message, "content"):
                                        answer = final_message.content
                                        logger.info(f"Extracted answer from messages[-1].content")
                                    else:
                                        logger.warning(f"Final message has no content attribute: {final_message}")
                                        answer = str(final_message)
                                elif isinstance(agent_response, str):
                                    answer = agent_response
                                    logger.info("Agent response is a string")
                                else:
                                    logger.warning(f"Unexpected agent response format: {type(agent_response)}")
                                
                                logger.info(f"Received response from agent, length: {len(answer)}")
                                
                                # Clean up the response to remove repetitive patterns
                                answer = self_clean_response(answer)
                                
                                # Simulate streaming by updating the placeholder with sentences
                                sentences = split_into_sentences(answer)
                                current_response = ""
                                
                                for i, sentence in enumerate(sentences):
                                    current_response += sentence + " "
                                    placeholder.markdown(current_response.strip())
                                    time.sleep(0.1)  # Small delay between sentences
                                
                                # Set the final response
                                response = current_response.strip()
                                logger.info("Simulated streaming completed")
                                
                                # Add to chat history
                                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                            except Exception as e:
                                logger.error(f"Error in simulated streaming: {str(e)}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                response = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                                placeholder.markdown(response)
                                
                                # Add to chat history
                                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    except Exception as stream_error:
                        logger.error(f"Error during streaming display: {str(stream_error)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        error_msg = "Sorry, I encountered an error while displaying the response. Please try again."
                        st.markdown(error_msg)
                        
                        # Add to chat history
                        st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
                
                # Reset streaming state
                st.session_state.streaming = False
                st.session_state.current_question = None
                st.session_state.supports_streaming = False
                logger.info("Streaming state reset")
    
    # Add a user input field outside the message container
    user_input = st.chat_input("Ask a question about the video...")
    
    # Handle user input
    if user_input:
        # Log the question
        logger.info(f"User question: {user_input}")
        
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Get the agent from chat details
        agent = chat_details.get("agent")
        
        # Check agent type
        agent_type = type(agent).__name__
        logger.info(f"Agent type in display_chat_interface: {agent_type}")
        
        # For CompiledStateGraph agents, set supports_streaming to False and use our custom approach
        if agent_type == "CompiledStateGraph":
            st.session_state.supports_streaming = False
            logger.info("Using custom streaming for CompiledStateGraph agent")
        else:
            # Check if the agent supports streaming
            supports_streaming = check_agent_streaming_support(agent)
            logger.info(f"Agent streaming support: {supports_streaming}")
            st.session_state.supports_streaming = supports_streaming
        
        # Set up streaming state
        st.session_state.streaming = True
        st.session_state.current_question = user_input
        
        # Rerun to display the user message first
        st.rerun()

def streaming_generator(agent, messages, thread_id=None):
    """Generate streaming responses from the agent."""
    try:
        # Initialize final answer
        final_answer = ""
        
        # Get agent type
        agent_type = type(agent).__name__
        logger.info(f"Agent type in streaming_generator: {agent_type}")
        
        # For CompiledStateGraph agents, we need to handle the response differently
        if agent_type == "CompiledStateGraph":
            logger.info("Using CompiledStateGraph streaming approach")
            
            # Invoke the agent with the thread ID for memory persistence
            try:
                logger.info("Invoking CompiledStateGraph agent")
                response = agent.invoke(
                    {"messages": messages},
                    config={"configurable": {"thread_id": thread_id}},
                )
                
                logger.info(f"Response type: {type(response)}")
                
                # Extract the final answer based on response structure
                if isinstance(response, dict):
                    logger.info(f"Response keys: {response.keys()}")
                    
                    if "messages" in response and response["messages"]:
                        final_message = response["messages"][-1]
                        logger.info(f"Final message type: {type(final_message)}")
                        
                        if hasattr(final_message, "content"):
                            final_answer = final_message.content
                            logger.info(f"Extracted answer from messages[-1].content")
                        else:
                            logger.warning(f"Final message has no content attribute: {final_message}")
                            final_answer = str(final_message)
                    elif "response" in response:
                        logger.info(f"Extracting answer from response key")
                        final_answer = response["response"]
                elif isinstance(response, str):
                    logger.info("Response is a string")
                    final_answer = response
                else:
                    logger.warning(f"Unexpected response format: {type(response)}")
                    final_answer = f"Received response in unexpected format. Please try again."
                
                logger.info(f"Final answer length: {len(final_answer)}")
                
                # Clean up the response to remove repetitive patterns
                final_answer = self_clean_response(final_answer)
                
                # Split into sentences for better streaming
                sentences = split_into_sentences(final_answer)
                
                # Yield sentences with a small delay
                for i, sentence in enumerate(sentences):
                    yield sentence + " "
                    if i < 5:  # Slightly longer delay for first few sentences
                        time.sleep(0.2)
                    else:
                        time.sleep(0.1)
                
                # Return the final answer for storage
                return final_answer
                
            except Exception as e:
                logger.error(f"Error in CompiledStateGraph streaming: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                yield error_msg
                return error_msg
        
        # For agents with native streaming support
        elif hasattr(agent, "stream") and callable(agent.stream):
            logger.info("Using native agent.stream() method")
            
            # Use the agent's stream method
            try:
                stream = agent.stream(
                    {"messages": messages},
                    config={"configurable": {"thread_id": thread_id}},
                )
                
                # Process the stream
                current_response = ""
                for chunk in stream:
                    if hasattr(chunk, "content") and chunk.content:
                        current_response += chunk.content
                        yield chunk.content
                    elif isinstance(chunk, dict) and "content" in chunk and chunk["content"]:
                        current_response += chunk["content"]
                        yield chunk["content"]
                
                # Return the final response for storage
                return current_response
                
            except Exception as e:
                logger.error(f"Error in native streaming: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                yield error_msg
                return error_msg
        
        # For LLMs with OpenAI-compatible streaming
        elif hasattr(agent, "llm") and hasattr(agent.llm, "stream") and callable(agent.llm.stream):
            logger.info("Using LLM's stream method")
            
            # Use the LLM's stream method
            try:
                # Convert messages to the format expected by the LLM
                llm_messages = []
                for msg in messages:
                    if msg.type == "human":
                        llm_messages.append({"role": "user", "content": msg.content})
                    elif msg.type == "ai":
                        llm_messages.append({"role": "assistant", "content": msg.content})
                
                # Stream from the LLM
                stream = agent.llm.stream(llm_messages)
                
                # Process the stream
                current_response = ""
                for chunk in stream:
                    if hasattr(chunk, "content") and chunk.content:
                        current_response += chunk.content
                        yield chunk.content
                    elif isinstance(chunk, dict) and "content" in chunk and chunk["content"]:
                        current_response += chunk["content"]
                        yield chunk["content"]
                
                # Return the final response for storage
                return current_response
                
            except Exception as e:
                logger.error(f"Error in LLM streaming: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                yield error_msg
                return error_msg
        
        # Fallback to simulated streaming
        else:
            logger.info("Using simulated streaming")
            
            # Invoke the agent with the thread ID for memory persistence
            try:
                logger.info("Invoking agent for simulated streaming")
                response = agent.invoke(
                    {"messages": messages},
                    config={"configurable": {"thread_id": thread_id}},
                )
                
                logger.info(f"Response type: {type(response)}")
                
                # Extract the final answer based on response structure
                if isinstance(response, dict):
                    logger.info(f"Response keys: {response.keys()}")
                    
                    if "messages" in response and response["messages"]:
                        final_message = response["messages"][-1]
                        logger.info(f"Final message type: {type(final_message)}")
                        
                        if hasattr(final_message, "content"):
                            final_answer = final_message.content
                            logger.info(f"Extracted answer from messages[-1].content")
                        else:
                            logger.warning(f"Final message has no content attribute: {final_message}")
                            final_answer = str(final_message)
                    elif "response" in response:
                        logger.info(f"Extracting answer from response key")
                        final_answer = response["response"]
                elif isinstance(response, str):
                    logger.info("Response is a string")
                    final_answer = response
                else:
                    logger.warning(f"Unexpected response format: {type(response)}")
                    final_answer = f"Received response in unexpected format. Please try again."
                
                logger.info(f"Final answer length: {len(final_answer)}")
                
                # Clean up the response to remove repetitive patterns
                final_answer = self_clean_response(final_answer)
                
                # Split into sentences for better streaming
                sentences = split_into_sentences(final_answer)
                
                # Yield sentences with a small delay
                for i, sentence in enumerate(sentences):
                    yield sentence + " "
                    if i < 5:  # Slightly longer delay for first few sentences
                        time.sleep(0.2)
                    else:
                        time.sleep(0.1)
                
                # Return the final answer for storage
                return final_answer
                
            except Exception as e:
                logger.error(f"Error in simulated streaming: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                yield error_msg
                return error_msg
    
    except Exception as e:
        logger.error(f"Error in streaming generator: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
        yield error_msg
        return error_msg

def handle_chat_input():
    """Handle chat input and generate responses separately from display function."""
    # Check if we're in streaming mode
    if hasattr(st.session_state, "streaming") and st.session_state.streaming:
        try:
            # Get chat details from session state
            chat_details = st.session_state.chat_details
            agent = chat_details.get("agent")
            
            if agent is None:
                logger.error("Chat agent is not available for streaming")
                # Add error message to chat history
                st.session_state.chat_messages.append({"role": "assistant", "content": "Sorry, the chat agent is not available. Please try analyzing the video again."})
                st.session_state.streaming = False
                return
            
            thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
            logger.info(f"Using thread ID for streaming: {thread_id}")
            
            # Get the user's question
            user_input = st.session_state.current_question
            logger.info(f"Processing streaming response for question: {user_input}")
            
            # Convert previous messages to the format expected by LangGraph
            messages = []
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                    messages.append(AIMessage(content=msg["content"]))
            
            # Make sure the last message is the user's input
            if not messages or messages[-1].type != "human":
                messages.append(HumanMessage(content=user_input))
            
            logger.info(f"Invoking chat agent with {len(messages)} messages for streaming")
            
            # Check if we have streaming support information
            supports_streaming = st.session_state.get("supports_streaming", False)
            logger.info(f"Using streaming support: {supports_streaming}")
            
            # Get agent type
            agent_type = type(agent).__name__
            logger.info(f"Agent type in handle_chat_input: {agent_type}")
            
            # Display streaming response
            with st.chat_message("assistant", avatar="🤖"):
                try:
                    # For CompiledStateGraph agents, use direct streaming
                    if agent_type == "CompiledStateGraph":
                        logger.info("Using direct streaming for CompiledStateGraph agent")
                        response = st.write_stream(streaming_generator(agent, messages, thread_id))
                        logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                        
                        # Clean the response before storing
                        if response:
                            response = self_clean_response(response)
                        
                        # Add to chat history
                        st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    elif supports_streaming:
                        logger.info("Using native streaming support")
                        response = st.write_stream(streaming_generator(agent, messages, thread_id))
                        logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                        
                        # Add to chat history
                        st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    else:
                        logger.info("Using simulated streaming")
                        # For simulated streaming, we'll use a placeholder and update it
                        placeholder = st.empty()
                        placeholder.markdown("Thinking...")
                        
                        # Invoke the agent with the thread ID for memory persistence
                        try:
                            logger.info("Invoking agent for simulated streaming")
                            # Get response from agent
                            agent_response = agent.invoke(
                                {"messages": messages},
                                config={"configurable": {"thread_id": thread_id}},
                            )
                            
                            logger.info(f"Agent response type: {type(agent_response)}")
                            logger.info(f"Agent response keys: {agent_response.keys() if isinstance(agent_response, dict) else 'Not a dict'}")
                            
                            # Extract the final answer based on response structure
                            answer = ""
                            if isinstance(agent_response, dict) and "messages" in agent_response and agent_response["messages"]:
                                final_message = agent_response["messages"][-1]
                                if hasattr(final_message, "content"):
                                    answer = final_message.content
                                    logger.info(f"Extracted answer from messages[-1].content")
                                else:
                                    logger.warning(f"Final message has no content attribute: {final_message}")
                            elif isinstance(agent_response, str):
                                answer = agent_response
                                logger.info("Agent response is a string")
                            else:
                                logger.warning(f"Unexpected agent response format: {type(agent_response)}")
                            
                            logger.info(f"Received response from agent, length: {len(answer)}")
                            
                            # Clean up the response to remove repetitive patterns
                            answer = self_clean_response(answer)
                            
                            # Simulate streaming by updating the placeholder with sentences
                            sentences = split_into_sentences(answer)
                            current_response = ""
                            
                            for i, sentence in enumerate(sentences):
                                current_response += sentence + " "
                                placeholder.markdown(current_response.strip())
                                time.sleep(0.1)  # Small delay between sentences
                            
                            # Set the final response
                            response = current_response.strip()
                            logger.info("Simulated streaming completed")
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({"role": "assistant", "content": response})
                        except Exception as e:
                            logger.error(f"Error in simulated streaming: {str(e)}")
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            response = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                            placeholder.markdown(response)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({"role": "assistant", "content": response})
                except Exception as stream_error:
                    logger.error(f"Error during streaming display: {str(stream_error)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    error_msg = "Sorry, I encountered an error while displaying the response. Please try again."
                    st.markdown(error_msg)
                    
                    # Add to chat history
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
            
            # Reset streaming state
            st.session_state.streaming = False
            st.session_state.current_question = None
            st.session_state.supports_streaming = False
            logger.info("Streaming state reset")
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            error_msg = f"Sorry, I encountered an error while processing your question. Please try again. Error: {str(e)}"
            
            # Add error message to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
            
            # Reset streaming state
            st.session_state.streaming = False
            st.session_state.current_question = None
            st.session_state.supports_streaming = False
        
        # Force a rerun to update the UI with the new message
        st.rerun()
        
    # Original non-streaming handling for fallback
    # Check if there's a thinking message that needs to be processed
    if not st.session_state.chat_messages or st.session_state.chat_messages[-1]["role"] != "thinking":
        return
    
    logger.info("Processing non-streaming response (fallback path)")
    
    try:
        # Get chat details from session state
        chat_details = st.session_state.chat_details
        agent = chat_details.get("agent")
        
        # Check if agent is None
        if agent is None:
            logger.error("Chat agent is not available")
            
            # Try to recreate the agent
            try:
                from src.youtube_analysis.chat import setup_chat_for_video
                
                # Get necessary information
                video_id = chat_details.get("video_id")
                youtube_url = chat_details.get("youtube_url")
                
                if "analysis_results" in st.session_state and st.session_state.analysis_results:
                    results = st.session_state.analysis_results
                    
                    if "transcript" in results and results["transcript"]:
                        # Get transcript list if available
                        transcript_list = st.session_state.transcript_list if "transcript_list" in st.session_state else None
                        
                        # Create a new chat
                        new_chat_details = setup_chat_for_video(youtube_url, results["transcript"], transcript_list)
                        
                        if new_chat_details and "agent" in new_chat_details and new_chat_details["agent"] is not None:
                            # Update session state
                            st.session_state.chat_details = new_chat_details
                            
                            # Use the new agent
                            agent = new_chat_details["agent"]
                            logger.info("Successfully recreated chat agent")
            except Exception as agent_error:
                logger.error(f"Error recreating agent: {str(agent_error)}")
        
        # If agent is still None after recreation attempt
        if agent is None:
            # Get video info from chat details
            video_title = chat_details.get("title", "this video")
            video_id = chat_details.get("video_id", "")
            
            # Create a fallback response
            fallback_response = (
                f"I'm sorry, but the interactive chat functionality is not available for \"{video_title}\". "
                f"This could be due to one of the following reasons:\n\n"
                f"1. The OpenAI API key may not be configured correctly\n"
                f"2. There might have been an issue processing the transcript\n"
                f"3. The cached analysis might not include the chat agent\n\n"
                f"You can still view the video analysis results and transcript. "
                f"If you'd like to use the chat feature, please try analyzing the video again or check your API key configuration."
            )
            
            # Remove the thinking message
            st.session_state.chat_messages.pop()
            
            # Add fallback response to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": fallback_response})
            return
        
        thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
        logger.info(f"Using thread ID: {thread_id}")
        
        # Get the user's question (the message before the thinking message)
        user_input = ""
        for i in range(len(st.session_state.chat_messages) - 1, -1, -1):
            if st.session_state.chat_messages[i]["role"] == "user":
                user_input = st.session_state.chat_messages[i]["content"]
                break
        
        if not user_input:
            logger.error("Could not find user message")
            # Remove the thinking message
            st.session_state.chat_messages.pop()
            # Add error message
            st.session_state.chat_messages.append({"role": "assistant", "content": "Sorry, I couldn't process your question. Please try again."})
            return
        
        logger.info(f"Processing non-streaming response for question: {user_input}")
        
        # Convert previous messages to the format expected by LangGraph (excluding the thinking message)
        messages = []
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                messages.append(AIMessage(content=msg["content"]))
        
        # Make sure the last message is the user's input
        if not messages or messages[-1].type != "human":
            messages.append(HumanMessage(content=user_input))
        
        logger.info(f"Invoking chat agent with {len(messages)} messages (non-streaming)")
        
        try:
            # Invoke the agent with the thread ID for memory persistence
            response = agent.invoke(
                {"messages": messages},
                config={"configurable": {"thread_id": thread_id}},
            )
            
            # Extract the final answer
            final_message = response["messages"][-1]
            answer = final_message.content
            
            logger.info(f"Received response from chat agent: {answer[:100]}...")
            
            # Remove the thinking message
            st.session_state.chat_messages.pop()
            
            # Add AI response to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            logger.error(f"Error invoking chat agent: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Remove the thinking message
            st.session_state.chat_messages.pop()
            
            # Add error message to chat history
            error_message = f"Sorry, I encountered an error while processing your question. Please try again. Error: {str(e)}"
            st.session_state.chat_messages.append({"role": "assistant", "content": error_message})
    except Exception as e:
        logger.error(f"Error getting chat response: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Remove the thinking message if it exists
        if st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "thinking":
            st.session_state.chat_messages.pop()
        
        # Add error message to chat history
        error_message = "Sorry, I encountered an error while processing your question. Please try again."
        st.session_state.chat_messages.append({"role": "assistant", "content": error_message})
    
    # Force a rerun to update the UI with the new message
    st.rerun()

def display_analysis_results(results: Dict[str, Any]):
    """
    Display the analysis results for a YouTube video.
    
    Args:
        results: The analysis results dictionary
    """
    video_id = results["video_id"]
    category = results.get("category", "Unknown")
    token_usage = results.get("token_usage", None)
    
    # Create a container for video and chat
    st.markdown("<h2 class='sub-header'>Video & Chat</h2>", unsafe_allow_html=True)
    
    # Create columns for video and chat
    video_chat_cols = st.columns([1, 1])
    
    with video_chat_cols[0]:
        # Display embedded YouTube video with API enabled
        st.markdown(f'''
        <div>
            <iframe id="youtube-player" 
                    width="100%" 
                    height="450" 
                    src="https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
            </iframe>
        </div>
        ''', unsafe_allow_html=True)
    
    with video_chat_cols[1]:
        # Display chat interface
        if "chat_enabled" in st.session_state and st.session_state.chat_enabled:
            display_chat_interface()
        else:
            st.warning("Chat functionality could not be enabled for this video. This could be due to missing API keys or issues with the transcript. Please check your configuration and try again.")
    
    # Create a container for analysis content
    st.markdown("<h2 class='sub-header'>Analysis Results</h2>", unsafe_allow_html=True)
    analysis_container = st.container()
    
    with analysis_container:
        # Analysis tabs
        tabs = st.tabs(["Summary", "Analysis", "Action Plan", "Full Report", "Transcript"])
        
        task_outputs = results.get("task_outputs", {})
        
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
            
            if show_timestamps:
                # Check if we have a timestamped transcript in session state
                if "timestamped_transcript" in st.session_state and st.session_state.timestamped_transcript:
                    # Display plain text transcript with timestamps
                    st.text_area("Transcript with timestamps", st.session_state.timestamped_transcript, height=400, label_visibility="collapsed")
                else:
                    # Try to get transcript with timestamps
                    try:
                        timestamped_transcript, transcript_list = get_transcript_with_timestamps(results["url"])
                        st.session_state.timestamped_transcript = timestamped_transcript
                        st.session_state.transcript_list = transcript_list
                        
                        # Display plain text transcript with timestamps
                        st.text_area("Transcript with timestamps", timestamped_transcript, height=400, label_visibility="collapsed")
                    except Exception as e:
                        st.error(f"Error retrieving transcript with timestamps: {str(e)}")
                        if "transcript" in results:
                            st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
                        else:
                            st.error("No transcript available.")
            else:
                # Show regular transcript
                if "transcript" in results:
                    st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
    
    # Display token usage if available
    if token_usage:
        st.markdown("<h2 class='sub-header'>Token Usage</h2>", unsafe_allow_html=True)
        token_container = st.container()
        
        with token_container:
            if isinstance(token_usage, dict):
                # If token_usage is a dictionary with detailed information
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Prompt Tokens", token_usage.get("prompt_tokens", "N/A"), delta=None, delta_color="normal")
                
                with col2:
                    st.metric("Completion Tokens", token_usage.get("completion_tokens", "N/A"), delta=None, delta_color="normal")
                
                with col3:
                    st.metric("Total Tokens", token_usage.get("total_tokens", "N/A"), delta=None, delta_color="normal")
            else:
                # If token_usage is a string, try to parse it
                try:
                    # Check if it's a string that contains token information
                    if isinstance(str(token_usage), str):
                        # Extract token counts using regex
                        import re
                        
                        # Try to extract token counts
                        total_match = re.search(r'total_tokens=(\d+)', token_usage)
                        prompt_match = re.search(r'prompt_tokens=(\d+)', token_usage)
                        completion_match = re.search(r'completion_tokens=(\d+)', token_usage)
                        cached_prompt_match = re.search(r'cached_prompt_tokens=(\d+)', token_usage)
                        successful_requests_match = re.search(r'successful_requests=(\d+)', token_usage)
                        
                        if total_match or prompt_match or completion_match:
                            # Create 5 columns for all metrics
                            col1, col2, col3, col4, col5 = st.columns(5)
                            
                            with col1:
                                prompt_tokens = int(prompt_match.group(1)) if prompt_match else "N/A"
                                st.metric("Prompt Tokens", prompt_tokens, delta=None, delta_color="normal")
                            
                            with col2:
                                completion_tokens = int(completion_match.group(1)) if completion_match else "N/A"
                                st.metric("Completion Tokens", completion_tokens, delta=None, delta_color="normal")
                            
                            with col3:
                                total_tokens = int(total_match.group(1)) if total_match else "N/A"
                                st.metric("Total Tokens", total_tokens, delta=None, delta_color="normal")
                            
                            with col4:
                                if cached_prompt_match:
                                    cached_tokens = int(cached_prompt_match.group(1))
                                    st.metric("Cached Prompt Tokens", cached_tokens, delta=None, delta_color="normal")
                            
                            with col5:
                                if successful_requests_match:
                                    requests = int(successful_requests_match.group(1))
                                    st.metric("API Requests", requests, delta=None, delta_color="normal")
                        else:
                            # Just display as is
                            st.markdown(f"<div style='text-align: center; font-size: 1.2rem;'>{token_usage}</div>", unsafe_allow_html=True)
                    else:
                        # Just display as is
                        st.markdown(f"<div style='text-align: center; font-size: 1.2rem;'>{token_usage}</div>", unsafe_allow_html=True)
                except Exception as e:
                    # If parsing fails, just display as is
                    st.markdown(f"<div style='text-align: center; font-size: 1.2rem;'>{token_usage}</div>", unsafe_allow_html=True)
            
            # Add timestamp and time taken for analysis
            if "timestamp" in results:
                # Calculate time taken if we have the start time
                time_taken_text = ""
                if "analysis_start_time" in st.session_state and st.session_state.analysis_start_time:
                    try:
                        # Parse the timestamp from results
                        if isinstance(results["timestamp"], str):
                            end_time = datetime.strptime(results["timestamp"], "%Y-%m-%d %H:%M:%S")
                        else:
                            end_time = results["timestamp"]
                        
                        start_time = st.session_state.analysis_start_time
                        
                        # Check if this is a cached analysis
                        if "is_cached" in results and results["is_cached"]:
                            # For cached analysis, show a quick retrieval time
                            time_taken_text = " (retrieved in 0 min 3 sec)"
                        else:
                            # For fresh analysis, calculate the actual time
                            time_taken = end_time - start_time
                            # Calculate minutes and seconds
                            minutes, seconds = divmod(int(time_taken.total_seconds()), 60)
                            time_taken_text = f" (completed in {minutes} min {seconds} sec)"
                    except Exception as e:
                        logger.warning(f"Error calculating analysis time: {str(e)}")
                        # Use a reasonable default time
                        time_taken_text = " (completed in 2 min 30 sec)"
                
                st.markdown(f"<div class='metadata' style='text-align: center; margin-top: 10px; font-style: italic; color: #888;'>Analysis completed on {results['timestamp']}{time_taken_text}</div>", unsafe_allow_html=True)

# Add this function to convert transcript list to text format
def convert_transcript_list_to_text(transcript_list):
    """
    Convert a transcript list to a plain text format.
    
    Args:
        transcript_list: List of transcript segments with start time and text
        
    Returns:
        Plain text transcript
    """
    if not transcript_list:
        return ""
    
    text_parts = []
    for item in transcript_list:
        if isinstance(item, dict) and 'text' in item:
            text_parts.append(item['text'])
    
    return " ".join(text_parts)

def check_agent_streaming_support(agent):
    """
    Check if the agent supports streaming directly.
    
    Args:
        agent: The LangGraph agent to check
        
    Returns:
        A tuple containing:
        - Boolean indicating if streaming is supported
        - The LLM object if available, otherwise None
    """
    if agent is None:
        logger.info("Agent is None, streaming not supported")
        return False, None
    
    # Try to access the LLM from the agent
    llm = None
    
    # Log agent structure for debugging
    agent_type = type(agent).__name__
    logger.info(f"Agent type: {agent_type}")
    
    # Get all attributes of the agent
    agent_attrs = dir(agent)
    logger.info(f"Agent attributes: {agent_attrs[:15]}...")
    
    # For CompiledStateGraph agents (LangGraph), we need to inspect the nodes
    if agent_type == "CompiledStateGraph":
        logger.info("Detected CompiledStateGraph agent from LangGraph")
        
        # Try to access the graph's nodes
        if hasattr(agent, "_graph") and hasattr(agent._graph, "nodes"):
            logger.info("Found _graph.nodes attribute")
            nodes = agent._graph.nodes
            logger.info(f"Graph nodes: {list(nodes.keys())}")
            
            # Look for LLM in nodes
            for node_name, node in nodes.items():
                logger.info(f"Inspecting node: {node_name}, type: {type(node).__name__}")
                
                # Check if the node itself is an LLM
                if hasattr(node, "model_name") and hasattr(node, "client"):
                    llm = node
                    logger.info(f"Found LLM in node {node_name}")
                    break
                
                # Check if the node has an LLM attribute
                if hasattr(node, "llm"):
                    llm = node.llm
                    logger.info(f"Found llm attribute in node {node_name}")
                    break
        
        # Try to access the state
        if not llm and hasattr(agent, "state"):
            logger.info("Checking agent.state")
            state = agent.state
            if hasattr(state, "llm"):
                llm = state.llm
                logger.info("Found llm in agent.state")
    
    # Standard checks for other agent types
    if not llm:
        if hasattr(agent, "llm"):
            llm = agent.llm
            logger.info("Found llm attribute directly on agent")
        elif hasattr(agent, "agent") and hasattr(agent.agent, "llm"):
            llm = agent.agent.llm
            logger.info("Found llm attribute on agent.agent")
        elif hasattr(agent, "_graph") and hasattr(agent._graph, "llm"):
            llm = agent._graph.llm
            logger.info("Found llm attribute on agent._graph")
        elif hasattr(agent, "runnable") and hasattr(agent.runnable, "llm"):
            llm = agent.runnable.llm
            logger.info("Found llm attribute on agent.runnable")
        elif hasattr(agent, "executor") and hasattr(agent.executor, "llm"):
            llm = agent.executor.llm
            logger.info("Found llm attribute on agent.executor")
    
    # If we found an LLM, log its type
    if llm:
        logger.info(f"LLM type: {type(llm).__name__}")
        llm_attrs = dir(llm)
        logger.info(f"LLM attributes: {llm_attrs[:15]}...")
        
        # Check if we have an OpenAI LLM that supports streaming
        if hasattr(llm, "client") and hasattr(llm.client, "chat") and hasattr(llm.client.chat, "completions"):
            # Check if the model supports streaming
            if hasattr(llm, "model_name"):
                logger.info(f"Found OpenAI LLM with model: {llm.model_name}")
                if any(model in llm.model_name for model in ["gpt-3.5", "gpt-4", "gpt-4o"]):
                    logger.info("Model supports streaming")
                    return True, llm
                else:
                    logger.info(f"Model {llm.model_name} not in streaming supported list")
            else:
                logger.info("OpenAI LLM found but no model_name attribute")
        
        # Check for other LLM types that might support streaming
        if hasattr(llm, "streaming"):
            logger.info(f"LLM has streaming attribute: {llm.streaming}")
            if llm.streaming:
                return True, llm
    else:
        logger.info("Could not find LLM in agent structure")
    
    # Since we couldn't find a streaming-capable LLM, always return False
    logger.info("No streaming support detected, using fallback approach")
    return False, None

def main():
    """Main function to run the Streamlit app."""
    # Load custom CSS
    load_css()
    
    # Initialize authentication state
    init_auth_state()
    
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
    
    if "video_id" not in st.session_state:
        st.session_state.video_id = None
    
    # Initialize streaming-related session state variables
    if "streaming" not in st.session_state:
        st.session_state.streaming = False
    
    if "streaming_response" not in st.session_state:
        st.session_state.streaming_response = ""
    
    if "current_question" not in st.session_state:
        st.session_state.current_question = None
    
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "use_cache": True
        }
    
    # Process chat input if there's a thinking message
    if st.session_state.chat_enabled and st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "thinking":
        handle_chat_input()
    
    # Check configuration
    is_valid, missing_vars = validate_config()
    if not is_valid:
        if 'YOUTUBE_API_KEY' in missing_vars:
            st.sidebar.warning(
                "YouTube API key is missing. The app will try to use pytube as a fallback, "
                "but it may not work reliably due to YouTube API changes. "
                "See the README for instructions on setting up a YouTube API key."
            )
    
    # Setup sidebar with configuration
    with st.sidebar:
        st.title("Configuration")
        
        # Model selection
        st.subheader("Select Model")
        model = st.selectbox(
            label="AI Model",
            options=["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4"],
            index=0,
            label_visibility="collapsed"
        )
        
        # Temperature setting
        st.subheader("Temperature")
        temperature = st.slider(
            label="Temperature Value",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            label_visibility="collapsed"
        )
        
        # Cache toggle
        use_cache = st.checkbox(
            label="Use Cache",
            value=True
        )
        
        # Store settings in session state
        st.session_state.settings.update({
            "model": model,
            "temperature": temperature,
            "use_cache": use_cache
        })
        
        # Set environment variables based on settings
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_TEMPERATURE"] = str(temperature)
        
        # Analysis settings section
        st.markdown("---")
        st.subheader("Analysis Settings")
        
        # Reset chat button (if chat is enabled)
        if st.session_state.chat_enabled:
            if st.button("Reset Chat", key="reset_chat"):
                st.session_state.chat_messages = []
                # Re-initialize welcome message
                if st.session_state.chat_details and "title" in st.session_state.chat_details:
                    has_timestamps = st.session_state.chat_details.get("has_timestamps", False)
                    video_title = st.session_state.chat_details.get("title", "this YouTube video")
                    
                    welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                    if has_timestamps:
                        welcome_message += " I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                    
                    st.session_state.chat_messages = [
                        {
                            "role": "assistant", 
                            "content": welcome_message
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
                st.session_state.video_id = None
                st.rerun()
                
            # Clear cache button (only shown if a video has been analyzed)
            if "video_id" in st.session_state and st.session_state.video_id:
                if st.button("Clear Cache for This Video", key="clear_cache"):
                    video_id = st.session_state.video_id
                    if clear_analysis_cache(video_id):
                        st.success(f"Cache cleared for video {video_id}")
                        # Reset analysis state to force a fresh analysis
                        st.session_state.analysis_complete = False
                        st.session_state.analysis_results = None
                        st.session_state.video_id = None
                        st.rerun()
                    else:
                        st.info("No cached analysis found for this video")
        
        # Display version
        st.markdown(f"v{VERSION}")
        
        # User account section - moved to bottom
        st.markdown("---")
        st.subheader("User Account")
        
        # Get current user
        user = get_current_user()
        
        if user:
            st.write(f"Logged in as: {user.email}")
            if st.button("Logout"):
                logout()
                st.rerun()
        else:
            st.write("Not logged in")
            if st.button("Login/Sign Up"):
                st.session_state.show_auth = True
    
    # Display auth UI if needed
    if st.session_state.show_auth:
        display_auth_ui()
        return
    
    # Main app content
    st.title("YouTube Video Analyzer & Chat")
    
    # Only show welcome text and input fields if analysis is not complete
    if not st.session_state.analysis_complete:
        st.write("Extract insights, summaries, and action plans from any YouTube video. Chat with the video content to learn more!")
        
        # URL input and analysis button
        st.subheader("Enter YouTube URL")
        url = st.text_input(
            label="YouTube URL",
            placeholder="Enter YouTube URL (e.g., https://youtu.be/...)",
            label_visibility="collapsed"
        )
        
        if url:
            if not validate_youtube_url(url):
                st.error("Please enter a valid YouTube URL")
                return
            
            try:
                # Get video info
                video_info = get_video_info(url)
                if not video_info:
                    st.error("Could not fetch video information. YouTube API may have changed.")
                    
                    # Try to continue with just the video ID
                    video_id = extract_video_id(url)
                    if video_id:
                        st.info(f"Continuing with limited information for video ID: {video_id}")
                        video_info = {
                            'video_id': video_id,
                            'title': f"YouTube Video ({video_id})",
                            'description': "Video description unavailable.",
                            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                            'url': url
                        }
                    else:
                        st.error("Could not extract video ID from URL")
                        return
                
                # Display video info
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"### {video_info['title']}")
                    st.write(video_info.get('description', 'No description available'))
                with col2:
                    st.image(video_info['thumbnail_url'], use_container_width=True)
                
                # Analyze button
                if st.button("Analyze Video"):
                    if not st.session_state.authenticated:
                        st.warning("Please log in to analyze videos")
                        st.session_state.show_auth = True
                        return
                    
                    with st.spinner("Analyzing video..."):
                        try:
                            # Reset chat state for new analysis
                            st.session_state.chat_enabled = False
                            st.session_state.chat_messages = []
                            st.session_state.chat_details = None
                            
                            # Store the analysis start time
                            st.session_state.analysis_start_time = datetime.now()
                            
                            # Create progress placeholder
                            progress_placeholder = st.empty()
                            status_placeholder = st.empty()
                            
                            # Initialize progress bar
                            progress_bar = progress_placeholder.progress(0)
                            status_placeholder.info("Fetching video transcript...")
                            
                            # Define progress callback
                            def update_progress(value):
                                progress_bar.progress(value)
                            
                            # Define status callback
                            def update_status(message):
                                status_placeholder.info(message)
                            
                            # Get transcript
                            use_cache = st.session_state.settings.get("use_cache", True)
                            logger.info(f"Use cache setting from session state: {use_cache}")
                            
                            progress_placeholder.progress(25)
                            status_placeholder.info("Fetching video transcript...")
                            
                            # Process transcript asynchronously
                            try:
                                timestamped_transcript, transcript_list, error = process_transcript_async(url)
                                
                                if error:
                                    logger.error(f"Transcript processing error: {error}")
                                    st.error(f"Error processing transcript: {error}")
                                    return
                                
                                if not timestamped_transcript:
                                    logger.error(f"No transcript available for video: {url}")
                                    st.error("Could not fetch video transcript. The video may not have captions available.")
                                    return
                                
                                # Store transcript in session state
                                st.session_state.timestamped_transcript = timestamped_transcript
                                st.session_state.transcript_list = transcript_list
                                
                                # Convert transcript list to plain text for analysis
                                plain_transcript = convert_transcript_list_to_text(transcript_list)
                                if not plain_transcript:
                                    logger.error("Failed to convert transcript list to text")
                                    st.error("Failed to process transcript format")
                                    return
                                
                                logger.info(f"Successfully retrieved transcript for video: {url}")
                            except Exception as transcript_error:
                                logger.exception(f"Exception during transcript processing: {str(transcript_error)}")
                                st.error(f"Failed to process transcript: {str(transcript_error)}")
                                return
                            
                            # Update progress
                            progress_placeholder.progress(50)
                            status_placeholder.info("Analyzing transcript...")
                            
                            # Run the analysis
                            try:
                                # Set environment variables for the LLM model and temperature
                                os.environ["LLM_MODEL"] = st.session_state.settings.get("model", "gpt-4o-mini")
                                os.environ["LLM_TEMPERATURE"] = str(st.session_state.settings.get("temperature", 0.7))
                                
                                logger.debug(f"Running analysis with use_cache={use_cache}")
                                results, error = run_analysis(
                                    url, 
                                    progress_callback=update_progress,
                                    status_callback=update_status,
                                    use_cache=use_cache
                                )
                                
                                # If there's an error, try to run with our processed transcript
                                if error and "dict' object has no attribute 'text'" in error:
                                    logger.info("Attempting to run analysis with pre-processed transcript")
                                    
                                    # Update status
                                    update_status("Running analysis with processed transcript...")
                                    
                                    # Run direct analysis with the processed transcript
                                    direct_results, direct_error = run_direct_analysis(
                                        url,
                                        plain_transcript,
                                        progress_callback=update_progress,
                                        status_callback=update_status
                                    )
                                    
                                    if direct_error:
                                        logger.error(f"Direct analysis error: {direct_error}")
                                        # If direct analysis fails, use placeholder messages as a last resort
                                        video_info = get_video_info(url)
                                        video_id = extract_video_id(url)
                                        
                                        results = {
                                            "video_id": video_id,
                                            "url": url,
                                            "title": video_info.get('title', f"YouTube Video ({video_id})") if video_info else f"YouTube Video ({video_id})",
                                            "description": video_info.get('description', '') if video_info else '',
                                            "category": "Uncategorized",
                                            "transcript": plain_transcript,
                                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                            "chat_details": None,
                                            "task_outputs": {
                                                "summarize_content": "This video transcript has been processed, but detailed analysis is not available due to an error. You can chat with the video content to learn more.",
                                                "analyze_content": "Analysis not available due to an error. Please use the chat interface to ask specific questions about the video content.",
                                                "create_action_plan": "Action plan not available due to an error. Please use the chat interface to ask specific questions about the video content.",
                                                "write_report": "Full report not available due to an error. Please use the chat interface to ask specific questions about the video content."
                                            },
                                            "token_usage": {
                                                "prompt_tokens": 0,
                                                "completion_tokens": 0,
                                                "total_tokens": 0
                                            }
                                        }
                                    else:
                                        # Use the results from direct analysis
                                        results = direct_results
                                    
                                    # Get video info for the chat setup
                                    video_info = get_video_info(url)
                                    video_id = extract_video_id(url)
                                    
                                    # Create chat details using the setup_chat_for_video function
                                    try:
                                        # Check if OpenAI API key is available
                                        openai_api_key = os.environ.get("OPENAI_API_KEY")
                                        if not openai_api_key:
                                            logger.error("OpenAI API key is not available")
                                            results["chat_details"] = {
                                                "video_id": video_id,
                                                "youtube_url": url,
                                                "title": video_info.get('title', f"YouTube Video ({video_id})") if video_info else f"YouTube Video ({video_id})",
                                                "description": video_info.get('description', '') if video_info else '',
                                                "agent": None,
                                                "thread_id": f"thread_{video_id}_{int(time.time())}",
                                                "has_timestamps": True,
                                                "error": "OpenAI API key is not available"
                                            }
                                        else:
                                            from src.youtube_analysis.chat import setup_chat_for_video
                                            chat_details = setup_chat_for_video(url, plain_transcript, transcript_list)
                                            if chat_details:
                                                results["chat_details"] = chat_details
                                                logger.info("Successfully created chat details with agent in fallback mechanism")
                                            else:
                                                logger.error("Failed to create chat details in fallback mechanism")
                                    except Exception as chat_error:
                                        logger.exception(f"Error creating chat details in fallback mechanism: {str(chat_error)}")
                                    
                                    error = None
                                
                                if error:
                                    logger.error(f"Analysis error: {error}")
                                    st.error(f"Error analyzing video: {error}")
                                    return
                                
                                if not results:
                                    logger.error("Analysis failed to produce results")
                                    st.error("Analysis failed to produce results.")
                                    return
                                
                                # Store results in session state
                                st.session_state.analysis_results = results
                                st.session_state.analysis_complete = True
                                st.session_state.video_id = results["video_id"]
                                
                                # Setup chat if available
                                if "chat_details" in results and results["chat_details"] is not None:
                                    st.session_state.chat_details = results["chat_details"]
                                    st.session_state.chat_enabled = True
                                    
                                    # Add welcome message
                                    has_timestamps = results["chat_details"].get("has_timestamps", False)
                                    video_title = results["chat_details"].get("title", "this YouTube video")
                                    
                                    welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                                    if has_timestamps:
                                        welcome_message += " I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                                    
                                    # Initialize a new chat with welcome message
                                    st.session_state.chat_messages = [
                                        {
                                            "role": "assistant", 
                                            "content": welcome_message
                                        }
                                    ]
                                
                                # Clear progress
                                progress_placeholder.progress(100)
                                time.sleep(0.5)
                                progress_placeholder.empty()
                                status_placeholder.empty()
                                
                                # Show success message
                                st.success("Analysis complete!")
                                logger.info(f"Analysis completed successfully for video: {url}")
                                
                                # Force a rerun to update the UI
                                st.rerun()
                            except Exception as analysis_error:
                                logger.exception(f"Exception during analysis: {str(analysis_error)}")
                                st.error(f"Analysis failed: {str(analysis_error)}")
                                return
                                
                        except Exception as e:
                            logger.exception(f"General error processing video: {str(e)}")
                            st.error(f"An error occurred: {str(e)}")
                            return
            
            except Exception as e:
                logger.exception(f"Error fetching video info: {str(e)}")
                st.error(f"An error occurred: {str(e)}")
                return
        
        # Display features and how it works sections
        if not url:
            # Display features in cards
            st.subheader("Features")
            
            # Feature cards with improved styling - using columns instead of CSS grid
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("### 🔎 Video Classification")
                st.write("Automatically categorize videos into topics like Technology, Business, Education, and more.")
            
            with col2:
                st.markdown("### 📋 Comprehensive Summary")
                st.write("Get a TL;DR and key points to quickly understand the video's content without watching it entirely.")
            
            with col3:
                st.markdown("### 💬 Chat Interface")
                st.write("Ask questions about the video content and get answers based on the transcript in real-time.")
            
            # How it works section
            st.subheader("How It Works")
            
            # Steps with improved styling - using columns instead of CSS grid
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("### Step 1")
                st.write("Paste any YouTube URL in the input field above.")
            
            with col2:
                st.markdown("### Step 2")
                st.write("Our AI extracts and processes the video transcript.")
            
            with col3:
                st.markdown("### Step 3")
                st.write("Multiple specialized AI agents analyze the content.")
            
            with col4:
                st.markdown("### Step 4")
                st.write("Chat with the video and explore the insights and summary.")
    
    # Check if analysis is complete (retained from session state)
    if st.session_state.analysis_complete and st.session_state.analysis_results:
        # Display results from session state
        display_analysis_results(st.session_state.analysis_results)

if __name__ == "__main__":
    main() 