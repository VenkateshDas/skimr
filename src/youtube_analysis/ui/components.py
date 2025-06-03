"""
Streamlit UI components for displaying analysis results and chat interface.
"""

import streamlit as st
from typing import Dict, Any, List, Callable, Optional
import re
from datetime import datetime
import os

from ..utils.logging import get_logger
from ..utils.youtube_utils import clean_markdown_fences

logger = get_logger("ui_components")


def display_analysis_results(
    analysis_results: Dict[str, Any], 
    session_manager,
    on_demand_handler: Optional[Callable] = None
) -> None:
    """
    Display analysis results in a tabbed interface.
    
    Args:
        analysis_results: Dictionary containing analysis results
        session_manager: StreamlitSessionManager instance
        on_demand_handler: Callback function for generating additional content
    """
    if not analysis_results or "task_outputs" not in analysis_results:
        st.error("No analysis results to display")
        # Debug information
        if analysis_results:
            with st.expander("🔧 Debug - Available Keys"):
                st.json(list(analysis_results.keys()))
        return
    
    task_outputs = analysis_results.get("task_outputs", {})
    

    
    # Define tab configuration
    tab_config = [
        ("📊 Summary", "classify_and_summarize_content", "summary"),
        ("📋 Action Plan", "analyze_and_plan_content", "action_plan"),
        ("📝 Blog Post", "write_blog_post", "blog"),
        ("💼 LinkedIn Post", "write_linkedin_post", "linkedin"), 
        ("🐦 X Tweet", "write_tweet", "tweet"),
        ("📜 Transcript", "transcript", "transcript"),
        # ("🎬 Highlights", "highlights", "highlights")  # Disabled - keeping code for future use
    ]
    
    # Create tabs
    tabs = st.tabs([tab[0] for tab in tab_config])
    
    # Display content in each tab
    for idx, (tab_name, task_key, content_type) in enumerate(tab_config):
        with tabs[idx]:
            if content_type == "transcript":
                _display_transcript_tab(analysis_results, session_manager)
            elif content_type == "highlights":
                # Highlights disabled - keeping code for future use
                # _display_highlights_tab(analysis_results, session_manager)
                st.info("Video highlights feature is temporarily disabled.")
            else:
                # Regular content tabs
                content = task_outputs.get(task_key)
                if content:
                    # Handle both string content and TaskOutput objects
                    if isinstance(content, dict) and "content" in content:
                        # It's a TaskOutput dictionary
                        actual_content = content["content"]
                    elif isinstance(content, str):
                        # It's raw string content
                        actual_content = content
                    else:
                        # Try to extract content from object
                        actual_content = getattr(content, 'content', str(content))
                    
                    _display_content_with_copy(actual_content, content_type)
                    
                    # Disable regenerate for Summary tab
                    if task_key != "classify_and_summarize_content":
                        # Add custom instruction field for regeneration
                        st.markdown("---")
                        st.markdown("### Regenerate with Custom Instructions")
                        custom_instruction = st.text_area(
                            f"Add custom instructions for regenerating this {tab_name}",
                            key=f"custom_instruction_{task_key}",
                            placeholder="Example: Focus more on the technical aspects, or Add more actionable steps, etc."
                        )
                        if st.button(f"Regenerate {tab_name}", key=f"regen_tab_{task_key}"):
                            if on_demand_handler:
                                on_demand_handler(task_key)
                    
                else:
                    # Content not yet generated
                    if task_key == "classify_and_summarize_content":
                        # Special handling for summary - it should be the main analysis result
                        st.warning("📊 Analysis summary not available. This might indicate an issue with the analysis process.")
                        st.info("The summary should be automatically generated during video analysis. If you see this message, please try analyzing the video again or contact support.")
                        

                    else:
                        st.info(f"{tab_name} not yet generated.")
                        
                        # Add custom instruction field
                        st.markdown("### Custom Instructions")
                        custom_instruction = st.text_area(
                            f"Add custom instructions for this {tab_name}",
                            key=f"custom_instruction_{task_key}",
                            placeholder="Example: Focus more on the technical aspects, or Add more actionable steps, etc."
                        )
                        
                        if on_demand_handler:
                            # Pass the backend task_key instead of display name
                            if st.button(f"Generate {tab_name}", key=f"gen_tab_{task_key}"):
                                on_demand_handler(task_key)


