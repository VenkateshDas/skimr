"""Utilities for subtitle generation and management."""

from typing import List, Dict, Any, Optional, Tuple
import logging
import base64
import os
from pathlib import Path
import tempfile

logger = logging.getLogger("youtube_analysis.utils.subtitle")

def chunk_words_to_cues(segments: List[Dict[str, Any]], max_words: int = 5, max_duration: float = 2.0) -> List[Dict[str, Any]]:
    """
    Chunk word-level timestamps into subtitle cues for low-latency display.
    Args:
        segments: List of transcript segments, each may have a 'words' field (list of dicts with 'start', 'end', 'word')
        max_words: Maximum number of words per cue
        max_duration: Maximum duration (in seconds) per cue
    Returns:
        List of cues, each with 'start', 'duration', 'text'
    """
    cues = []
    for segment in segments:
        words = segment.get("words")
        if not words:
            # Fallback: treat the whole segment as one cue
            cues.append({
                "start": segment.get("start", 0),
                "duration": segment.get("duration", 0),
                "text": segment.get("text", "")
            })
            continue
        i = 0
        while i < len(words):
            cue_words = [words[i]]
            cue_start = words[i]["start"]
            cue_end = words[i]["end"]
            j = i + 1
            while j < len(words) and len(cue_words) < max_words and (words[j]["end"] - cue_start) <= max_duration:
                cue_words.append(words[j])
                cue_end = words[j]["end"]
                j += 1
            cue_text = " ".join(w["word"] for w in cue_words)
            cues.append({
                "start": cue_start,
                "duration": cue_end - cue_start,
                "text": cue_text
            })
            i = j
    return cues

def ensure_fine_grained_cues(segments: List[Dict[str, Any]], max_words: int = 5, max_duration: float = 2.0) -> List[Dict[str, Any]]:
    """
    Ensure that the segments are fine-grained cues (word-level chunked).
    If segments have 'words' field, chunk them; otherwise, return as is.
    """
    if not segments:
        return []
    # If already fine-grained (short cues), just return
    if all((seg.get("duration", 0) <= max_duration and len(seg.get("text", "").split()) <= max_words) for seg in segments):
        return segments
    # If any segment has 'words', chunk all
    if any("words" in seg and seg["words"] for seg in segments):
        return chunk_words_to_cues(segments, max_words=max_words, max_duration=max_duration)
    return segments

def generate_srt_content(segments: List[Dict[str, Any]], max_words: int = 5, max_duration: float = 2.0) -> str:
    """
    Generate SRT format content from fine-grained cues.
    Args:
        segments: List of transcript segments or cues
        max_words: Max words per cue (for chunking if needed)
        max_duration: Max duration per cue (for chunking if needed)
    Returns:
        String in SRT format
    """
    cues = ensure_fine_grained_cues(segments, max_words=max_words, max_duration=max_duration)
    if not cues:
        return ""
    srt_content = ""
    for i, segment in enumerate(cues, 1):
        start_time = segment.get("start", 0)
        duration = segment.get("duration", 0)
        if not duration or duration <= 0:
            if i < len(cues):
                next_start = cues[i].get("start", 0)
                duration = max(0.1, next_start - start_time)
            else:
                duration = 5.0
        end_time = start_time + duration
        start_formatted = format_srt_time(start_time)
        end_formatted = format_srt_time(end_time)
        srt_content += f"{i}\n"
        srt_content += f"{start_formatted} --> {end_formatted}\n"
        srt_content += f"{segment.get('text', '')}\n\n"
    return srt_content

