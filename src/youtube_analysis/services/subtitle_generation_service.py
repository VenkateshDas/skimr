"""
Advanced subtitle generation service with media file support and intelligent chunking.
"""

import os
import tempfile
import math
import shutil
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from openai import OpenAI
import pysubs2
from pydub import AudioSegment
import ffmpeg

from ..utils.logging import get_logger

logger = get_logger("subtitle_generation_service")

# Constants
OPENAI_API_SIZE_LIMIT_BYTES = 24 * 1024 * 1024  # Slightly less than 25MB for safety


class SubtitleGenerationService:
    """
    Service for generating subtitles from media files using OpenAI Whisper API.
    Handles file size limits by intelligently chunking audio files.
    """
    
    def __init__(self, openai_api_key: str = None):
        """
        Initialize the subtitle generation service.
        
        Args:
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(api_key=api_key)
        logger.info("Initialized SubtitleGenerationService")
    
    def generate_subtitles_from_media(
        self,
        media_file_path: str,
        output_subtitle_path: str,
        language: str = None,
        prompt: str = None,
        temperature: float = 0.0,
        whisper_model: str = "whisper-1"
    ) -> str:
        """
        Generate subtitles from a media file.
        
        Args:
            media_file_path: Path to the input media file (audio or video)
            output_subtitle_path: Path where the subtitle file should be saved
            language: ISO-639-1 language code (optional, auto-detect if None)
            prompt: Optional prompt to improve transcription quality
            temperature: Sampling temperature (0.0 to 1.0)
            whisper_model: Whisper model to use
            
        Returns:
            Path to the generated subtitle file
            
        Raises:
            FileNotFoundError: If the input file doesn't exist
            ValueError: If the file format is not supported
            Exception: For API or processing errors
        """
        logger.info(f"Starting subtitle generation for: {media_file_path}")
        
        # Validate input file
        if not os.path.exists(media_file_path):
            raise FileNotFoundError(f"Media file not found: {media_file_path}")
        
        temp_audio_file = None
        temp_chunk_dir = None
        
        try:
            # Step 1: Audio preparation
            audio_file_to_process = self._prepare_audio(media_file_path)
            if audio_file_to_process != media_file_path:
                temp_audio_file = audio_file_to_process
            
            # Step 2: Load audio with pydub for analysis
            logger.debug(f"Loading audio file: {audio_file_to_process}")
            audio_segment = AudioSegment.from_file(audio_file_to_process)
            
            # Step 3: Determine if chunking is needed
            file_size = os.path.getsize(audio_file_to_process)
            audio_chunks_info = []
            
            if file_size < OPENAI_API_SIZE_LIMIT_BYTES:
                logger.info(f"File size ({file_size} bytes) under limit, no chunking needed")
                audio_chunks_info = [(audio_file_to_process, 0)]
            else:
                logger.info(f"File size ({file_size} bytes) exceeds limit, chunking required")
                audio_chunks_info, temp_chunk_dir = self._chunk_audio(audio_segment, audio_file_to_process)
            
            # Step 4: Transcribe chunks and assemble subtitles
            final_srt_string = self._transcribe_and_assemble(
                audio_chunks_info, language, prompt, temperature, whisper_model
            )
            
            # Step 5: Parse and save final subtitles
            if final_srt_string.strip():
                final_subs = pysubs2.SSAFile.from_string(final_srt_string)
                final_subs.save(output_subtitle_path)
                logger.info(f"Successfully generated subtitles: {output_subtitle_path}")
            else:
                # Create empty subtitle file if no content
                empty_subs = pysubs2.SSAFile()
                empty_subs.save(output_subtitle_path)
                logger.warning("Generated empty subtitle file")
            
            return output_subtitle_path
            
        except Exception as e:
            logger.error(f"Error generating subtitles: {str(e)}")
            raise
        finally:
            # Step 6: Cleanup
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                    logger.debug(f"Cleaned up temporary audio file: {temp_audio_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp audio file: {e}")
            
            if temp_chunk_dir and os.path.exists(temp_chunk_dir):
                try:
                    shutil.rmtree(temp_chunk_dir)
                    logger.debug(f"Cleaned up temporary chunk directory: {temp_chunk_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp chunk dir: {e}")
    
    def _prepare_audio(self, media_file_path: str) -> str:
        """
        Prepare audio for transcription by extracting from video if needed.
        
        Args:
            media_file_path: Path to the media file
            
        Returns:
            Path to the audio file ready for processing
        """
        # Determine media type
        mime_type, _ = mimetypes.guess_type(media_file_path)
        logger.debug(f"Detected MIME type: {mime_type}")
        
        # If it's already an audio file, return as-is
        if mime_type and mime_type.startswith('audio'):
            logger.debug("Input is audio file, no extraction needed")
            return media_file_path
        
        # If it's a video file, extract audio
        if mime_type and mime_type.startswith('video'):
            logger.info("Input is video file, extracting audio")
            return self._extract_audio_from_video(media_file_path)
        
        # Try to process as audio anyway (fallback)
        logger.warning(f"Unknown media type for {media_file_path}, attempting to process as audio")
        return media_file_path
    
    def _extract_audio_from_video(self, video_file_path: str) -> str:
        """
        Extract audio from video file using ffmpeg.
        
        Args:
            video_file_path: Path to the video file
            
        Returns:
            Path to the extracted audio file
        """
        # Create temporary MP3 file
        temp_dir = tempfile.gettempdir()
        temp_audio_file = os.path.join(temp_dir, f"extracted_audio_{os.getpid()}.mp3")
        
        try:
            # Use ffmpeg-python for extraction
            (
                ffmpeg
                .input(video_file_path)
                .output(temp_audio_file, format='mp3', acodec='libmp3lame', audio_bitrate='128k')
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"Successfully extracted audio to: {temp_audio_file}")
            return temp_audio_file
            
        except Exception as e:
            # Fallback using pydub
            logger.warning(f"ffmpeg extraction failed, trying pydub: {e}")
            try:
                audio = AudioSegment.from_file(video_file_path)
                audio.export(temp_audio_file, format="mp3")
                logger.info(f"Successfully extracted audio using pydub: {temp_audio_file}")
                return temp_audio_file
            except Exception as e2:
                logger.error(f"Both ffmpeg and pydub extraction failed: {e2}")
                raise ValueError(f"Failed to extract audio from video: {e2}")
    
    def _chunk_audio(self, audio_segment: AudioSegment, audio_file_path: str) -> Tuple[List[Tuple[str, int]], str]:
        """
        Chunk audio file into pieces smaller than the API limit.
        
        Args:
            audio_segment: Loaded audio segment
            audio_file_path: Path to the original audio file
            
        Returns:
            Tuple of (list of (chunk_path, offset_ms), temp_chunk_dir)
        """
        # Calculate target chunk duration
        file_size = os.path.getsize(audio_file_path)
        duration_ms = len(audio_segment)
        
        # Calculate bitrate and max chunk duration
        bitrate = audio_segment.frame_rate * audio_segment.sample_width * 8 * audio_segment.channels
        max_chunk_duration_ms = int((OPENAI_API_SIZE_LIMIT_BYTES * 0.95 * 8 * 1000) / bitrate)
        
        logger.info(f"Calculated max chunk duration: {max_chunk_duration_ms}ms ({max_chunk_duration_ms/1000:.1f}s)")
        
        # Create temporary directory for chunks
        temp_chunk_dir = tempfile.mkdtemp(prefix="subtitle_chunks_")
        audio_chunks_info = []
        
        current_pos_ms = 0
        chunk_index = 0
        
        while current_pos_ms < duration_ms:
            chunk_start_ms = current_pos_ms
            chunk_end_ms = min(current_pos_ms + max_chunk_duration_ms, duration_ms)
            
            # Extract chunk
            audio_chunk_segment = audio_segment[chunk_start_ms:chunk_end_ms]
            chunk_file_path = os.path.join(temp_chunk_dir, f"chunk_{chunk_index:03d}.mp3")
            
            # Export chunk
            audio_chunk_segment.export(chunk_file_path, format="mp3")
            
            # Verify chunk size
            chunk_size = os.path.getsize(chunk_file_path)
            if chunk_size > OPENAI_API_SIZE_LIMIT_BYTES:
                logger.warning(f"Chunk {chunk_index} still too large ({chunk_size} bytes), may fail API call")
            
            audio_chunks_info.append((chunk_file_path, chunk_start_ms))
            logger.debug(f"Created chunk {chunk_index}: {chunk_start_ms}ms-{chunk_end_ms}ms, size: {chunk_size} bytes")
            
            current_pos_ms = chunk_end_ms
            chunk_index += 1
        
        logger.info(f"Split audio into {len(audio_chunks_info)} chunks")
        return audio_chunks_info, temp_chunk_dir
    
    def _transcribe_and_assemble(
        self,
        audio_chunks_info: List[Tuple[str, int]],
        language: str,
        prompt: str,
        temperature: float,
        whisper_model: str
    ) -> str:
        """
        Transcribe audio chunks and assemble into final SRT string.
        
        Args:
            audio_chunks_info: List of (chunk_path, offset_ms) tuples
            language: Language code
            prompt: Transcription prompt
            temperature: Sampling temperature
            whisper_model: Whisper model name
            
        Returns:
            Final SRT string with all chunks combined
        """
        final_srt_string = ""
        
        for idx, (chunk_file_path, offset_ms) in enumerate(audio_chunks_info):
            logger.info(f"Transcribing chunk {idx + 1}/{len(audio_chunks_info)}: {chunk_file_path}")
            
            try:
                # Call OpenAI API
                with open(chunk_file_path, "rb") as audio_file_chunk:
                    params = {
                        "model": whisper_model,
                        "file": audio_file_chunk,
                        "response_format": "srt",  # Request SRT directly
                        "temperature": temperature
                    }
                    
                    if language:
                        params["language"] = language
                    if prompt:
                        params["prompt"] = prompt
                    
                    transcription_response = self.client.audio.transcriptions.create(**params)
                    chunk_srt_data = transcription_response  # This is already an SRT formatted string
                
                # Process and shift SRT data for the chunk
                if chunk_srt_data and chunk_srt_data.strip():
                    # Parse the chunk's SRT string
                    subs_chunk = pysubs2.SSAFile.from_string(chunk_srt_data)
                    
                    # Shift timestamps
                    if offset_ms > 0:
                        subs_chunk.shift(ms=offset_ms)
                        logger.debug(f"Shifted chunk {idx} by {offset_ms}ms")
                    
                    # Convert back to SRT string and append
                    shifted_chunk_srt_string = subs_chunk.to_string('srt')
                    final_srt_string += shifted_chunk_srt_string + "\n"
                else:
                    logger.warning(f"Empty transcription for chunk {idx}")
                    
            except Exception as e:
                logger.error(f"Error transcribing chunk {idx}: {str(e)}")
                # Continue with other chunks instead of failing completely
                continue
        
        return final_srt_string
    
    def generate_subtitles_from_youtube_audio(
        self,
        audio_file_path: str,
        output_subtitle_path: str,
        language: str = None,
        prompt: str = None,
        temperature: float = 0.0,
        whisper_model: str = "whisper-1"
    ) -> str:
        """
        Convenience method for generating subtitles from YouTube audio files.
        This is a wrapper around the main method for backwards compatibility.
        
        Args:
            audio_file_path: Path to the audio file
            output_subtitle_path: Path where the subtitle file should be saved
            language: ISO-639-1 language code
            prompt: Optional transcription prompt
            temperature: Sampling temperature
            whisper_model: Whisper model name
            
        Returns:
            Path to the generated subtitle file
        """
        return self.generate_subtitles_from_media(
            media_file_path=audio_file_path,
            output_subtitle_path=output_subtitle_path,
            language=language,
            prompt=prompt,
            temperature=temperature,
            whisper_model=whisper_model
        )