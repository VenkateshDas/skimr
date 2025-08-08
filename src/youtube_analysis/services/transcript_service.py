"""Service for transcript operations."""

from typing import Optional, Tuple, List, Dict, Any
import asyncio
import re
from ..models import VideoData, TranscriptSegment
from ..transcription import WhisperTranscriber, TranscriptUnavailable
from ..repositories import CacheRepository, YouTubeRepository
from ..utils.logging import get_logger
from ..utils.language_utils import get_language_name, validate_language_code

logger = get_logger("transcript_service")


class TranscriptService:
    """Service for transcript-related operations."""
    
    def __init__(self, cache_repository: CacheRepository, youtube_repository: YouTubeRepository):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        self.whisper_transcriber = WhisperTranscriber()
        logger.info("Initialized TranscriptService")
    
    async def get_transcript(self, youtube_url: str, use_cache: bool = True) -> Optional[str]:
        """Get plain transcript for a video."""
        video_data = await self._get_video_data(youtube_url, use_cache)
        return video_data.transcript if video_data else None
    
    async def get_timestamped_transcript(
        self, 
        youtube_url: str, 
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Get timestamped transcript and segment list."""
        video_data = await self._get_video_data(youtube_url, use_cache)
        if not video_data:
            return None, None
        
        transcript_list = None
        if video_data.transcript_segments:
            transcript_list = [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                }
                for seg in video_data.transcript_segments
            ]
        
        return video_data.timestamped_transcript, transcript_list
    
    async def get_formatted_transcripts(
        self,
        youtube_url: str,
        video_id: str,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Get formatted transcripts for a video.
        
        Args:
            youtube_url: YouTube URL
            video_id: Video ID
            use_cache: Whether to use cached data
            
        Returns:
            Tuple of (timestamped transcript string, segment list)
        """
        video_data = await self._get_video_data(youtube_url, use_cache)
        if not video_data:
            return None, None
        
        # Format transcript with timestamps
        timestamped_transcript = ""
        transcript_segments = []
        
        if video_data.transcript_segments:
            for seg in video_data.transcript_segments:
                # Format timestamp
                start = seg.start
                minutes, seconds = divmod(int(start), 60)
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                
                # Add to timestamped transcript
                timestamped_transcript += f"{timestamp} {seg.text}\n"
                
                # Add to segments list
                transcript_segments.append({
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                })
        
        return timestamped_transcript, transcript_segments
    
    def get_transcript_sync(self, youtube_url: str, use_cache: bool = True) -> Optional[List[Dict[str, Any]]]:
        """
        Synchronous method to get transcript, used as a fallback for the webapp.
        
        Args:
            youtube_url: The YouTube video URL
            use_cache: Whether to use cached data
            
        Returns:
            List of transcript segments or None if error
        """
        try:
            # Get video data synchronously
            video_data = self.get_video_data_sync(youtube_url, use_cache)
            
            # If we have valid video data with transcript segments, use it
            if video_data and video_data.transcript_segments:
                # Convert transcript segments to dictionary format
                transcript_list = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration
                    }
                    for seg in video_data.transcript_segments
                ]
                logger.info(f"Successfully retrieved transcript segments from video data for {youtube_url}")
                return transcript_list
            
            # If no segments in video data, try direct YouTube API call
            video_id = self.youtube_repo.extract_video_id(youtube_url)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {youtube_url}")
                return None
            
            # Try using YouTubeTranscriptApi directly
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'de', 'ta', 'es', 'fr'])
                logger.info(f"Retrieved transcript directly using YouTubeTranscriptApi for {video_id}")
                return transcript_list
            except Exception as yt_api_error:
                logger.error(f"Error using YouTubeTranscriptApi directly: {str(yt_api_error)}")
                
                # Try to get transcript asynchronously as a last resort
                try:
                    transcript_text = asyncio.run(self.get_transcript(youtube_url, use_cache))
                    if transcript_text:
                        # Create a simple transcript segment with the full text
                        logger.info(f"Created simple transcript segment from plain text for {video_id}")
                        return [{"text": transcript_text, "start": 0.0, "duration": 0.0}]
                    else:
                        # Try Whisper transcription as final fallback
                        logger.info(f"Attempting Whisper transcription as final fallback for {video_id}")
                        whisper_result = asyncio.run(self.get_transcript_with_whisper(youtube_url, use_cache=use_cache))
                        if whisper_result and len(whisper_result) == 2:
                            _, segments = whisper_result
                            if segments:
                                logger.info(f"Successfully transcribed {video_id} with Whisper")
                                return segments
                            
                        logger.error(f"Could not retrieve transcript for {video_id}")
                        return None
                except Exception as async_error:
                    logger.error(f"Error in async transcript retrieval fallback: {str(async_error)}")
                    return None
        except Exception as e:
            logger.error(f"Error in get_transcript_sync: {str(e)}")
            return None
    
    def get_video_data_sync(self, youtube_url: str, use_cache: bool = True) -> Optional[VideoData]:
        """
        Synchronous wrapper for _get_video_data.
        
        Args:
            youtube_url: The YouTube video URL
            use_cache: Whether to use cached data
            
        Returns:
            VideoData object or None if error
        """
        try:
            # Use asyncio.run to execute the async method
            video_data = asyncio.run(self._get_video_data(youtube_url, use_cache))
            
            # Verify that video_data is not a coroutine
            if asyncio.iscoroutine(video_data):
                logger.warning(f"get_video_data_sync received a coroutine, attempting to resolve it")
                try:
                    # Run the coroutine
                    video_data = asyncio.run(video_data)
                except Exception as coroutine_error:
                    logger.error(f"Error resolving coroutine in get_video_data_sync: {str(coroutine_error)}")
                    return None
            
            # Ensure video_data is a proper VideoData object
            from ..models import VideoData as VideoDataModel
            if not isinstance(video_data, VideoDataModel):
                logger.warning(f"get_video_data_sync got unexpected type: {type(video_data)}, expected VideoData")
                # If it's a dict, try to convert it to VideoData
                if isinstance(video_data, dict):
                    try:
                        return VideoDataModel.from_dict(video_data)
                    except Exception as convert_error:
                        logger.error(f"Error converting dict to VideoData: {str(convert_error)}")
                        return None
                return None
            
            return video_data
        except Exception as e:
            logger.error(f"Error in get_video_data_sync: {str(e)}")
            return None
    
    async def _get_video_data(self, youtube_url: str, use_cache: bool = True) -> Optional[VideoData]:
        """Get video data from cache or fetch fresh."""
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            return None
        
        if use_cache:
            video_data = await self.cache_repo.get_video_data(video_id)
            if video_data:
                return video_data
        
        # Fetch fresh data
        video_data = await self.youtube_repo.get_video_data(youtube_url)
        if video_data:
            await self.cache_repo.store_video_data(video_data)
        
        return video_data
    
    async def get_transcript_with_whisper(
        self, 
        youtube_url: str, 
        language: str = "en", 
        model_name: str = None,
        use_cache: bool = True,
        transcription_model: str = "openai"
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Get transcript using OpenAI or Groq Whisper API directly.
        Args:
            youtube_url: YouTube URL
            language: ISO-639-1 language code
            model_name: Whisper model to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
            use_cache: Whether to use cached transcript
            transcription_model: 'openai' or 'groq'
        Returns:
            Tuple of (transcript text, segment list) or None if error
        """
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {youtube_url}")
            return None
        cache_key = f"whisper_transcript_{video_id}_{language}_{model_name or 'default'}_{transcription_model}"
        if use_cache:
            cached_data = await self.cache_repo.get_custom_data("transcripts", cache_key)
            if cached_data:
                logger.info(f"Using cached Whisper transcript for {video_id}")
                return cached_data.get("text"), cached_data.get("segments")
        try:
            logger.info(f"Transcribing {video_id} with Whisper API ({transcription_model})")
            whisper_transcriber = WhisperTranscriber(provider=transcription_model, default_model=model_name)
            transcript_obj = await whisper_transcriber.get(
                video_id=video_id, 
                language=language,
                model_name=model_name
            )
            if not transcript_obj or not transcript_obj.segments:
                logger.warning(f"Whisper transcription failed for {video_id}")
                return None
            segments_list = [
                {
                    "text": segment.text,
                    "start": segment.start,
                    "duration": segment.duration or 0
                }
                for segment in transcript_obj.segments
            ]
            transcript_text = transcript_obj.text
            if use_cache:
                await self.cache_repo.store_custom_data(
                    "transcripts", 
                    cache_key, 
                    {
                        "text": transcript_text,
                        "segments": segments_list
                    }
                )
            logger.info(f"Successfully transcribed {video_id} with Whisper ({transcription_model})")
            return transcript_text, segments_list
        except TranscriptUnavailable as e:
            logger.warning(f"Whisper transcription unavailable for {video_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error in Whisper transcription for {video_id}: {str(e)}")
            return None

    def get_transcript_with_whisper_sync(
        self, 
        youtube_url: str, 
        language: str = "en", 
        model_name: str = None,
        use_cache: bool = True,
        transcription_model: str = "openai"
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Synchronous method to get transcript using Whisper.
        Args:
            youtube_url: YouTube URL
            language: ISO-639-1 language code
            model_name: Whisper model to use
            use_cache: Whether to use cached transcript
            transcription_model: 'openai' or 'groq'
        Returns:
            Tuple of (transcript text, segment list) or None if error
        """
        try:
            return asyncio.run(self.get_transcript_with_whisper(
                youtube_url=youtube_url, 
                language=language, 
                model_name=model_name, 
                use_cache=use_cache,
                transcription_model=transcription_model
            ))
        except Exception as e:
            logger.error(f"Error in get_transcript_with_whisper_sync: {str(e)}")
            return None

    async def _create_artificial_segments(self, text: str, video_duration: float) -> List[Dict[str, Any]]:
        """
        Create artificial segments with estimated timestamps for a text without timestamps.
        Args:
            text: Complete transcript text
            video_duration: Duration of the video in seconds
        Returns:
            List of artificial segments with estimated timestamps
        """
        AVG_CHARS_PER_SECOND = 13  # Average speaking rate
        MAX_SEGMENT_LENGTH = 180   # Maximum characters in a segment

        # Split text into sentences
        sentence_endings = re.compile(r'(?<=[.!?]) +')
        sentences = [s.strip() for s in sentence_endings.split(text) if s.strip()]

        segments = []
        current_position = 0.0
        current_segment = ""

        for sentence in sentences:
            if len(current_segment) + len(sentence) > MAX_SEGMENT_LENGTH and current_segment:
                segment_duration = len(current_segment) / AVG_CHARS_PER_SECOND
                segments.append({
                    "text": current_segment,
                    "start": current_position,
                    "duration": segment_duration
                })
                current_position += segment_duration
                current_segment = sentence
            else:
                if current_segment:
                    current_segment += " " + sentence
                else:
                    current_segment = sentence

        # Add the last segment
        if current_segment:
            segment_duration = len(current_segment) / AVG_CHARS_PER_SECOND
            segments.append({
                "text": current_segment,
                "start": current_position,
                "duration": segment_duration
            })

        # Adjust timing to fit video duration
        total_duration = sum(seg["duration"] for seg in segments)
        if total_duration > 0 and video_duration > 0:
            scale = video_duration / total_duration
            for seg in segments:
                seg["start"] *= scale
                seg["duration"] *= scale

        return segments
    
    async def get_or_create_segments(self, youtube_url: str, use_cache: bool = True, transcription_model: str = "openai") -> List[Dict[str, Any]]:
        """
        Get proper transcript segments or create artificial ones if needed.
        Args:
            youtube_url: YouTube URL
            use_cache: Whether to use cached data
            transcription_model: 'openai' or 'groq'
        Returns:
            List of transcript segments
        """
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            return []
        video_data = await self._get_video_data(youtube_url, use_cache)
        if not video_data:
            return []
        if (video_data.transcript_segments and 
            len(video_data.transcript_segments) > 1):
            return [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                }
                for seg in video_data.transcript_segments
            ]
        if (video_data.transcript_segments and 
            len(video_data.transcript_segments) == 1 and
            video_data.transcript):
            if len(video_data.transcript) < 200:
                return [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration
                    }
                    for seg in video_data.transcript_segments
                ]
            video_info = await self.youtube_repo._get_video_info(youtube_url)
            video_duration = getattr(video_info, 'duration', 0) if video_info else 0
            if not video_duration:
                video_duration = len(video_data.transcript) / 10
            return await self._create_artificial_segments(
                video_data.transcript, 
                video_duration
            )
        if video_data.transcript:
            video_info = await self.youtube_repo._get_video_info(youtube_url)
            video_duration = getattr(video_info, 'duration', 0) if video_info else 0
            return await self._create_artificial_segments(
                video_data.transcript, 
                video_duration
            )
        # If no transcript at all, try Whisper fallback with selected provider
        whisper_result = await self.get_transcript_with_whisper(
            youtube_url=youtube_url,
            language="en",
            model_name=None,
            use_cache=use_cache,
            transcription_model=transcription_model
        )
        if whisper_result and len(whisper_result) == 2:
            _, segments = whisper_result
            if segments:
                return segments
        return []

    def get_or_create_segments_sync(self, youtube_url: str, use_cache: bool = True, transcription_model: str = "openai") -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for get_or_create_segments.
        """
        try:
            return asyncio.run(self.get_or_create_segments(youtube_url, use_cache, transcription_model=transcription_model))
        except Exception as e:
            logger.error(f"Error in get_or_create_segments_sync: {str(e)}")
            return []
    
    async def translate_transcript(
        self,
        youtube_url: str,
        target_language: str,
        source_language: str = None,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Translate transcript to target language.
        
        Args:
            youtube_url: YouTube URL
            target_language: ISO-639-1 language code for target language
            source_language: ISO-639-1 language code for source (if known)
            use_cache: Whether to use cached translations
            
        Returns:
            Tuple of (translated transcript text, translated segment list)
        """
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {youtube_url}")
            return None, None
        
        # Create a unique cache key for this translation
        cache_key = f"translated_transcript_{video_id}_{target_language}"
        
        # Try to get from cache first
        if use_cache:
            cached_data = await self.cache_repo.get_custom_data("translations", cache_key)
            if cached_data:
                logger.info(f"Using cached translation for {video_id} to {target_language}")
                return cached_data.get("text"), cached_data.get("segments")
        
        # Get segments (real or artificial)
        original_segments = await self.get_or_create_segments(youtube_url, use_cache)
        if not original_segments:
            logger.error(f"No transcript segments available for {video_id}")
            return None, None
        
        # Get complete transcript text (for reference)
        original_transcript = " ".join([seg["text"] for seg in original_segments])
        
        # Perform translation
        try:
            translated_text, translated_segments = await self._translate_segments(
                original_segments, 
                target_language
            )
            
            # Cache the results
            if use_cache:
                await self.cache_repo.store_custom_data(
                    "translations",
                    cache_key,
                    {
                        "text": translated_text,
                        "segments": translated_segments
                    }
                )
            
            logger.info(f"Successfully translated transcript for {video_id} to {target_language}")
            return translated_text, translated_segments
            
        except Exception as e:
            logger.error(f"Error translating transcript for {video_id}: {str(e)}")
            return None, None
    
    async def _translate_segments(
        self,
        segments: List[Dict[str, Any]],
        target_language: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Translate transcript segments to the target language.
        
        Args:
            segments: List of transcript segments
            target_language: ISO-639-1 language code for target language
            
        Returns:
            Tuple of (full translated text, translated segments list)
        """
        try:
            import openai
            from ..core.config import config
            import concurrent.futures
            import asyncio
            
            # Validate language code
            if not validate_language_code(target_language):
                raise ValueError(f"Invalid language code: {target_language}")
                
            target_language_name = get_language_name(target_language)
            
            # For efficiency, batch segments for translation
            batch_size = 10  # Adjust based on testing
            segment_batches = [segments[i:i+batch_size] for i in range(0, len(segments), batch_size)]
            
            translated_segments = []
            
            for batch in segment_batches:
                texts_to_translate = [segment["text"] for segment in batch]
                combined_text = "\n".join(texts_to_translate)
                system_message = f"Translate the following subtitles to {target_language_name}. Maintain the original meaning and style. Do not add or remove information."
                
                # Try OpenAI v1.x sync API in a thread
                def sync_openai_call():
                    try:
                        client = openai.OpenAI()
                        return client.chat.completions.create(
                            model=config.llm.default_model,
                            messages=[
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": combined_text}
                            ],
                            temperature=0.3,
                            max_tokens=2000,
                        )
                    except Exception as e:
                        return e
                
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(None, sync_openai_call)
                    if isinstance(response, Exception):
                        raise response
                    translated_text = response.choices[0].message.content.strip()
                except Exception as e:
                    # Fallback for OpenAI v0.x
                    try:
                        response = await openai.ChatCompletion.acreate(
                            model=config.llm.default_model,
                            messages=[
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": combined_text}
                            ],
                            temperature=0.3,
                            max_tokens=2000,
                        )
                        translated_text = response.choices[0].message["content"].strip()
                    except Exception as e2:
                        logger.error(f"Translation error (both APIs failed): {e2}")
                        raise
                
                translated_lines = translated_text.split("\n")
                
                # Handle case where lines don't match (should be rare with proper prompting)
                if len(translated_lines) != len(batch):
                    logger.warning(f"Translation returned {len(translated_lines)} lines but expected {len(batch)} lines")
                    if len(translated_lines) < len(batch):
                        translated_lines.extend([""] * (len(batch) - len(translated_lines)))
                    else:
                        translated_lines = translated_lines[:len(batch)]
                
                for i, segment in enumerate(batch):
                    translated_segment = segment.copy()
                    translated_segment["text"] = translated_lines[i]
                    translated_segments.append(translated_segment)
            
            full_translated_text = " ".join([segment["text"] for segment in translated_segments])
            return full_translated_text, translated_segments
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            raise
    
    def translate_transcript_sync(
        self,
        youtube_url: str,
        target_language: str,
        source_language: str = None,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Synchronous wrapper for translate_transcript.
        """
        try:
            # First, validate languages
            from ..utils.language_utils import validate_language_code, get_language_name
            
            if not validate_language_code(target_language):
                logger.error(f"Invalid target language code: {target_language}")
                return None, None
                
            if source_language and not validate_language_code(source_language):
                logger.warning(f"Invalid source language code: {source_language}, will auto-detect")
                source_language = None
            
            # Extract video ID for logging
            video_id = self.youtube_repo.extract_video_id(youtube_url)
            if not video_id:
                logger.error(f"Invalid YouTube URL: {youtube_url}")
                return None, None
            
            # Log the translation attempt
            logger.info(f"Starting translation for video {video_id} to {target_language} (source: {source_language or 'auto'})")
            
            try:
                result = asyncio.run(self.translate_transcript(
                    youtube_url=youtube_url,
                    target_language=target_language,
                    source_language=source_language,
                    use_cache=use_cache
                ))
                
                # Log success or failure
                if result and len(result) == 2 and result[0] and result[1]:
                    text, segments = result
                    logger.info(f"Successfully translated video {video_id} to {target_language}: {len(segments)} segments")
                    return result
                else:
                    logger.error(f"Translation returned empty result for video {video_id}")
                    return None, None
                    
            except asyncio.CancelledError:
                logger.error(f"Translation was cancelled for video {video_id}")
                return None, None
            except RuntimeError as re:
                if "already running" in str(re):
                    # Handle case when event loop is already running
                    logger.warning(f"Event loop already running, using thread-safe translation for {video_id}")
                    
                    # Create a new event loop in a thread to run the translation
                    import threading
                    import concurrent.futures
                    
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(self.translate_transcript(
                                youtube_url=youtube_url,
                                target_language=target_language,
                                source_language=source_language,
                                use_cache=use_cache
                            ))
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        try:
                            result = future.result(timeout=120)  # 2 minute timeout
                            if result and len(result) == 2:
                                logger.info(f"Successfully translated video {video_id} in thread")
                                return result
                        except concurrent.futures.TimeoutError:
                            logger.error(f"Translation timed out for video {video_id}")
                            return None, None
                
                logger.error(f"Runtime error in translate_transcript_sync: {str(re)}")
                return None, None
        except Exception as e:
            logger.error(f"Error in translate_transcript_sync: {str(e)}", exc_info=True)
            return None, None
    
    # Removed unused subtitle generation via external service to keep code lean
    
    def generate_subtitle_file_from_segments(
        self,
        segments: List[Dict[str, Any]],
        output_subtitle_path: str,
        language: str = "en"
    ) -> Optional[str]:
        """
        Generate subtitle file from existing transcript segments.
        
        Args:
            segments: List of transcript segments with text, start, duration
            output_subtitle_path: Path where subtitle file should be saved
            language: Language code for the subtitles
            
        Returns:
            Path to generated subtitle file or None if error
        """
        try:
            from ..utils.subtitle_utils import create_subtitle_files
            import os
            
            if not segments:
                logger.error("No segments provided for subtitle generation")
                return None
            
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(output_subtitle_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Determine file format from extension
            file_ext = os.path.splitext(output_subtitle_path)[1].lower()
            
            if file_ext == '.srt':
                from ..utils.subtitle_utils import generate_srt_content
                content = generate_srt_content(segments)
            elif file_ext == '.vtt':
                from ..utils.subtitle_utils import generate_vtt_content
                content = generate_vtt_content(segments)
            else:
                # Default to SRT
                from ..utils.subtitle_utils import generate_srt_content
                content = generate_srt_content(segments)
                if not output_subtitle_path.endswith('.srt'):
                    output_subtitle_path += '.srt'
            
            # Write the file
            with open(output_subtitle_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Successfully generated subtitle file: {output_subtitle_path}")
            return output_subtitle_path
            
        except Exception as e:
            logger.error(f"Error generating subtitle file from segments: {str(e)}")
            return None
    
    # Removed enhanced subtitle file generation helper to reduce maintenance surface