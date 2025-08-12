import asyncio
import json
import logging
import tempfile
import subprocess
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import requests
import random
import re
import math

import yt_dlp
from groq import Groq
from pydub import AudioSegment

from .base import BaseTranscriber, TranscriptUnavailable
from .models import Transcript, TranscriptSegment
from ..utils.subtitle_utils import chunk_words_to_cues

logger = logging.getLogger("youtube_analysis.transcription")

class WhisperTranscriber(BaseTranscriber):
    """Download audio & transcribe via OpenAI or Groq Whisper API."""

    _AUDIO_FMT = "bestaudio"
    _AUDIO_FMT_FALLBACK = "best"
    _SUPPORTED_MODELS = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
    _MAX_WHISPER_FILESIZE = 25 * 1024 * 1024  # 25MB
    _CHUNK_DURATION_SEC = 600  # 10 minutes, will adjust dynamically if needed

    def __init__(
        self, 
        provider: str = "openai", 
        default_model: str = "whisper-1",
        use_timestamps: bool = True,
        use_post_processing: bool = False,
        post_processing_model: str = "gpt-4.1-mini",
        prompt: str = None
    ):
        """
        Args:
            provider: 'openai' or 'groq'
            default_model: Model name to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
            use_timestamps: Whether to use word-level timestamps
            use_post_processing: Whether to use GPT for post-processing correction
            post_processing_model: Model to use for post-processing
            prompt: Optional prompt to improve transcription quality
        """
        self.provider = provider or "openai"
        self.default_model = default_model or "whisper-1"
        self.use_timestamps = use_timestamps
        self.use_post_processing = use_post_processing
        self.post_processing_model = post_processing_model
        self.prompt = prompt
        super().__init__()

    async def get(
        self, 
        *, 
        video_id: str, 
        language: str, 
        model_name: str = None,
        prompt: str = None
    ) -> Transcript:
        """
        Get transcript using OpenAI or Groq Whisper API.
        Args:
            video_id: YouTube video ID
            language: ISO-639-1 language code
            model_name: Model to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
            prompt: Optional prompt to improve transcription quality
        Returns:
            Transcript object
        """
        logger.debug(f"Whisper fallback for {video_id} (provider={self.provider})")
        model = model_name or self.default_model
        active_prompt = prompt or self.prompt
        async with self._download_audio(video_id) as audio_path:
            mp3_path = await self._convert_to_mp3(audio_path)
            audio_file = mp3_path or audio_path
            file_size = os.path.getsize(audio_file)
            if file_size > self._MAX_WHISPER_FILESIZE:
                logger.warning(f"Audio file {audio_file} is {file_size} bytes (>25MB). Splitting into chunks.")
                chunk_paths = await self._split_audio_intelligently(audio_file)
                all_segments = []
                previous_transcript_text = ""
                for idx, chunk_path in enumerate(chunk_paths):
                    logger.info(f"Transcribing chunk {idx+1}/{len(chunk_paths)}: {chunk_path}")
                    chunk_prompt = active_prompt
                    if previous_transcript_text and idx > 0:
                        if chunk_prompt:
                            chunk_prompt = f"{chunk_prompt} {previous_transcript_text[-1000:]}"
                        else:
                            chunk_prompt = previous_transcript_text[-1000:]
                    if self.provider == "groq":
                        segments = await self._call_groq_whisper(chunk_path, language, model, chunk_prompt)
                    else:
                        segments = await self._call_openai_whisper(chunk_path, language, model, chunk_prompt)
                    previous_transcript_text = " ".join([seg["text"] for seg in segments])
                    if idx > 0:
                        time_offset = sum(os.path.getsize(chunk_paths[i]) / file_size * 
                                         (await self._get_audio_duration(audio_file)) 
                                         for i in range(idx))
                        for seg in segments:
                            seg["start"] += time_offset
                    all_segments.extend(segments)
                cues = all_segments
            else:
                if self.provider == "groq":
                    cues = await self._call_groq_whisper(audio_file, language, model, active_prompt)
                else:
                    cues = await self._call_openai_whisper(audio_file, language, model, active_prompt)
            # Convert cues (dicts) to TranscriptSegment objects for compatibility
            transcript_segments = [TranscriptSegment(
                text=cue["text"],
                start=cue["start"],
                duration=cue.get("duration", 0)
            ) for cue in cues]
            # Apply post-processing if enabled
            if self.use_post_processing:
                transcript_segments = await self._post_process_transcript(transcript_segments, language)
        return Transcript(video_id=video_id, language=language, source=self.provider, segments=transcript_segments)

    async def _transcribe_audio_to_srt(
        self,
        *,
        audio_file_path: str,
        output_subtitle_path: str,
        language: str,
        model_name: str,
        prompt: Optional[str]
    ) -> Optional[str]:
        """Transcribe the given audio file and write SRT to output_subtitle_path."""
        try:
            # Reuse the get() path to obtain segments quickly
            tmp_video_id = "local_audio"
            # Create faux transcript by calling provider on direct file
            # We call the lower-level helpers directly for efficiency
            if self.provider == "groq":
                segments = await self._call_groq_whisper(Path(audio_file_path), language, model_name, prompt)
            else:
                segments = await self._call_openai_whisper(Path(audio_file_path), language, model_name, prompt)

            # Build cues and write SRT
            cues = segments
            from ..utils.subtitle_utils import generate_srt_content
            srt_text = generate_srt_content(cues)
            out_path = Path(output_subtitle_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(srt_text)
            return str(out_path)
        except Exception as e:
            logger.error(f"Failed to transcribe audio to SRT: {e}")
            return None

    async def _post_process_transcript(
        self, 
        segments: List[TranscriptSegment], 
        language: str
    ) -> List[TranscriptSegment]:
        """
        Post-process transcript using GPT to improve accuracy of specialized terms,
        acronyms, punctuation, etc.
        """
        if not segments:
            return segments
        
        import openai
        
        # Extract full text from all segments
        full_text = " ".join([seg.text for seg in segments])
        
        system_prompt = """
        You are an expert transcription editor. Your task is to correct any spelling discrepancies, 
        ensure proper punctuation, and fix any misrecognized words in the transcript.
        Do not add any new information or change the meaning of the text.
        Preserve all timestamps and segment breaks exactly as they appear in the original.
        Only make corrections to spelling, grammar, punctuation, and word recognition errors.
        """
        
        try:
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=self.post_processing_model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_text}
                ]
            )
            
            corrected_text = response.choices[0].message.content
            
            # Use the corrected text but preserve the original timestamps
            # Split the corrected text proportionally to match original segments
            word_count_original = len(full_text.split())
            words_corrected = corrected_text.split()
            word_count_corrected = len(words_corrected)
            
            corrected_segments = []
            word_idx = 0
            
            for segment in segments:
                # Calculate how many words should be in this segment
                segment_word_count = len(segment.text.split())
                proportion = segment_word_count / word_count_original
                corrected_segment_word_count = max(1, round(proportion * word_count_corrected))
                
                # Get the words for this segment
                segment_words = words_corrected[word_idx:word_idx + corrected_segment_word_count]
                word_idx += corrected_segment_word_count
                
                if segment_words:
                    corrected_segments.append(TranscriptSegment(
                        start=segment.start,
                        duration=segment.duration,
                        text=" ".join(segment_words)
                    ))
            
            return corrected_segments
        except Exception as e:
            logger.warning(f"Post-processing failed: {str(e)}. Using original transcript.")
            return segments

    @asynccontextmanager
    async def _download_audio(self, video_id: str):
        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Base options
            base_opts = {
                "format": f"{self._AUDIO_FMT}/{self._AUDIO_FMT_FALLBACK}",
                "quiet": True,
                "noprogress": True,
                "outtmpl": f"{tmpdir}/%(id)s.%(ext)s",
                "noplaylist": True,
                "ignoreerrors": False,
                "retries": 3,
                "socket_timeout": 15,
                "sleep_requests": 0.5,
                "max_sleep_requests": 2,
                "geo_bypass": True,
            }

            # No custom SSL tweaks

            # Try multiple player clients and user agents to bypass SABR/app restrictions
            attempts = [
                # Prefer web clients first to avoid GVS PO token requirements
                {
                    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "player_client": ["web"],
                },
                {
                    "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                    "player_client": ["web_safari"],
                },
                {
                    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "player_client": ["web_embedded"],
                },
                {
                    "ua": "Mozilla/5.0 (CrKey armv7l 1.36.159268) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.67 Safari/537.36",
                    "player_client": ["tv_embedded"],
                },
                {
                    "ua": "Mozilla/5.0 (Chromium OS 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.114 Safari/537.36",
                    "player_client": ["tv"],
                },
                {
                    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                    "player_client": ["ios"],
                },
                # Keep android attempts last; often require PO token
                {
                    "ua": "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                    "player_client": ["android_embedded"],
                },
            ]

            loop = asyncio.get_running_loop()
            last_error: Optional[Exception] = None
            for attempt in attempts:
                ytdlp_opts = dict(base_opts)
                # Ensure hostile extractor_args are removed
                extractor_args = ytdlp_opts.get("extractor_args") or {}
                yt_args = extractor_args.get("youtube") or {}
                yt_args.pop("player_skip", None)  # allow js signature
                yt_args.pop("skip", None)          # don't skip dash/hls
                yt_args["player_client"] = attempt["player_client"]
                extractor_args["youtube"] = yt_args
                ytdlp_opts["extractor_args"] = extractor_args
                # Set UA
                headers = ytdlp_opts.get("http_headers") or {}
                headers["User-Agent"] = attempt["ua"]
                headers.setdefault("Referer", "https://www.youtube.com/")
                headers.setdefault("Accept-Language", os.environ.get("YTDLP_ACCEPT_LANGUAGE", "en-US,en;q=0.9"))
                ytdlp_opts["http_headers"] = headers

                try:
                    logger.debug("Attempting yt-dlp audio download with player_client=%s", attempt["player_client"]) 
                    # Hard timeout per attempt to avoid getting stuck
                    await asyncio.wait_for(
                        loop.run_in_executor(None, yt_dlp.YoutubeDL(ytdlp_opts).download, [url]),
                        timeout=25,
                    )
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    continue

            if last_error:
                # As a last resort, always try Piped (independent of SSL verify)
                try:
                    await loop.run_in_executor(None, self._download_audio_via_piped, video_id, tmpdir)
                except Exception as piped_e:
                    raise TranscriptUnavailable(
                        f"Failed to download audio with yt-dlp and Piped. yt-dlp error: {last_error}; Piped error: {piped_e}"
                    ) from piped_e
            
            # locate downloaded file
            audio_files = list(Path(tmpdir).glob(f"{video_id}.*"))
            if not audio_files:
                raise TranscriptUnavailable("yt-dlp failed to download audio")
            yield audio_files[0]

    def _download_audio_via_piped(self, video_id: str, tmpdir: str) -> None:
        # Try multiple public Piped instances
        candidates = [
            os.environ.get("PIPED_BASE_URL"),
            "https://piped.video",
            "https://piped.projectsegfau.lt",
            "https://piped.in.projectsegfau.lt",
            "https://watch.leptons.xyz",
            "https://piped.privacydev.net",
            "https://piped.mha.fi",
        ]
        candidates = [c for c in candidates if c]

        last_exc = None
        session = requests.Session()
        get_ssl_config().configure_requests_session(session)
        # Apply proxies to Piped fallback as well
        try:
            http_proxy = os.getenv("YOUTUBE_PROXY_HTTP")
            https_proxy = os.getenv("YOUTUBE_PROXY_HTTPS")
            proxies = {}
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy
            if proxies:
                session.proxies.update(proxies)
        except Exception:
            pass
        for base in candidates:
            try:
                streams_url = f"{base}/api/v1/streams/{video_id}"
                resp = session.get(streams_url, timeout=20)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception as e:
                    # Not JSON, try next instance
                    last_exc = RuntimeError(
                        f"Piped returned non-JSON (status {resp.status_code}) from {streams_url}: {(resp.text or '').strip()[:200]}"
                    )
                    continue
                audio_streams = data.get("audioStreams") or []
                if not audio_streams:
                    last_exc = RuntimeError("No audio streams listed by Piped")
                    continue
                preferred = None
                for s in audio_streams:
                    mime = (s.get("mimeType") or "").lower()
                    if "mp4" in mime or "m4a" in mime:
                        preferred = s
                        break
                if preferred is None:
                    preferred = audio_streams[0]
                stream_url = preferred.get("url")
                if not stream_url:
                    last_exc = RuntimeError("Audio stream missing URL")
                    continue
                ext = "m4a" if "mp4" in (preferred.get("mimeType") or "").lower() else "webm"
                out_path = Path(tmpdir) / f"{video_id}.{ext}"
                with session.get(stream_url, stream=True, timeout=90) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise RuntimeError("All Piped instances failed without an explicit error")

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

    async def _call_openai_whisper(
        self, 
        audio_path: Path, 
        language: str, 
        model: str,
        prompt: str = None
    ) -> List[Dict[str, Any]]:
        """Call OpenAI Whisper API with the audio file and return fine-grained cues."""
        import openai
        logger.debug("[OPENAI] Entering _call_openai_whisper: using OpenAI Whisper API for transcription.")
        api_key = os.environ.get("OPENAI_API_KEY")
        response_format = "verbose_json"
        try:
            client = openai.OpenAI(api_key=api_key)
            with open(audio_path, "rb") as audio_file:
                # Prepare API call parameters
                params = {
                    "file": audio_file,
                    "model": model,
                    "response_format": response_format,
                    "language": language,
                    "temperature": 0.0
                }
                # Add timestamp_granularities for word-level timestamps when model supports it
                if self.use_timestamps and model == "whisper-1":
                    params["timestamp_granularities"] = ["word", "segment"]
                # Add prompt if provided
                if prompt:
                    params["prompt"] = prompt
                resp = client.audio.transcriptions.create(**params)
                # OpenAI returns segments as a list of objects, not dicts
                raw_segments = getattr(resp, "segments", None) or []
                if not raw_segments:
                    text = (getattr(resp, "text", None) or "").strip()
                    if not text:
                        raise TranscriptUnavailable("OpenAI returned no transcript text.")
                    return [{"start": 0.0, "duration": 0.0, "text": text}]
                # If word-level timestamps are present, chunk into cues
                has_words = any(hasattr(seg, "words") or (isinstance(seg, dict) and "words" in seg) for seg in raw_segments)
                if has_words:
                    # Convert all segments to dicts for chunk_words_to_cues
                    seg_dicts = []
                    for seg in raw_segments:
                        if isinstance(seg, dict):
                            seg_dicts.append(seg)
                        else:
                            d = {k: getattr(seg, k, None) for k in ["start", "end", "text", "words"]}
                            seg_dicts.append(d)
                    cues = chunk_words_to_cues(seg_dicts)
                    return cues
                # Fallback: segment-level cues
                segments = []
                for seg in raw_segments:
                    if isinstance(seg, dict):
                        start = seg.get("start", 0)
                        end = seg.get("end", start)
                        text = seg.get("text", "").strip()
                    else:
                        start = getattr(seg, "start", 0)
                        end = getattr(seg, "end", start)
                        text = getattr(seg, "text", "").strip()
                    duration = end - start
                    segments.append({
                        "start": start,
                        "duration": duration,
                        "text": text
                    })
                return segments
        except Exception as e:
            logger.error("OpenAI Whisper API error: %s", str(e))
            raise TranscriptUnavailable(f"OpenAI Whisper API failed: {str(e)}") from e

    async def _call_groq_whisper(
        self, 
        audio_path: Path, 
        language: str, 
        model: str,
        prompt: str = None
    ) -> List[TranscriptSegment]:
        """Call Groq's Whisper API with the audio file."""
        logger.debug("[GROQ] Entering _call_groq_whisper: using Groq Whisper API for transcription.")
        response_format = "verbose_json"
        MAX_SEGMENT_DURATION = 8.0  # seconds
        try:
            api_key = os.environ.get("GROQ_API_KEY")
            client = Groq(api_key=api_key)
            with open(audio_path, "rb") as audio_file:
                # Prepare API call parameters
                params = {
                    "file": audio_file,
                    "model": model,
                    "response_format": response_format,
                    "timestamp_granularities": ["segment"],
                    "language": language,
                    "temperature": 0.0
                }
                
                # Add prompt if provided
                if prompt:
                    params["prompt"] = prompt
                
                resp = client.audio.transcriptions.create(**params)
                
                raw_segments = getattr(resp, "segments", None) or []
                if not raw_segments:
                    text = (getattr(resp, "text", None) or "").strip()
                    if not text:
                        raise TranscriptUnavailable("Groq returned no transcript text.")
                    return [TranscriptSegment(start=0.0, duration=0.0, text=text)]
                segments = []
                for seg in raw_segments:
                    start = seg.get("start", 0)
                    end = seg.get("end", start)
                    text = seg.get("text", "").strip()
                    duration = end - start
                    if duration > MAX_SEGMENT_DURATION:
                        import re
                        sentences = re.split(r'(?<=[.!?]) +', text)
                        n = len(sentences)
                        if n == 0:
                            n = 1
                            sentences = [text]
                        sub_duration = duration / n
                        for i, sent in enumerate(sentences):
                            sent = sent.strip()
                            if not sent:
                                continue
                            sub_start = start + i * sub_duration
                            segments.append(TranscriptSegment(
                                start=sub_start,
                                duration=sub_duration,
                                text=sent
                            ))
                    else:
                        segments.append(TranscriptSegment(
                            start=start,
                            duration=duration,
                            text=text
                        ))
                return segments
        except Exception as e:
            logger.error("Groq Whisper API error: %s", str(e))
            raise TranscriptUnavailable(f"Groq Whisper API failed: {str(e)}") from e

    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get duration of audio file in seconds using ffprobe."""
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    async def _split_audio_intelligently(self, audio_path: Path) -> List[Path]:
        """
        Split audio intelligently using PyDub to avoid cutting mid-sentence.
        Returns list of chunk Paths.
        """
        import tempfile
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
        
        logger.info(f"Loading audio file for intelligent splitting: {audio_path}")
        
        # Load audio file
        audio = AudioSegment.from_file(str(audio_path))
        duration_ms = len(audio)
        file_size = os.path.getsize(audio_path)
        
        # Calculate how many chunks we need
        max_bytes = self._MAX_WHISPER_FILESIZE
        num_chunks = math.ceil(file_size / max_bytes)
        
        # Target duration for each chunk in milliseconds
        target_chunk_duration_ms = duration_ms / num_chunks
        
        # Find silent points to split at
        # These parameters can be adjusted to improve silence detection
        min_silence_len = 500  # minimum silence length in ms
        silence_thresh = -40   # silence threshold in dBFS
        
        logger.info(f"Detecting silence in audio to find natural break points")
        # Get non-silent sections
        nonsilent_sections = detect_nonsilent(
            audio, 
            min_silence_len=min_silence_len, 
            silence_thresh=silence_thresh
        )
        
        # If no silent sections found, fall back to equal chunks
        if not nonsilent_sections:
            logger.warning("No silence detected for intelligent splitting, falling back to equal chunks")
            return await self._split_audio_equally(audio_path, audio, num_chunks)
            
        # Determine split points at silence
        current_duration = 0
        split_points = []
        
        for i in range(len(nonsilent_sections) - 1):
            # End of current non-silent section
            current_section_end = nonsilent_sections[i][1]
            # Start of next non-silent section
            next_section_start = nonsilent_sections[i + 1][0]
            
            # Find middle of silence between sections
            silence_midpoint = (current_section_end + next_section_start) // 2
            
            if current_duration == 0:  # First chunk
                current_duration = silence_midpoint
                split_points.append(silence_midpoint)
            elif silence_midpoint - split_points[-1] >= target_chunk_duration_ms * 0.75:
                # Only add split point if chunk is at least 75% of target duration
                current_duration = silence_midpoint - split_points[-1]
                split_points.append(silence_midpoint)
        
        # If we don't have enough split points, add more based on target duration
        if len(split_points) < num_chunks - 1:
            # Add more split points at regular intervals for remaining duration
            remaining_duration = duration_ms - split_points[-1] if split_points else duration_ms
            remaining_chunks = num_chunks - len(split_points) - 1
            
            if remaining_chunks > 0:
                chunk_size = remaining_duration / (remaining_chunks + 1)
                for i in range(1, remaining_chunks + 1):
                    split_points.append(split_points[-1] + chunk_size if split_points else chunk_size * i)
        
        # Ensure the last split point is not too close to the end
        if split_points and duration_ms - split_points[-1] < target_chunk_duration_ms * 0.5:
            split_points.pop()  # Remove last split point if it creates a very small final chunk
            
        # Create chunks
        tmpdir = tempfile.mkdtemp(prefix="whisper_chunks_")
        chunk_paths = []
        
        # Export first chunk (from start to first split point)
        if split_points:
            first_chunk = audio[:split_points[0]]
            first_chunk_path = os.path.join(tmpdir, f"chunk_000.mp3")
            first_chunk.export(first_chunk_path, format="mp3")
            chunk_paths.append(Path(first_chunk_path))
            
            # Export middle chunks
            for i in range(len(split_points) - 1):
                chunk = audio[split_points[i]:split_points[i+1]]
                chunk_path = os.path.join(tmpdir, f"chunk_{i+1:03d}.mp3")
                chunk.export(chunk_path, format="mp3")
                chunk_paths.append(Path(chunk_path))
            
            # Export last chunk (from last split point to end)
            last_chunk = audio[split_points[-1]:]
            last_chunk_path = os.path.join(tmpdir, f"chunk_{len(split_points):03d}.mp3")
            last_chunk.export(last_chunk_path, format="mp3")
            chunk_paths.append(Path(last_chunk_path))
        else:
            # No split points, just export the whole audio
            chunk_path = os.path.join(tmpdir, "chunk_000.mp3")
            audio.export(chunk_path, format="mp3")
            chunk_paths.append(Path(chunk_path))
            
        logger.info(f"Split audio into {len(chunk_paths)} chunks at natural break points")
        
        # Check if any chunk is still > max_bytes
        for i, chunk_path in enumerate(chunk_paths):
            if os.path.getsize(chunk_path) > max_bytes:
                logger.warning(f"Chunk {i} is still larger than {max_bytes} bytes. Further splitting required.")
                # This could be improved to recursively split problematic chunks
                
        return chunk_paths
    
    async def _split_audio_equally(self, audio_path: Path, audio: AudioSegment, num_chunks: int) -> List[Path]:
        """Split audio into equal chunks as a fallback method."""
        import tempfile
        
        tmpdir = tempfile.mkdtemp(prefix="whisper_chunks_")
        chunk_paths = []
        
        duration_ms = len(audio)
        chunk_duration_ms = duration_ms // num_chunks
        
        for i in range(num_chunks):
            start_ms = i * chunk_duration_ms
            end_ms = start_ms + chunk_duration_ms if i < num_chunks - 1 else duration_ms
            
            chunk = audio[start_ms:end_ms]
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            chunk.export(chunk_path, format="mp3")
            chunk_paths.append(Path(chunk_path))
            
        logger.info(f"Split audio into {len(chunk_paths)} equal chunks")
        return chunk_paths
    
    async def generate_subtitle_file(
        self,
        video_id: str,
        output_subtitle_path: str,
        language: str = "en",
        model_name: str = None,
        prompt: str = None
    ) -> Optional[str]:
        """
        Generate subtitle file directly from YouTube video using enhanced chunking.
        
        Args:
            video_id: YouTube video ID
            output_subtitle_path: Path where subtitle file should be saved
            language: ISO-639-1 language code
            model_name: Whisper model to use
            prompt: Optional prompt for transcription
            
        Returns:
            Path to generated subtitle file or None if error
        """
        logger.info(f"Generating subtitle file for video {video_id}")
        
        try:
            # Download audio first
            async with self._download_audio(video_id) as audio_path:
                mp3_path = await self._convert_to_mp3(audio_path)
                audio_file = mp3_path or audio_path
                
                # Directly transcribe and produce SRT here to avoid extra service
                srt_path = await self._transcribe_audio_to_srt(
                    audio_file_path=str(audio_file),
                    output_subtitle_path=output_subtitle_path,
                    language=language,
                    model_name=model_name or self.default_model,
                    prompt=prompt
                )
                logger.info(f"Successfully generated subtitle file: {srt_path}")
                return srt_path
                
        except Exception as e:
            logger.error(f"Error generating subtitle file for video {video_id}: {str(e)}")
            return None

    async def _split_audio_file(self, audio_path: Path, max_bytes: int) -> List[Path]:
        """
        Legacy method for splitting audio file into chunks <= max_bytes using ffmpeg.
        This is kept for backwards compatibility, but _split_audio_intelligently is preferred.
        """
        import tempfile
        import shutil
        import subprocess
        from pathlib import Path

        # Get duration of audio file using ffprobe
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        logger.info(f"Audio duration: {duration:.2f} seconds")

        # Estimate chunk duration so each chunk is <= max_bytes
        # Do a quick test: get file size and duration, estimate bitrate
        file_size = os.path.getsize(audio_path)
        bitrate = file_size / duration  # bytes per second
        est_chunk_duration = int(max_bytes / bitrate)
        chunk_duration = min(est_chunk_duration, self._CHUNK_DURATION_SEC)
        if chunk_duration < 10:
            chunk_duration = 10  # minimum 10 seconds per chunk
        logger.info(f"Splitting into chunks of {chunk_duration} seconds each")

        # Prepare output directory
        tmpdir = tempfile.mkdtemp(prefix="whisper_chunks_")
        chunk_pattern = os.path.join(tmpdir, "chunk_%03d.mp3")

        # Use ffmpeg to split
        cmd = [
            'ffmpeg', '-i', str(audio_path), '-f', 'segment', '-segment_time', str(chunk_duration),
            '-c', 'copy', chunk_pattern, '-y'
        ]
        subprocess.run(cmd, check=True)

        # Collect chunk files
        chunk_files = sorted(Path(tmpdir).glob("chunk_*.mp3"))
        # If any chunk is still > max_bytes, re-split that chunk into smaller pieces
        final_chunks = []
        for chunk in chunk_files:
            if os.path.getsize(chunk) > max_bytes:
                logger.warning(f"Chunk {chunk} is still > max_bytes, splitting further.")
                # Recursively split this chunk
                sub_chunks = await self._split_audio_file(chunk, max_bytes)
                final_chunks.extend(sub_chunks)
                # Optionally, remove the large chunk
                os.remove(chunk)
            else:
                final_chunks.append(chunk)
        return final_chunks 