def _display_content_with_copy(content: str, content_type: str) -> None:
    """Display content with raw markdown expander."""
    # Clean markdown fences if present
    cleaned_content = clean_markdown_fences(content)
    
    # Display the main content
    st.markdown(cleaned_content)
    
    # Add expander with raw markdown at the end
    with st.expander("📄 View Raw Markdown", expanded=False):
        st.code(content, language="markdown")


def _display_transcript_tab(analysis_results: Dict[str, Any], session_manager) -> None:
    """Display transcript with timestamp toggle, translation and export options."""
    st.markdown("### Video Transcript")
    
    # Get settings and transcript data
    settings = session_manager.get_settings()
    transcript_segments = analysis_results.get("transcript_segments", [])
    transcript_text = analysis_results.get("transcript", "")
    video_id = analysis_results.get("video_id")
    
    # Check for artificial segments or single segment from GPT-4o transcription
    is_artificial = False
    needs_artificial_segments = False
    
    # Case 1: Single segment with start time 0
    if len(transcript_segments) == 1 and transcript_segments[0].get("start", 0) == 0.0:
        is_artificial = True
        needs_artificial_segments = True
    
    # Case 2: No segments but have transcript text
    if not transcript_segments and transcript_text:
        needs_artificial_segments = True
    
    # Case 3: Few segments for a long transcript (likely GPT-4o)
    if transcript_segments and len(transcript_segments) < 3 and len(transcript_text) > 1000:
        needs_artificial_segments = True
    
    # If we need artificial segments, create them
    if needs_artificial_segments and transcript_text and video_id:
        with st.spinner("Creating segmented subtitles..."):
            from youtube_analysis.service_factory import get_transcript_service
            transcript_service = get_transcript_service()
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            # Get the selected transcription model from settings
            transcription_model = settings.get("transcription_model", "openai")
            # Try to get or create proper segments
            artificial_segments = transcript_service.get_or_create_segments_sync(youtube_url, transcription_model=transcription_model)
            if artificial_segments and len(artificial_segments) > 1:
                transcript_segments = artificial_segments
                is_artificial = True
                st.info("📌 Timestamps are estimated based on text length")
    
    # Get current language settings
    target_language = settings.get("subtitle_language", "en")
    
    # Detect source language from transcript text
    from youtube_analysis.utils.subtitle_utils import detect_language
    source_language = analysis_results.get("detected_language")
    
    # If source language not already detected, detect it now
    if not source_language and transcript_text:
        source_language = detect_language(transcript_text)
    
    # If still no source language or unknown, default to English
    if not source_language or source_language == "unknown":
        # Check for Hindi characters
        devanagari_chars = sum(1 for c in transcript_text if '\u0900' <= c <= '\u097F')
        if devanagari_chars > 0:
            source_language = "hi"
        else:
            source_language = "en"  # Default fallback
    
    # Create columns for controls
    col1, col2, col3 = st.columns([1, 1, 1])
    
    # Toggle for timestamps
    with col1:
        show_timestamps = st.checkbox("Show timestamps", value=True, key="transcript_timestamps")
    
    # Get or create translated segments
    translated_segments = None
    translated_text = None
    
    # Get subtitles data for video player from session state
    subtitles_player_key = f"subtitles_for_player_{video_id}"
    subtitles_data_for_player = session_manager.get_state(subtitles_player_key, {})
        
    # Add original language subtitles to subtitles_data_for_player
    if transcript_segments:
        if source_language not in subtitles_data_for_player or subtitles_data_for_player[source_language].get("segments") != transcript_segments:
            subtitles_data_for_player[source_language] = {
                "segments": transcript_segments,
                # Default if no other language is default, or if it's the only one
                "default": not any(info.get("default") for lang, info in subtitles_data_for_player.items() if lang != source_language)
            }

    # Translation button
    with col2:
        from youtube_analysis.utils.language_utils import get_language_name
        translate_label = f"Translate to {get_language_name(target_language)}"
        translate_key = f"translate_to_{target_language}"
        
        # Check session for cached translation (for display, not for player data yet)
        session_translation_key = f"translated_segments_for_display_{video_id}_{target_language}"
        # This key refers to the translated segments specifically for display in the transcript tab
        # It's separate from subtitles_player_key which is for the video player
        
        cached_translated_segments_for_display = session_manager.get_state(session_translation_key)

        if cached_translated_segments_for_display:
            translated_segments = cached_translated_segments_for_display # Use this for display
            translated_text = " ".join([seg.get("text", "") for seg in translated_segments])
            st.success(f"✅ Translation to {get_language_name(target_language)} available")
            
            # Ensure this translation is also in subtitles_data_for_player and set as default
            if target_language not in subtitles_data_for_player or subtitles_data_for_player[target_language].get("segments") != translated_segments:
                subtitles_data_for_player[target_language] = {
                    "segments": translated_segments,
                    "default": True
                }
                if source_language in subtitles_data_for_player and source_language != target_language:
                    subtitles_data_for_player[source_language]["default"] = False
        
        elif target_language != source_language:
            if st.button(translate_label, key=translate_key):
                with st.spinner(f"Translating to {get_language_name(target_language)}..."):
                    try:
                        from youtube_analysis.service_factory import get_translation_service
                        translation_service = get_translation_service()
                        
                        current_segments_to_translate = transcript_segments # Always translate original
                        
                        # Perform translation
                        api_translated_text, api_translated_segments = translation_service.translate_transcript_sync(
                            segments=current_segments_to_translate,
                            source_language=source_language, 
                            target_language=target_language,
                            video_id=video_id 
                        )
                        
                        if api_translated_segments:
                            translated_segments = api_translated_segments # For display
                            translated_text = api_translated_text       # For display
                            
                            # Store translated segments for display in session state
                            session_manager.set_state(session_translation_key, translated_segments)
                            
                            # Update subtitles_data_for_player with the new translation and set as default
                            subtitles_data_for_player[target_language] = {
                                "segments": translated_segments, # Use the fresh translation
                                "default": True
                            }
                            if source_language in subtitles_data_for_player and source_language != target_language:
                                subtitles_data_for_player[source_language]["default"] = False
                                
                            st.success(f"Successfully translated to {get_language_name(target_language)}")
                            # We need to rerun to reflect the translated text in the text_area
                            st.rerun() 
                        else:
                            st.error("Translation failed. Please try again.")
                    except Exception as e:
                        logger.error(f"Error during translation: {e}")
                        st.error(f"Translation error: {e}")
        else: # Source and target are the same
             if target_language == source_language and transcript_segments:
                # If they are same, ensure original is default in player data
                if source_language in subtitles_data_for_player:
                     subtitles_data_for_player[source_language]["default"] = True
                # Remove other languages from being default
                for lang_code in list(subtitles_data_for_player.keys()):
                    if lang_code != source_language:
                        subtitles_data_for_player[lang_code]["default"] = False


    # Always save the potentially modified subtitles_data_for_player back to session state
    session_manager.set_state(subtitles_player_key, subtitles_data_for_player)

    # Display transcript (original or translated)
    display_segments = transcript_segments
    current_transcript_text = transcript_text
    
    if translated_segments and target_language != source_language:
        st.markdown(f"### Translated Transcript ({get_language_name(target_language)})")
        display_segments = translated_segments
        current_transcript_text = translated_text if translated_text else " ".join([s.get("text","") for s in translated_segments])
    else:
        st.markdown(f"### Original Transcript ({get_language_name(source_language)})")

    if display_segments:
        # Always display transcript in a scrollable text box, with or without timestamps
        if show_timestamps:
            from ..utils.subtitle_utils import format_srt_time
            transcript_with_timestamps = "\n".join([
                f"[{format_srt_time(seg.get('start', 0))} --> {format_srt_time(seg.get('start', 0) + (seg.get('duration', 2.0) or 2.0))}] {seg.get('text', '')}" for seg in display_segments
            ])
            st.text_area(
                "Transcript (with timestamps)",
                value=transcript_with_timestamps,
                height=400,
                key="transcript_text_area_timestamps",
                label_visibility="collapsed"
            )
        else:
            st.text_area(
                "Full Transcript",
                value=current_transcript_text,
                height=400,
                key="transcript_text_area_full",
                label_visibility="collapsed"
            )
    else:
        st.info("Transcript not available")

    # Subtitle file generation and download options
    with col3:
        st.markdown("""
            <div style="height: 28px;"></div> 
        """, unsafe_allow_html=True) # Spacer to align with checkbox and button
        
        # Get the latest subtitles_data_for_player for the button states
        current_subtitles_for_player_for_button = session_manager.get_state(subtitles_player_key, {})
        can_apply_or_download = bool(current_subtitles_for_player_for_button and any(info.get("segments") for info in current_subtitles_for_player_for_button.values()))

        if st.button("✔ Apply Subtitles to Video Player", key="apply_subtitles_button", disabled=not can_apply_or_download):
            if video_id and current_subtitles_for_player_for_button: # Check again before setting
                session_manager.set_state("show_video_with_subtitles", True)
                session_manager.set_state("video_id_for_subtitles", video_id)
                st.success("Subtitles applied! Player will update.")
                st.rerun() # Rerun to update the player display
            else:
                st.warning("No subtitle data available to apply.")
        
        # Download options
        # Determine which segments to use for download (original or translated)
        segments_for_download = transcript_segments # Default to original
        export_language = source_language
        
        if translated_segments and target_language != source_language:
            segments_for_download = translated_segments
            export_language = target_language
            
        if segments_for_download:
            st.markdown("#### Download Options:")
            from ..utils.subtitle_utils import create_subtitle_files
            
            # Generate subtitle files
            subtitle_files = create_subtitle_files(
                segments=segments_for_download, 
                video_id=video_id, 
                language=export_language
            )
            
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                if "srt" in subtitle_files and os.path.exists(subtitle_files["srt"]):
                    with open(subtitle_files["srt"], "r", encoding="utf-8") as f_srt:
                        st.download_button(
                            label=f"Download SRT ({get_language_name(export_language)})",
                            data=f_srt.read(),
                            file_name=f"{video_id}_{export_language}.srt",
                            mime="text/plain",
                            key=f"download_srt_{export_language}"
                        )
            
            with col_dl2:
                if "vtt" in subtitle_files and os.path.exists(subtitle_files["vtt"]):
                    with open(subtitle_files["vtt"], "r", encoding="utf-8") as f_vtt:
                        st.download_button(
                            label=f"Download VTT ({get_language_name(export_language)})",
                            data=f_vtt.read(),
                            file_name=f"{video_id}_{export_language}.vtt",
                            mime="text/vtt",
                            key=f"download_vtt_{export_language}"
                        )
        else:
            st.info("No transcript segments available for download.")
            
    st.markdown("---") # Final separator for the tab


