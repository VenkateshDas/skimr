"""Service for chat operations with video context."""

import asyncio
import uuid
from typing import Optional, Dict, Any, List, Union, AsyncGenerator, Tuple
from datetime import datetime
from ..models import ChatSession, ChatMessage, MessageRole, VideoData, AnalysisResult
from ..repositories import CacheRepository, YouTubeRepository
from ..utils.chat_utils import setup_chat_for_video_async
from ..utils.logging import get_logger
from ..core import LLMManager
from ..core.config import CHAT_WELCOME_TEMPLATE, config

logger = get_logger("chat_service")


class ChatService:
    """Service for chat operations with video context."""
    
    def __init__(self, cache_repository: CacheRepository, youtube_repository: YouTubeRepository):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        self.llm_manager = LLMManager()
        self._chat_agents = {}  # Cache for chat agents by video_id
        logger.info("Initialized ChatService")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation: 1 token ≈ 4 characters)."""
        return max(1, len(text) // 4)
    
    async def stream_response(
        self,
        video_id: str,
        chat_history: List[Dict[str, str]],
        current_question: str,
        model_name: str = None,
        temperature: float = None
    ) -> AsyncGenerator[Tuple[str, Optional[Dict[str, int]]], None]:
        """
        Stream a chat response for a video with token usage tracking.
        
        Args:
            video_id: Video ID
            chat_history: List of previous chat messages
            current_question: Current user question
            model_name: LLM model to use (defaults to config)
            temperature: Temperature for generation (defaults to config)
            
        Yields:
            Tuple of (response chunk, token usage dict for final response)
        """
        try:
            # Use config defaults if not provided
            if model_name is None:
                model_name = config.llm.default_model
            if temperature is None:
                temperature = config.llm.default_temperature
            
            logger.info(f"Streaming chat response for video {video_id}")
            
            # Get chat agent for video
            agent = await self._get_or_create_chat_agent(video_id)
            
            if not agent:
                yield "I'm sorry, I couldn't retrieve the chat context for this video. Please try again.", None
                return
            
            # Prepare the input for the agent
            agent_input = {
                "messages": [
                    {"role": msg["role"], "content": msg["content"]} 
                    for msg in chat_history
                ] + [
                    {"role": "user", "content": current_question}
                ]
            }
            
            # Stream the response from the agent
            full_response = ""
            try:
                # Use astream method if available (LangGraph agents support this)
                if hasattr(agent, 'astream'):
                    async for chunk in agent.astream(agent_input):
                        # Handle different chunk formats from LangGraph
                        if isinstance(chunk, dict):
                            # Extract content from different possible formats
                            if "agent" in chunk and "messages" in chunk["agent"]:
                                # New message from agent
                                for message in chunk["agent"]["messages"]:
                                    if hasattr(message, 'content'):
                                        content = message.content
                                        if content and content not in full_response:
                                            full_response = content
                                            yield content[len(full_response)-len(content):] if full_response else content, None
                            elif "output" in chunk:
                                # Direct output format
                                content = chunk["output"]
                                if content and content not in full_response:
                                    new_content = content[len(full_response):]
                                    yield new_content, None
                                    full_response += new_content
                        elif hasattr(chunk, 'content'):
                            # Direct message format
                            content = chunk.content
                            if content and content not in full_response:
                                new_content = content[len(full_response):]
                                yield new_content, None
                                full_response = content
                else:
                    # Fallback: Use invoke method if stream not available
                    logger.warning("Agent doesn't support streaming, using invoke instead")
                    result = await agent.ainvoke(agent_input)
                    
                    # Extract response from result
                    if isinstance(result, dict) and "output" in result:
                        full_response = result["output"]
                        yield full_response, None
                    elif isinstance(result, dict) and "messages" in result:
                        # Get the last AI message
                        for msg in reversed(result["messages"]):
                            if msg.get("role") == "assistant" or hasattr(msg, 'type') and msg.type == "ai":
                                full_response = msg.get("content", "") if isinstance(msg, dict) else msg.content
                                yield full_response, None
                                break
                    else:
                        full_response = str(result)
                        yield full_response, None
                
                # Calculate token usage for the final response
                # Estimate tokens for question and response
                prompt_tokens = self._estimate_tokens(current_question)
                completion_tokens = self._estimate_tokens(full_response)
                total_tokens = prompt_tokens + completion_tokens
                
                token_usage = {
                    "total_tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }
                
                logger.info(f"Estimated chat token usage: {token_usage}")
                # Send final token usage information
                yield "", token_usage
                        
            except Exception as e:
                logger.error(f"Error during agent streaming: {str(e)}", exc_info=True)
                error_msg = f"\n\nI encountered an error while processing your request: {str(e)}"
                yield error_msg, None
                
        except Exception as e:
            logger.error(f"Error streaming chat response: {str(e)}", exc_info=True)
            error_msg = f"\n\nI encountered an error while generating the response: {str(e)}"
            yield error_msg, None

    # Keep the original method for backward compatibility
    async def stream_response_original(
        self,
        video_id: str,
        chat_history: List[Dict[str, str]],
        current_question: str,
        model_name: str = None,
        temperature: float = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response for a video (original method without token tracking).
        """
        # Use config defaults if not provided
        if model_name is None:
            model_name = config.llm.default_model
        if temperature is None:
            temperature = config.llm.default_temperature
            
        async for chunk, token_usage in self.stream_response(video_id, chat_history, current_question, model_name, temperature):
            if chunk:  # Only yield non-empty chunks
                yield chunk

    async def _get_or_create_chat_agent(self, video_id: str):
        """Get existing or create new chat agent for a video."""
        # Check cache
        if video_id in self._chat_agents:
            return self._chat_agents[video_id]
        
        # Try to get video data from cache first
        video_data = await self.cache_repo.get_video_data(video_id)
        if video_data:
            # Get analysis result for context
            analysis_result = await self.cache_repo.get_analysis_result(video_id)
            
            # Setup chat using cached video data
            chat_details = await self.setup_chat(video_data, analysis_result)
            if not chat_details or "agent" not in chat_details:
                logger.error(f"Failed to setup chat agent for {video_id} using cached video data")
                return None
            
            # Cache the agent
            self._chat_agents[video_id] = chat_details["agent"]
            return chat_details["agent"]
        
        # Fallback: derive YouTube URL and build context even if video_data isn't cached
        logger.warning(f"No video data in cache for {video_id}, attempting fallback setup")
        analysis_result = await self.cache_repo.get_analysis_result(video_id)
        youtube_url = None
        if analysis_result and hasattr(analysis_result, "youtube_url") and analysis_result.youtube_url:
            youtube_url = analysis_result.youtube_url
        else:
            # Last-resort URL construction
            youtube_url = f"https://youtu.be/{video_id}"
        
        chat_details = await self.setup_chat(youtube_url, analysis_result)
        if not chat_details or "agent" not in chat_details:
            logger.error(f"Failed to setup chat agent for {video_id} via fallback path")
            return None
        
        # Cache the agent
        self._chat_agents[video_id] = chat_details["agent"]
        return chat_details["agent"]
    
    def _format_chat_history(self, chat_history: List[Dict[str, str]]) -> str:
        """Format chat history for the agent."""
        formatted = []
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                formatted.append(f"Human: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        return "\n\n".join(formatted)
    
    async def setup_chat(
        self, 
        youtube_url_or_data: Union[str, VideoData], 
        analysis_result: Optional[AnalysisResult] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Set up chat for a video.
        
        Args:
            youtube_url_or_data: Either a YouTube URL string or a VideoData object
            analysis_result: Optional analysis result to use for enhanced context
            
        Returns:
            Dictionary with chat details or None if failed
        """
        try:
            # Handle the case where a coroutine was passed
            if asyncio.iscoroutine(youtube_url_or_data):
                logger.warning("setup_chat received a coroutine for youtube_url_or_data, resolving it")
                youtube_url_or_data = await youtube_url_or_data
                
            # Handle different argument types
            if isinstance(youtube_url_or_data, VideoData):
                # We already have the VideoData object
                video_data = youtube_url_or_data
                youtube_url = video_data.youtube_url
                logger.info(f"Using provided VideoData object for {youtube_url}")
            elif isinstance(youtube_url_or_data, str):
                # We have a URL string, need to get VideoData
                youtube_url = youtube_url_or_data
                
                # Extract video ID
                video_id = self.youtube_repo.extract_video_id(youtube_url)
                if not video_id:
                    logger.error(f"Invalid YouTube URL: {youtube_url}")
                    return None
                
                # Try to get from cache first
                video_data = await self.cache_repo.get_video_data(video_id)
                
                # If not in cache, fetch from YouTube
                if not video_data:
                    logger.info(f"Fetching video data for {video_id}")
                    video_data = await self.youtube_repo.get_video_data(youtube_url)
                    # Store fetched video data in cache for future requests
                    try:
                        if video_data:
                            await self.cache_repo.store_video_data(video_data)
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache fetched video data for {video_id}: {str(cache_err)}")
            else:
                # Unexpected type
                logger.error(f"Unexpected type for youtube_url_or_data: {type(youtube_url_or_data)}")
                return None
            
            # Check if we have a valid VideoData object with transcript
            if not video_data:
                logger.error("Failed to get video data for chat setup")
                return None
            
            if not hasattr(video_data, 'has_transcript'):
                logger.error("VideoData object missing has_transcript attribute")
                return None
                
            if not video_data.has_transcript:
                logger.error("No transcript available for chat setup")
                return None
            
            # Convert transcript segments to list format for the chat setup
            transcript_list = None
            if hasattr(video_data, 'transcript_segments') and video_data.transcript_segments:
                transcript_list = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration
                    }
                    for seg in video_data.transcript_segments
                ]
                logger.info(f"Prepared {len(transcript_list)} transcript segments for chat")
            
            # Get the transcript text
            transcript = video_data.transcript if hasattr(video_data, 'transcript') else None
            if not transcript:
                logger.error("No transcript text available for chat setup")
                return None
            
            # Set up chat
            logger.info(f"Setting up chat for {youtube_url}")
            chat_details = await setup_chat_for_video_async(
                youtube_url,
                transcript,
                transcript_list
            )
            
            if not chat_details:
                logger.error(f"Failed to set up chat for {youtube_url}")
                return None
                
            logger.info(f"Successfully set up chat for {youtube_url}")
            return chat_details
            
        except Exception as e:
            logger.error(f"Error setting up chat: {str(e)}", exc_info=True)
            return None

    def setup_chat_sync(
        self, 
        youtube_url_or_data: Union[str, VideoData], 
        analysis_result: Optional[AnalysisResult] = None
    ) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for setup_chat."""
        return asyncio.run(self.setup_chat(youtube_url_or_data, analysis_result))

    # Chat Session Caching Methods
    async def get_or_create_chat_session(
        self, 
        video_id: str, 
        youtube_url: str,
        initial_agent_details: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatSession]:
        """
        Get existing chat session from cache or create a new one.
        
        Args:
            video_id: Video ID
            youtube_url: YouTube URL
            initial_agent_details: Agent details from initial setup
            
        Returns:
            ChatSession object or None if failed
        """
        try:
            # Try to get existing chat session from cache
            chat_session = await self.cache_repo.get_chat_session(video_id)
            
            if chat_session:
                logger.info(f"Retrieved existing chat session for video {video_id} with {len(chat_session.messages)} messages")
                return chat_session
            
            # Create new chat session if none exists
            session_id = str(uuid.uuid4())
            chat_session = ChatSession(
                session_id=session_id,
                video_id=video_id,
                youtube_url=youtube_url,
                agent_details=initial_agent_details
            )
            
            # Save the new session to cache
            await self.cache_repo.store_chat_session(chat_session)
            logger.info(f"Created new chat session for video {video_id}")
            
            return chat_session
            
        except Exception as e:
            logger.error(f"Error getting or creating chat session for video {video_id}: {str(e)}")
            return None
    
    async def save_chat_session(self, chat_session: ChatSession) -> bool:
        """
        Save chat session to cache.
        
        Args:
            chat_session: ChatSession to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.cache_repo.store_chat_session(chat_session)
            return True
        except Exception as e:
            logger.error(f"Error saving chat session: {str(e)}")
            return False
    
    async def update_chat_session_with_messages(
        self, 
        video_id: str, 
        messages: List[Dict[str, str]]
    ) -> bool:
        """
        Update chat session with new messages from Streamlit session.
        
        Args:
            video_id: Video ID
            messages: List of message dictionaries from Streamlit
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert Streamlit messages to proper format for cache
            cache_messages = []
            for msg in messages:
                cache_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "metadata": msg.get("metadata")
                })
            
            await self.cache_repo.update_chat_session_messages(video_id, cache_messages)
            logger.debug(f"Updated chat session messages for video {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating chat session messages for video {video_id}: {str(e)}")
            return False
    
    async def get_cached_chat_messages(self, video_id: str) -> List[Dict[str, str]]:
        """
        Get chat messages from cached session in Streamlit format.
        
        Args:
            video_id: Video ID
            
        Returns:
            List of message dictionaries in Streamlit format
        """
        try:
            chat_session = await self.cache_repo.get_chat_session(video_id)
            
            if not chat_session:
                return []
            
            # Convert ChatMessage objects to Streamlit format
            streamlit_messages = []
            for msg in chat_session.messages:
                streamlit_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
            
            logger.debug(f"Retrieved {len(streamlit_messages)} cached messages for video {video_id}")
            return streamlit_messages
            
        except Exception as e:
            logger.error(f"Error getting cached chat messages for video {video_id}: {str(e)}")
            return []
    
    async def clear_chat_session(self, video_id: str) -> bool:
        """
        Clear chat session for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.cache_repo.clear_chat_session(video_id)
            
            # Also clear from in-memory agent cache
            if video_id in self._chat_agents:
                del self._chat_agents[video_id]
            
            logger.info(f"Cleared chat session for video {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing chat session for video {video_id}: {str(e)}")
            return False
    
    async def initialize_chat_session_with_welcome(
        self, 
        video_id: str, 
        youtube_url: str, 
        video_title: str,
        agent_details: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatSession]:
        """
        Initialize a new chat session with a welcome message.
        
        Args:
            video_id: Video ID
            youtube_url: YouTube URL
            video_title: Video title for personalized welcome
            agent_details: Agent details from setup
            
        Returns:
            ChatSession with welcome message or None if failed
        """
        try:
            # Create or get chat session
            chat_session = await self.get_or_create_chat_session(video_id, youtube_url, agent_details)
            
            if not chat_session:
                return None
            
            # Add welcome message if session is empty
            if len(chat_session.messages) == 0:
                welcome_msg = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
                
                chat_session.add_assistant_message(welcome_msg)
                
                # Save the updated session
                await self.save_chat_session(chat_session)
                logger.info(f"Initialized chat session with welcome message for video {video_id}")
            
            return chat_session
            
        except Exception as e:
            logger.error(f"Error initializing chat session with welcome for video {video_id}: {str(e)}")
            return None