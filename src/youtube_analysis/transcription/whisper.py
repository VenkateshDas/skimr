import asyncio
import json
import logging
import tempfile
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

import yt_dlp
import openai

from .base import BaseTranscriber, TranscriptUnavailable
from .models import Transcript, TranscriptSegment

logger = logging.getLogger("youtube_analysis.transcription")

class WhisperTranscriber(BaseTranscriber):
    """Download audio & transcribe via OpenAI Whisper API."""

    # Use a simpler format string as we'll convert with FFmpeg anyway
    _AUDIO_FMT = "bestaudio"
    _AUDIO_FMT_FALLBACK = "best"
    
    # Supported models
    _SUPPORTED_MODELS = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
    
    def __init__(self, default_model: str = "gpt-4o-transcribe"):
        """Initialize the transcriber with configurable default model.
        
        Args:
            default_model: Model name to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
        """
        if default_model not in self._SUPPORTED_MODELS:
            logger.warning(f"Unsupported model: {default_model}. Using gpt-4o-transcribe instead.")
            default_model = "gpt-4o-transcribe"
            
        self.default_model = default_model
        super().__init__()

    async def get(self, *, video_id: str, language: str, model_name: str = None) -> Transcript:
        """Get transcript using OpenAI's whisper models.
        
        Args:
            video_id: YouTube video ID
            language: ISO-639-1 language code
            model_name: OpenAI model to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
                        If None, uses the default model specified in constructor
        
        Returns:
            Transcript object
        """
        logger.debug("Whisper fallback for %s", video_id)
        
        # Use provided model_name or fall back to default
        model = model_name if model_name in self._SUPPORTED_MODELS else self.default_model
        logger.info(f"Using OpenAI model: {model} for transcription")
        
        async with self._download_audio(video_id) as audio_path:
            # Convert to MP3 to ensure compatibility with OpenAI
            mp3_path = await self._convert_to_mp3(audio_path)
            transcript = await self._call_whisper(mp3_path or audio_path, language, model)
        return Transcript(video_id=video_id, language=language, source="whisper", segments=transcript)

    @asynccontextmanager
    async def _download_audio(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmpdir:
            ytdlp_opts = {
                "format": self._AUDIO_FMT,
                "quiet": True,
                "outtmpl": f"{tmpdir}/%(id)s.%(ext)s",
                "noplaylist": True,
                "nocheckcertificate": True,
                "ignoreerrors": False,
            }
            
            loop = asyncio.get_running_loop()
            try:
                logger.debug("Attempting to download audio with format: %s", self._AUDIO_FMT)
                await loop.run_in_executor(None, yt_dlp.YoutubeDL(ytdlp_opts).download, [url])
            except Exception as e:
                logger.warning("Failed to download with primary format: %s. Trying fallback format: %s", 
                               self._AUDIO_FMT, self._AUDIO_FMT_FALLBACK)
                ytdlp_opts["format"] = self._AUDIO_FMT_FALLBACK
                try:
                    await loop.run_in_executor(None, yt_dlp.YoutubeDL(ytdlp_opts).download, [url])
                except Exception as fallback_e:
                    raise TranscriptUnavailable(f"Failed to download audio: {str(fallback_e)}") from fallback_e
            
            # locate downloaded file
            audio_files = list(Path(tmpdir).glob(f"{video_id}.*"))
            if not audio_files:
                raise TranscriptUnavailable("yt-dlp failed to download audio")
            yield audio_files[0]

    async def _convert_to_mp3(self, input_path: Path) -> Optional[Path]:
        """Convert the input file to MP3 format using FFmpeg."""
        # Create output path with .mp3 extension in the same directory
        output_path = input_path.with_suffix('.mp3')
        
        if output_path.exists():
            # If the file already exists (somehow), don't recreate it
            return output_path
            
        # If input is already an MP3, no need to convert
        if input_path.suffix.lower() == '.mp3':
            return None
            
        # Run FFmpeg to convert to MP3
        cmd = [
            'ffmpeg', 
            '-i', str(input_path),  # Input file
            '-vn',                  # Disable video
            '-acodec', 'libmp3lame', # Use MP3 codec
            '-q:a', '2',            # Quality setting
            '-y',                   # Overwrite output
            str(output_path)        # Output file
        ]
        
        logger.debug("Converting %s to MP3 using FFmpeg", input_path)
        try:
            # Run FFmpeg synchronously (it's typically fast for audio)
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug("Successfully converted to %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            # Log error but continue with original file
            logger.warning("FFmpeg conversion failed: %s", 
                          e.stderr.decode() if e.stderr else str(e))
            return None
        except Exception as e:
            logger.warning("Unexpected error during conversion: %s", str(e))
            return None

    async def _call_whisper(self, audio_path: Path, language: str, model: str) -> List[TranscriptSegment]:
        """Call OpenAI's Whisper API with the audio file."""
        logger.debug("Processing %s with Whisper API, language=%s, model=%s", audio_path, language, model)
        
        # Determine appropriate response format based on model
        is_whisper_model = model == "whisper-1"
        response_format = "verbose_json" if is_whisper_model else "text"
        
        try:
            # In newer OpenAI Python SDK, we need to provide a binary file object
            with open(audio_path, "rb") as audio_file:
                # Always use transcriptions API for all languages to preserve original language
                logger.debug(f"Using transcription API with model {model} for language {language}")
                try:
                    resp = openai.audio.transcriptions.create(
                        file=audio_file,
                        model=model,
                        language=language,
                        response_format=response_format
                    )
                    
                    # For GPT-4o models, we get a direct string response
                    if not is_whisper_model:
                        # Check if response is a string directly or has a text attribute
                        if isinstance(resp, str):
                            text = resp.strip()
                        else:
                            text = resp.text.strip() if hasattr(resp, 'text') else str(resp).strip()
                        return [TranscriptSegment(start=0.0, text=text)]
                    
                    # For whisper-1 with verbose_json, parse the segments
                    if hasattr(resp, 'segments'):
                        raw_segments = resp.segments
                    else:
                        # Parse JSON response
                        raw = json.loads(resp.json()) if hasattr(resp, 'json') else resp
                        raw_segments = raw.get("segments", [])
                
                except Exception as e:
                    logger.error(f"Transcription with {model} failed: {str(e)}")
                    raise TranscriptUnavailable(f"Transcription failed: {str(e)}")
                
                # For whisper-1 model with segments, convert to our format
                segments = [
                    TranscriptSegment(
                        start=seg.get("start", 0) if isinstance(seg, dict) else getattr(seg, "start", 0), 
                        text=seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
                    ) 
                    for seg in raw_segments
                ]
                return segments
            
        except Exception as e:
            logger.error("Whisper API error: %s", str(e))
            raise TranscriptUnavailable(f"Whisper API failed: {str(e)}") from e 