def _display_highlights_tab(analysis_results: Dict[str, Any], session_manager) -> None:
    """Display video highlights."""
    highlights = analysis_results.get("highlights")
    
    if highlights:
        st.markdown("### Key Video Moments")
        for idx, highlight in enumerate(highlights):
            with st.expander(f"Highlight {idx + 1}: {highlight.get('title', 'Untitled')}", expanded=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(highlight.get('description', ''))
                with col2:
                    timestamp = highlight.get('timestamp', '0:00')
                    st.metric("Timestamp", timestamp)
    else:
        st.info("Video highlights not yet generated.")
        if st.button("Generate Highlights", key="gen_highlights"):
            st.info("Highlight generation is coming soon!")


def display_chat_interface(
    analysis_results: Dict[str, Any],
    on_message: Callable[[str], None],
    on_reset: Callable[[], None] = None
) -> None:
    """
    Display chat interface with message history and input.
    
    Args:
        analysis_results: Analysis results dictionary
        on_message: Callback function when user submits a message
        on_reset: Callback function when user resets chat
    """
    st.markdown("### 💬 Video Chat")
    
    # Get chat messages and streaming state from session state
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    session_id = get_script_run_ctx().session_id
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        
    if "is_chat_streaming" not in st.session_state:
        st.session_state.is_chat_streaming = False
        
    if "chat_streaming_placeholder" not in st.session_state:
        st.session_state.chat_streaming_placeholder = ""
    
    chat_messages = st.session_state.chat_messages
    is_streaming = st.session_state.is_chat_streaming
    streaming_response_placeholder = st.session_state.chat_streaming_placeholder
    
    # Check if we have video info for the welcome message
    video_title = analysis_results.get("video_info", {}).get("title", "this video")
    
    # Initialize chat with welcome message if empty
    if not chat_messages:
        from youtube_analysis.core.config import CHAT_WELCOME_TEMPLATE
        welcome_msg = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
        chat_messages.append({"role": "assistant", "content": welcome_msg})
    
    # Create a container for the chat messages with fixed height for scrolling
    chat_container = st.container(height=380)
    
    with chat_container:
        # Display all messages in the chat container
        for i, message in enumerate(chat_messages):
            role = message["role"]
            content = message["content"]
            
            # Skip thinking messages or empty content
            if role == "thinking" or not content:
                continue
                
            # Display user messages
            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
            
            # Display assistant messages
            elif role == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(content)
        
        # Handle streaming response
        if is_streaming:
            with st.chat_message("assistant", avatar="🤖"):
                if streaming_response_placeholder:
                    placeholder = st.empty()
                    placeholder.markdown(streaming_response_placeholder + "▌")
                    # Store reference for streaming updates
                    st.session_state["chat_streaming_placeholder_ref"] = placeholder
                else:
                    st.markdown("*Thinking...*")
    
    # Add a user input field outside the message container
    user_input = st.chat_input("Ask a question about the video...", disabled=is_streaming)
    
    # Handle user input
    if user_input and not is_streaming:
        on_message(user_input.strip())
    
    # Add reset button
    if on_reset and len(chat_messages) > 1:
        st.button("Reset Chat", on_click=on_reset, key="reset_chat_button")


def display_performance_stats(performance_stats: Dict[str, Any]) -> None:
    """Display Phase 2 architecture performance statistics."""
    st.markdown("### ⚡ Performance Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cache_stats = performance_stats.get("cache_stats", {})
        st.metric(
            "Cache Hit Rate",
            f"{cache_stats.get('hit_rate', 0):.1%}",
            delta=f"{cache_stats.get('hits', 0)} hits"
        )
    
    with col2:
        connection_stats = performance_stats.get("connection_stats", {})
        st.metric(
            "Connection Pool",
            f"{connection_stats.get('active', 0)} active",
            delta=f"{connection_stats.get('reused', 0)} reused"
        )
    
    with col3:
        timing_stats = performance_stats.get("timing", {})
        total_time = timing_stats.get("total", 0)
        st.metric(
            "Analysis Time",
            f"{total_time:.1f}s",
            delta=f"-{timing_stats.get('saved', 0):.1f}s saved"
        )
    
    # Detailed breakdown
    with st.expander("Detailed Performance Breakdown", expanded=False):
        if "operation_times" in performance_stats:
            st.markdown("#### Operation Times")
            for operation, time in performance_stats["operation_times"].items():
                st.text(f"{operation}: {time:.2f}s")
        
        if "resource_usage" in performance_stats:
            st.markdown("#### Resource Usage")
            resource = performance_stats["resource_usage"]
            st.text(f"Memory: {resource.get('memory_mb', 0):.1f} MB")
            st.text(f"CPU: {resource.get('cpu_percent', 0):.1f}%")