"""Chat functionality for YouTube video analysis."""

import os
import time
from typing import Dict, Any, Optional, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage
from langgraph.prebuilt import create_react_agent
from langchain.schema import Document

from .utils.logging import get_logger
from .utils.youtube_utils import extract_video_id, get_video_info

# Configure logging
logger = get_logger("chat")

def create_vectorstore(text: str, transcript_list: Optional[List[Dict[str, Any]]] = None) -> FAISS:
    """
    Create a vector store from the text.
    
    Args:
        text: The text to create the vector store from
        transcript_list: Optional list of transcript items with timestamps
        
    Returns:
        A FAISS vector store
    """
    # Split the text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    
    if transcript_list:
        # Process transcript with timestamps
        chunks = []
        metadata_list = []
        
        # Process transcript in chunks
        current_chunk = ""
        current_chunk_metadata = {
            "start_time": None,
            "end_time": None
        }
        
        for item in transcript_list:
            # Convert seconds to MM:SS format
            seconds = int(item['start'])
            minutes, seconds = divmod(seconds, 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            
            # Add text with timestamp
            text_with_timestamp = f"[{timestamp}] {item['text']}"
            
            # If this is the first item in the chunk, set the start time
            if current_chunk_metadata["start_time"] is None:
                current_chunk_metadata["start_time"] = timestamp
                current_chunk_metadata["start_seconds"] = item['start']
            
            # Update the end time for each item
            current_chunk_metadata["end_time"] = timestamp
            current_chunk_metadata["end_seconds"] = item['start'] + item.get('duration', 0)
            
            # Add to current chunk
            if current_chunk:
                current_chunk += " "
            current_chunk += text_with_timestamp
            
            # If chunk is large enough, add it to chunks and reset
            if len(current_chunk) >= 1000:
                chunks.append(current_chunk)
                metadata_list.append(current_chunk_metadata.copy())
                current_chunk = ""
                current_chunk_metadata = {
                    "start_time": None,
                    "end_time": None
                }
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
            metadata_list.append(current_chunk_metadata)
        
        # Create embeddings
        embeddings = OpenAIEmbeddings()
        
        # Create a FAISS vector store with metadata
        texts_with_metadata = [
            {"content": chunk, "metadata": metadata}
            for chunk, metadata in zip(chunks, metadata_list)
        ]
        
        vectorstore = FAISS.from_documents(
            documents=[
                Document(page_content=item["content"], metadata=item["metadata"])
                for item in texts_with_metadata
            ],
            embedding=embeddings
        )
        
        logger.info(f"Created FAISS vector store with {len(chunks)} chunks (with timestamps)")
    else:
        # Process regular transcript without timestamps
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

def create_agent_graph(vectorstore: FAISS, video_metadata: Dict[str, Any], has_timestamps: bool = False):
    """
    Create a LangGraph agent with tools for handling YouTube content queries.
    
    Args:
        vectorstore: The vector store to use for retrieval
        video_metadata: Metadata about the YouTube video
        has_timestamps: Whether the transcript has timestamps
        
    Returns:
        A LangGraph agent
    """
    # Create language model
    model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(temperature=0.2, model_name=model_name)
    
    # Create retriever tool
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    
    # Define the search tool with updated retriever usage
    if has_timestamps:
        yt_retriever_tool = Tool(
            name="YouTube_Video_Search",
            description=f"Useful for searching information in the YouTube video transcript. Use this tool when the user asks about the content of the video with ID {video_metadata['video_id']}.",
            func=lambda query: format_timestamped_results(retriever.invoke(query))
        )
    else:
        yt_retriever_tool = Tool(
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
    tools = [yt_retriever_tool, video_info_tool]
    
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

IMPORTANT: When answering questions about the video content, always include the timestamp citations from the transcript in your response. 
These timestamps indicate when in the video the information was mentioned. Format citations like [MM:SS] in your answers.

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

def format_timestamped_results(docs):
    """
    Format search results to include timestamps.
    
    Args:
        docs: The search results from the retriever
        
    Returns:
        Formatted search results with timestamps
    """
    results = []
    
    for doc in docs:
        content = doc.page_content
        metadata = doc.metadata
        
        # Add timestamp information if available
        if metadata and "start_time" in metadata and "end_time" in metadata:
            time_range = f"[{metadata['start_time']} to {metadata['end_time']}]"
            results.append(f"{time_range}\n{content}")
        else:
            results.append(content)
    
    return "\n\n".join(results)

def setup_chat_for_video(youtube_url: str, transcript: str, transcript_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Set up the chat functionality for a YouTube video.
    
    Args:
        youtube_url: The URL of the YouTube video
        transcript: The transcript of the video
        transcript_list: Optional list of transcript items with timestamps
        
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
        
        # Check if we have timestamped transcript
        has_timestamps = transcript_list is not None and len(transcript_list) > 0
        
        # Create vector store
        vectorstore = create_vectorstore(transcript, transcript_list)
        logger.info(f"Successfully created vector store for chat (with timestamps: {has_timestamps})")
        
        # Create video metadata
        video_metadata = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available")
        }
        
        # Create agent
        agent = create_agent_graph(vectorstore, video_metadata, has_timestamps)
        logger.info("Successfully created agent for chat")
        
        # Create thread ID for persistence
        thread_id = f"thread_{video_id}_{int(time.time())}"
        
        # Return chat setup details
        return {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "title": video_info.get("title", f"YouTube Video {video_id}"),
            "description": video_info.get("description", "No description available"),
            "agent": agent,
            "thread_id": thread_id,
            "has_timestamps": has_timestamps
        }
    except Exception as e:
        logger.error(f"Error setting up chat: {str(e)}")
        return None 