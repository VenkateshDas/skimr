"""
Temporary module for webapp functions that haven't been fully migrated yet.
This will be cleaned up in future iterations.
"""

import streamlit as st
from typing import Optional
import traceback

from .utils.logging import get_logger

logger = get_logger("webapp_functions")


def handle_chat_input():
    """
    Temporary placeholder for chat input handling.
    Process the chat input using the agent from chat_details.
    """
    logger.warning("Using temporary chat input handler - full implementation needed")
    
    # Simple placeholder implementation
    if st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "thinking":
        try:
            # Get chat details
            chat_details = st.session_state.get("chat_details", {})
            agent = chat_details.get("agent")
            
            if not agent:
                logger.error("No agent found in chat_details")
                st.session_state.chat_messages[-1] = {
                    "role": "assistant",
                    "content": "Sorry, I couldn't find the chat agent. Please try analyzing the video again."
                }
                st.rerun()
                return
                
            # Get the user message (the one before "thinking")
            user_message = None
            for i in range(len(st.session_state.chat_messages) - 1, -1, -1):
                if st.session_state.chat_messages[i]["role"] == "user":
                    user_message = st.session_state.chat_messages[i]["content"]
                    break
            
            if not user_message:
                logger.error("No user message found before thinking message")
                st.session_state.chat_messages[-1] = {
                    "role": "assistant",
                    "content": "Sorry, I couldn't process your question. Please try again."
                }
                st.rerun()
                return
            
            # Convert messages to format expected by agent
            from langchain_core.messages import HumanMessage, AIMessage
            messages = []
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant" and msg["role"] != "thinking":
                    messages.append(AIMessage(content=msg["content"]))
            
            # Ensure the last message is the user's question
            if not messages or messages[-1].type != "human":
                messages.append(HumanMessage(content=user_message))
            
            # Get response from agent
            logger.info(f"Invoking agent with query: {user_message}")
            try:
                # Try to get a response with the agent
                thread_id = chat_details.get("thread_id", f"thread_{st.session_state.get('video_id', 'default')}")
                response = agent.invoke(
                    {"messages": messages},
                    config={"configurable": {"thread_id": thread_id}} if thread_id else None
                )
                
                # Extract the text response from different possible formats
                if isinstance(response, dict):
                    if "answer" in response:
                        answer = response["answer"]
                    elif "messages" in response and response["messages"]:
                        answer = response["messages"][-1].content
                    elif "output" in response:
                        answer = response["output"]
                    else:
                        answer = str(response)
                elif hasattr(response, "content"):
                    answer = response.content
                else:
                    answer = str(response)
                
                logger.info(f"Got response from agent: {answer[:100]}...")
                
                # Replace thinking message with the response
                st.session_state.chat_messages[-1] = {
                    "role": "assistant",
                    "content": answer
                }
            except Exception as e:
                logger.error(f"Error getting response from agent: {str(e)}")
                logger.error(f"Error details: {traceback.format_exc()}")
                st.session_state.chat_messages[-1] = {
                    "role": "assistant",
                    "content": f"Sorry, I encountered an error while processing your question: {str(e)}"
                }
        except Exception as e:
            logger.error(f"Error in handle_chat_input: {str(e)}")
            logger.error(f"Error details: {traceback.format_exc()}")
            st.session_state.chat_messages[-1] = {
                "role": "assistant",
                "content": f"Sorry, I encountered an error while processing your question: {str(e)}"
            }
        
        # Rerun to update the UI
        st.rerun()