def generate_vtt_content(segments: List[Dict[str, Any]], max_words: int = 5, max_duration: float = 2.0) -> str:
    """
    Generate WebVTT format content from fine-grained cues.
    Args:
        segments: List of transcript segments or cues
        max_words: Max words per cue (for chunking if needed)
        max_duration: Max duration per cue (for chunking if needed)
    Returns:
        String in WebVTT format
    """
    cues = ensure_fine_grained_cues(segments, max_words=max_words, max_duration=max_duration)
    if not cues:
        return ""
    vtt_content = "WEBVTT\n\n"
    for i, segment in enumerate(cues, 1):
        start_time = segment.get("start", 0)
        duration = segment.get("duration", 0)
        if not duration or duration <= 0:
            if i < len(cues):
                next_start = cues[i].get("start", 0)
                duration = max(0.1, next_start - start_time)
            else:
                duration = 5.0
        end_time = start_time + duration
        start_formatted = format_vtt_time(start_time)
        end_formatted = format_vtt_time(end_time)
        vtt_content += f"{start_formatted} --> {end_formatted}\n"
        vtt_content += f"{segment.get('text', '')}\n\n"
    return vtt_content

def format_srt_time(seconds: float) -> str:
    """
    Format seconds to SRT time format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

def format_vtt_time(seconds: float) -> str:
    """
    Format seconds to WebVTT time format (HH:MM:SS.mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{milliseconds:03d}"

def get_subtitle_html_track(segments: List[Dict[str, Any]], lang_code: str, label: str) -> str:
    """
    Generate HTML for a subtitle track that can be embedded in a video player.
    
    Args:
        segments: List of transcript segments
        lang_code: Language code for the track
        label: Display label for the track
        
    Returns:
        HTML string for the track
    """
    if not segments:
        return ""
    
    # Generate VTT content
    vtt_content = generate_vtt_content(segments)
    
    # Convert to base64 for embedding
    vtt_base64 = base64.b64encode(vtt_content.encode('utf-8')).decode('utf-8')
    
    # Create data URL
    vtt_data_url = f"data:text/vtt;base64,{vtt_base64}"
    
    # Return track HTML
    return f'<track kind="subtitles" src="{vtt_data_url}" srclang="{lang_code}" label="{label}" default>'

def create_subtitle_files(
    segments: List[Dict[str, Any]], 
    video_id: str, 
    language: str, 
    output_dir: str = None
) -> Dict[str, str]:
    """
    Create SRT and VTT subtitle files from segments.
    
    Args:
        segments: List of transcript segments
        video_id: YouTube video ID
        language: Language code for the subtitles
        output_dir: Directory to save files (defaults to 'downloads/subtitles')
        
    Returns:
        Dictionary with paths to created files
    """
    if not segments:
        return {}
        
    # Create output directory if not provided
    if not output_dir:
        output_dir = os.path.join("downloads", "subtitles")
        
    os.makedirs(output_dir, exist_ok=True)
    
    # File paths
    srt_path = os.path.join(output_dir, f"{video_id}_{language}.srt")
    vtt_path = os.path.join(output_dir, f"{video_id}_{language}.vtt")
    
    # Generate content
    srt_content = generate_srt_content(segments)
    vtt_content = generate_vtt_content(segments)
    
    # Write files
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
        
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
        
    return {
        "srt": srt_path,
        "vtt": vtt_path
    }

def get_plyr_compatible_vtt_url(segments: List[Dict[str, Any]], language: str = "en") -> str:
    """
    Create a VTT file and return a URL that can be used with Plyr video player.
    
    Args:
        segments: List of transcript segments
        language: Language code for the subtitles
        
    Returns:
        URL to the VTT file (using data: protocol)
    """
    if not segments:
        return ""
        
    vtt_content = generate_vtt_content(segments)
    vtt_base64 = base64.b64encode(vtt_content.encode('utf-8')).decode('utf-8')
    return f"data:text/vtt;base64,{vtt_base64}"

def get_custom_video_player_html(
    video_id: str,
    subtitles_data: Dict[str, Dict],
    width: int = 700, 
    height: int = 394
) -> str:
    """
    Generate HTML for a custom video player with subtitles overlay for YouTube.
    Args:
        video_id: YouTube video ID
        subtitles_data: Dictionary mapping language codes to subtitle segments
        width: Video width in pixels
        height: Video height in pixels
    Returns:
        HTML string for custom player with subtitles overlay
    """
    # Use the first available language as default
    default_lang = None
    for lang_code, info in subtitles_data.items():
        if info.get("default"):
            default_lang = lang_code
            break
    if not default_lang and subtitles_data:
        default_lang = next(iter(subtitles_data))

    # Prepare JS array of subtitle segments for the default language
    import json
    segments = subtitles_data.get(default_lang, {}).get("segments", [])
    js_segments = [
        {
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("start", 0)) + float(seg.get("duration", 0)),
            "text": seg.get("text", "")
        }
        for seg in segments
    ]
    segments_json = json.dumps(js_segments)

    container_id = f"player_container_{video_id}"
    player_id = f"yt_player_{video_id}"
    overlay_id = f"subtitle_overlay_{video_id}"

    html = f'''
    <div style="position: relative; max-width: {width}px; margin: 0 auto; aspect-ratio: 16/9;">
        <div id="{container_id}">
            <div id="{player_id}"></div>
            <div id="{overlay_id}" style="
                position: absolute;
                bottom: 10%;
                width: 100%;
                text-align: center;
                color: white;
                font-size: 1.5em;
                text-shadow: 2px 2px 4px #000;
                pointer-events: none;
                z-index: 10;
            "></div>
        </div>
    </div>
    <script src="https://www.youtube.com/iframe_api"></script>
    <script type="text/javascript">
        var ytPlayer_{video_id} = null;
        var subtitleSegments_{video_id} = {segments_json};
        var currentSubtitle_{video_id} = '';
        function onYouTubeIframeAPIReady() {{
            ytPlayer_{video_id} = new YT.Player('{player_id}', {{
                height: '{height}',
                width: '{width}',
                videoId: '{video_id}',
                events: {{
                    'onReady': onPlayerReady_{video_id},
                    'onStateChange': onPlayerStateChange_{video_id}
                }},
                playerVars: {{
                    'cc_load_policy': 0,
                    'modestbranding': 1,
                    'rel': 0,
                    'iv_load_policy': 3
                }}
            }});
        }}
        function onPlayerReady_{video_id}(event) {{
            setInterval(function() {{ updateSubtitle_{video_id}(); }}, 300);
        }}
        function onPlayerStateChange_{video_id}(event) {{}}
        function updateSubtitle_{video_id}() {{
            var player = ytPlayer_{video_id};
            if (!player || typeof player.getCurrentTime !== 'function') return;
            var time = player.getCurrentTime();
            var segments = subtitleSegments_{video_id};
            var overlay = document.getElementById('{overlay_id}');
            var sub = segments.find(function(s) {{ return time >= s.start && time < s.end; }});
            if (sub && sub.text !== currentSubtitle_{video_id}) {{
                overlay.textContent = sub.text;
                currentSubtitle_{video_id} = sub.text;
            }} else if (!sub) {{
                overlay.textContent = '';
                currentSubtitle_{video_id} = '';
            }}
        }}
        // If the API is already loaded, call the init function
        if (window.YT && window.YT.Player) {{
            onYouTubeIframeAPIReady();
        }}
    </script>
    '''
    return html

def detect_language(text: str) -> str:
    """
    Detect language of text.
    Enhanced implementation using langdetect library with better error handling.
    
    Args:
        text: Text to detect language for
        
    Returns:
        ISO 639-1 language code, defaults to "en"
    """
    if not text or len(text.strip()) < 10:
        return "unknown"
        
    try:
        from langdetect import detect, LangDetectException
        # Check if text has substantial Hindi/Devanagari content
        devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        if devanagari_chars > len(text) * 0.15:  # If more than 15% is Devanagari
            return "hi"  # Hindi
            
        # Sample a portion of the text for faster detection
        sample = text[:min(len(text), 1000)]
        
        # Use langdetect for other languages
        try:
            lang_code = detect(sample)
            # Log the detected language code for debugging
            logger.debug(f"Language detected: {lang_code} for text starting with: {sample[:30]}...")
            return lang_code
        except LangDetectException as e:
            logger.error(f"Language detection error: {e}")
            return "unknown"
    except ImportError:
        logger.warning("langdetect library not available")
        return "en"  # Default to English
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}")
        return "unknown" 