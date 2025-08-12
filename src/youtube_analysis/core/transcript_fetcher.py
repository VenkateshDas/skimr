"""
Robust YouTube transcript fetching engine based on test_yt.py with enhanced capabilities.

This module provides a comprehensive approach to fetching YouTube transcripts with:
- Robust session management with intelligent retry logic  
- YouTube API key/version extraction from HTML pages
- Spoken language detection using faster-whisper on local audio clips
- Smart caption track selection (manual vs ASR with coverage analysis)
- Translation support via timedtext tlang
- VTT output format with proper merging and rollup
- Playlist support and comprehensive error handling
"""

import asyncio
import time
import random
import os
import re
import json
import tempfile
import shutil
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from ..transcription import WhisperTranscriber, TranscriptUnavailable
from ..models import TranscriptSegment, VideoData, VideoInfo
from ..utils.logging import get_logger
from .cache_manager import CacheManager

logger = get_logger("transcript_fetcher")

# Constants from test_yt.py
YOUTUBE = "https://www.youtube.com"
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
]

def log(msg: str): 
    """Log message to logger."""
    logger.info(msg)

# Utility functions from test_yt.py
def normalize_lang(code: Optional[str]) -> Optional[str]:
    if not code: return None
    c = code.lower().strip()
    if "-" in c: c = c.split("-")[0]
    return {"zh-hans":"zh","zh-hant":"zh","pt-br":"pt","pt-pt":"pt"}.get(c, c)

def parse_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s): return s
    u = urlparse(s)
    host = (u.netloc or "").lower()
    if "youtu.be" in host:
        vid = u.path.strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid): return vid
    if "youtube.com" in host:
        qs = parse_qs(u.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid): return vid
    raise ValueError("Could not parse a valid YouTube video ID.")

def jitter_sleep(base_seconds: float): 
    time.sleep(base_seconds*(0.75+random.random()*0.5))

class TranscriptSource(Enum):
    """Available transcript sources."""
    ROBUST_YOUTUBE = "robust_youtube"
    MANUAL_CAPTIONS = "manual_captions"
    AUTO_GENERATED = "auto_generated"
    WHISPER_OPENAI = "whisper_openai"
    WHISPER_GROQ = "whisper_groq"

class TranscriptError(Exception):
    """Base class for transcript-related errors."""
    pass

class TranscriptUnavailableError(TranscriptError):
    """Transcript is not available for this video."""
    pass

class TranscriptTemporaryError(TranscriptError):
    """Temporary error that might resolve with retry."""
    pass

class TranscriptRateLimitError(TranscriptError):
    """Rate limit exceeded."""
    pass

@dataclass
class TranscriptResult:
    """Result of transcript fetching operation."""
    success: bool
    transcript: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None
    source: Optional[TranscriptSource] = None
    language: Optional[str] = None
    error: Optional[str] = None
    attempt_count: int = 0
    fetch_time_ms: int = 0
    spoken_language: Optional[str] = None
    is_auto: bool = False
    output_language: Optional[str] = None

# Session management from test_yt.py
def new_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=5, connect=3, read=3, backoff_factor=0.8,
                    status_forcelist=[429,500,502,503,504],
                    allowed_methods=["HEAD","GET","POST","OPTIONS"],
                    raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://",  HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": random.choice(UA_POOL),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.8",
        "Origin": YOUTUBE, "Referer": f"{YOUTUBE}/", "Connection":"keep-alive",
    })
    s.cookies.set("CONSENT","YES+1", domain=".youtube.com")
    s.cookies.set("PREF","hl=en", domain=".youtube.com")
    return s

@dataclass
class LanguagePreference:
    """Language preference configuration."""
    primary_languages: List[str] = field(default_factory=lambda: ['en'])
    secondary_languages: List[str] = field(default_factory=lambda: ['de', 'es', 'fr', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'hi', 'ar'])
    auto_detect_enabled: bool = True
    prefer_manual_captions: bool = True

# Bootstrap key/version from test_yt.py
def extract_innertube_from_html(html: str) -> Optional[Tuple[str,str]]:
    m_key = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
    m_ver = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
    if m_key and m_ver: return m_key.group(1), m_ver.group(1)
    for m in re.finditer(r'ytcfg\.set\(\s*(\{.*?\})\s*\)\s*;', html, flags=re.S):
        try: obj = json.loads(m.group(1))
        except Exception: continue
        api = obj.get("INNERTUBE_API_KEY")
        ver = obj.get("INNERTUBE_CONTEXT_CLIENT_VERSION") or ((obj.get("INNERTUBE_CONTEXT") or {}).get("client") or {}).get("clientVersion")
        if api and ver: return api, ver
    m_key2 = re.search(r"ytcfg\.set\(\s*['\"]INNERTUBE_API_KEY['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", html)
    m_ver2 = re.search(r"ytcfg\.set\(\s*['\"]INNERTUBE_CONTEXT_CLIENT_VERSION['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", html)
    if m_key2 and m_ver2: return m_key2.group(1), m_ver2.group(1)
    return None

def bootstrap_client_from_url(s: requests.Session, page_url: str) -> Tuple[str,str,str]:
    r = s.get(page_url, timeout=25, allow_redirects=True); r.raise_for_status()
    html = r.text
    if "consent.youtube.com" in r.url or "consent.google.com" in html.lower():
        s.cookies.set("CONSENT","YES+1", domain=".youtube.com")
        r = s.get(page_url, timeout=25, allow_redirects=True); r.raise_for_status()
        html = r.text
    pair = extract_innertube_from_html(html)
    if pair: return pair[0], pair[1], html
    r2 = s.get(f"{YOUTUBE}/?hl=en&persist_hl=1&persist_gl=1", timeout=25); r2.raise_for_status()
    pair2 = extract_innertube_from_html(r2.text)
    if pair2: return pair2[0], pair2[1], html
    raise RuntimeError("Failed to extract API key/client version.")

def bootstrap_client_for_video(s: requests.Session, video_id: str) -> Tuple[str,str,str]:
    return bootstrap_client_from_url(s, f"{YOUTUBE}/watch?v={video_id}&hl=en")

# Player & captions from test_yt.py
def fetch_player(s: requests.Session, video_id: str, api_key: str, client_version: str) -> Dict[str,Any]:
    endpoint=f"{YOUTUBE}/youtubei/v1/player"
    params={"key":api_key,"prettyPrint":"false"}
    payload={"context":{"client":{"clientName":"WEB","clientVersion":client_version}},"videoId":video_id}
    headers={"X-YouTube-Client-Name":"1","X-YouTube-Client-Version":client_version,"Content-Type":"application/json"}
    jitter_sleep(0.25)
    r=s.post(endpoint, params=params, json=payload, headers=headers, timeout=25); r.raise_for_status()
    data=r.json()
    status=(data.get("playabilityStatus") or {}).get("status","OK")
    if status!="OK":
        reason=(data.get("playabilityStatus") or {}).get("reason","unknown")
        raise RuntimeError(f"Player not OK: {status} ({reason})")
    return data

def _collect_tracks(player: Dict[str,Any]) -> List[Dict[str,Any]]:
    cap=(player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}
    tracks=cap.get("captionTracks") or []
    for t in tracks:
        t["languageCode"]=normalize_lang(t.get("languageCode"))
        t["is_asr"]=(t.get("kind")=="asr") or str(t.get("vssId","")).startswith("a.")
        t["_name"]=(t.get("name") or {}).get("simpleText","")
    return tracks

def _get_video_duration_ms(player: Dict[str,Any]) -> Optional[int]:
    vd = player.get("videoDetails") or {}
    if vd.get("lengthSeconds"):
        try: return int(vd["lengthSeconds"])*1000
        except Exception: pass
    mf = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    if mf.get("lengthSeconds"):
        try: return int(mf["lengthSeconds"])*1000
        except Exception: pass
    return None

# Language inference from test_yt.py
def infer_spoken_language(player: Dict[str,Any], tracks: List[Dict[str,Any]]) -> Optional[str]:
    # Heuristic fallbacks
    name_map={"english":"en","german":"de","french":"fr","spanish":"es","hindi":"hi","tamil":"ta",
              "arabic":"ar","russian":"ru","portuguese":"pt","italian":"it","japanese":"ja",
              "korean":"ko","turkish":"tr","polish":"pl","dutch":"nl","indonesian":"id",
              "mandarin":"zh","chinese":"zh"}
    for t in tracks:
        if t.get("is_asr"):
            name=(t.get("_name") or "").lower()
            for k,v in name_map.items():
                if k in name:
                    log(f"LID: heuristic from ASR name '{t['_name']}' → {v}")
                    return v
    asr_langs=[t.get("languageCode") for t in tracks if t.get("is_asr") and t.get("languageCode")]
    if len(asr_langs)==1:
        log(f"LID: single ASR track code → {asr_langs[0]}")
        return asr_langs[0]
    for t in tracks:
        if t.get("isDefault") and t.get("languageCode"):
            log(f"LID: default track language → {t['languageCode']}")
            return t["languageCode"]
    mf=(player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    if mf.get("language"):
        lang=normalize_lang(mf["language"]); log(f"LID: microformat language → {lang}")
        return lang
    for t in tracks:
        if t.get("languageCode"):
            log(f"LID: fallback first track language → {t['languageCode']}")
            return t["languageCode"]
    log("LID: could not infer spoken language")
    return None

def pick_track_for_language(tracks: List[Dict[str,Any]], lang: str, prefer_manual=True) -> Optional[Dict[str,Any]]:
    if prefer_manual:
        for t in tracks:
            if not t.get("is_asr") and t.get("languageCode")==lang: return t
        for t in tracks:
            if t.get("is_asr") and t.get("languageCode")==lang: return t
    else:
        for t in tracks:
            if t.get("is_asr") and t.get("languageCode")==lang: return t
        for t in tracks:
            if not t.get("is_asr") and t.get("languageCode")==lang: return t
    return None

def choose_track(player: Dict[str,Any], video_id: str, desired_lang: Optional[str]) -> Tuple[Dict[str,Any], str, List[Dict[str,Any]]]:
    tracks=_collect_tracks(player)
    if not tracks: raise RuntimeError("No captions available.")
    langs_summary=", ".join([f"{t['languageCode'] or '?'}{'-asr' if t['is_asr'] else ''}" for t in tracks])
    log(f"Tracks: [{langs_summary}]")
    spoken = infer_spoken_language(player, tracks)
    log(f"Decision: spoken={spoken} desired={desired_lang or 'auto'}")
    select_lang = normalize_lang(desired_lang) if desired_lang and desired_lang!="auto" else spoken

    if not select_lang:
        log("Selecting fallback: any manual, else any")
        for t in tracks:
            if not t.get("is_asr"): return t, spoken or (t.get("languageCode") or "unknown"), tracks
        return tracks[0], spoken or (tracks[0].get("languageCode") or "unknown"), tracks

    track = pick_track_for_language(tracks, select_lang, prefer_manual=True)
    if track:
        log(f"Selected track: lang={select_lang} {'ASR' if track.get('is_asr') else 'manual'}")
        return track, spoken or select_lang, tracks

    log("No exact match. Falling back to any manual, else any")
    for t in tracks:
        if not t.get("is_asr"):
            return t, spoken or select_lang, tracks
    return tracks[0], spoken or select_lang, tracks

# Timedtext fetch & merge from test_yt.py
def fetch_json3_events(s: requests.Session, track: Dict[str,Any], output_lang: Optional[str]) -> List[Dict[str,Any]]:
    base=track["baseUrl"]; url = base if "fmt=" in base else base + "&fmt=json3"
    if output_lang:
        tl=normalize_lang(output_lang)
        if tl:
            url = re.sub(r"tlang=[^&]+", f"tlang={tl}", url) if "tlang=" in url else (url + f"&tlang={tl}")
            log(f"Timedtext: translation requested → {tl}")
    jitter_sleep(0.2)
    r=s.get(url, timeout=25); r.raise_for_status()
    txt=r.text.lstrip(")]}'\n\r\t "); data=json.loads(txt)
    return data.get("events") or []

def clean_text(t: str) -> str:
    t=t.replace("\u200b",""); t=re.sub(r"\s+"," ", t); return t.strip()

def event_text(ev: Dict[str,Any]) -> str:
    segs=ev.get("segs") or []; return clean_text("".join(seg.get("utf8","") for seg in segs))

def ms_to_ts(ms: int) -> str:
    h=ms//3600000; ms%=3600000
    m=ms//60000;   ms%=60000
    s=ms//1000;    ms%=1000
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

def merge_rollup(events: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    cues=[]; active=None; last=""
    for ev in events:
        if "tStartMs" not in ev: continue
        start=int(ev["tStartMs"]); end=start+max(int(ev.get("dDurationMs",0)),1)
        txt=event_text(ev)
        if not txt: continue
        if active is None:
            active={"start":start,"end":end,"text":txt}; last=txt; continue
        if end>active["end"]: active["end"]=end
        if txt==last: continue
        elif txt.startswith(last):
            new=txt[len(last):].lstrip()
            if new:
                if active["text"] and not active["text"].endswith(" "): active["text"]+=" "
                active["text"]+=new
            last=txt
        elif last.startswith(txt):
            continue
        else:
            cues.append(active); active={"start":start,"end":end,"text":txt}; last=txt
    if active: cues.append(active)
    return cues

def cues_to_vtt(cues: List[Dict[str,Any]]) -> str:
    out=["WEBVTT",""]
    for c in cues:
        out.append(f"{ms_to_ts(c['start'])} --> {ms_to_ts(c['end'])}")
        out.append(c["text"]); out.append("")
    return "\n".join(out)

def coverage_ms_from_events(events: List[Dict[str,Any]]) -> int:
    max_end = 0
    for ev in events:
        if "tStartMs" in ev:
            start = int(ev["tStartMs"])
            end = start + max(int(ev.get("dDurationMs", 0)), 1)
            if end > max_end: max_end = end
    return max_end

# Main fetching function from test_yt.py
def get_clean_vtt_for_video(
    s: requests.Session, video_id: str,
    desired_lang: Optional[str], output_lang: Optional[str],
    min_coverage: float = 0.70, enable_asr_fallback: bool = True
) -> Tuple[str, Dict[str,Any]]:
    api_key, client_version, _ = bootstrap_client_for_video(s, video_id)
    player = fetch_player(s, video_id, api_key, client_version)

    # Choose initial track (manual preferred)
    track, spoken, all_tracks = choose_track(player, video_id, desired_lang)
    log(f"Chosen track: lang={track.get('languageCode')} ({'ASR' if track.get('is_asr') else 'manual'})")

    # Download events and compute coverage
    events = fetch_json3_events(s, track, output_lang)
    cues = merge_rollup(events)
    vtt = cues_to_vtt(cues)

    dur_ms = _get_video_duration_ms(player)
    cov_ms = coverage_ms_from_events(events)
    if dur_ms:
        cov_ratio = cov_ms / max(dur_ms, 1)
        log(f"Coverage: {cov_ms/1000:.1f}s of {dur_ms/1000:.1f}s ({cov_ratio:.2%}) for {track.get('languageCode')} {'ASR' if track.get('is_asr') else 'manual'}")
    else:
        cov_ratio = 1.0  # unknown duration → assume ok

    # If manual is short and ASR exists in same language, switch
    if enable_asr_fallback and (not track.get("is_asr")) and dur_ms and cov_ratio < min_coverage:
        lang = track.get("languageCode")
        asr = pick_track_for_language(all_tracks, lang, prefer_manual=False)  # prefer ASR now
        if asr and asr.get("is_asr"):
            log(f"Coverage below threshold ({cov_ratio:.2%} < {min_coverage:.2%}). Trying ASR in '{lang}'…")
            events_asr = fetch_json3_events(s, asr, output_lang)
            cov_asr = coverage_ms_from_events(events_asr)
            ratio_asr = cov_asr / max(dur_ms, 1)
            log(f"ASR coverage: {cov_asr/1000:.1f}s of {dur_ms/1000:.1f}s ({ratio_asr:.2%})")
            if ratio_asr > cov_ratio:
                log("Switching to ASR track due to better coverage.")
                cues_asr = merge_rollup(events_asr)
                vtt = cues_to_vtt(cues_asr)
                track = asr
            else:
                log("ASR coverage not better; keeping manual.")

    return vtt, {
        "spokenLanguage": spoken,
        "sourceLanguage": track.get("languageCode"),
        "is_auto": track.get("is_asr"),
        "outputLanguage": normalize_lang(output_lang) if output_lang else None
    }

def vtt_to_segments(vtt_content: str) -> List[Dict[str, Any]]:
    """Convert VTT content to segments list."""
    segments = []
    lines = vtt_content.strip().split('\n')
    i = 0
    
    # Skip WEBVTT header
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == "WEBVTT":
        i += 1
    
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        # Look for timestamp line
        if '-->' in line:
            timestamp_line = line
            text_lines = []
            i += 1
            
            # Collect text lines until empty line or end
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            
            if text_lines:
                # Parse timestamp
                try:
                    start_str, end_str = timestamp_line.split(' --> ')
                    start_ms = _parse_timestamp(start_str.strip())
                    end_ms = _parse_timestamp(end_str.strip())
                    duration_ms = end_ms - start_ms
                    
                    segments.append({
                        "text": " ".join(text_lines),
                        "start": start_ms / 1000.0,  # Convert to seconds
                        "duration": duration_ms / 1000.0
                    })
                except ValueError:
                    pass  # Skip malformed timestamps
        i += 1
    
    return segments

def _parse_timestamp(timestamp: str) -> int:
    """Parse VTT timestamp to milliseconds."""
    # Format: HH:MM:SS.mmm or MM:SS.mmm
    parts = timestamp.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")
    
    sec_parts = seconds.split('.')
    seconds = sec_parts[0]
    milliseconds = sec_parts[1] if len(sec_parts) > 1 else "0"
    
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(milliseconds.ljust(3, '0')[:3])
    return total_ms

class RobustTranscriptFetcher:
    """
    Robust transcript fetching engine based on test_yt.py logic.
    """
    
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        language_preferences: Optional[LanguagePreference] = None,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 30.0,
        enable_circuit_breaker: bool = True
    ):
        self.cache = cache_manager or CacheManager()
        self.language_prefs = language_preferences or LanguagePreference()
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        
        # Whisper transcribers for fallback
        self._whisper_openai = None
        self._whisper_groq = None
        
        logger.info("Initialized RobustTranscriptFetcher with test_yt.py logic")
    
    @property
    def whisper_openai(self) -> WhisperTranscriber:
        """Lazy initialization of OpenAI Whisper transcriber."""
        if self._whisper_openai is None:
            self._whisper_openai = WhisperTranscriber(provider="openai")
        return self._whisper_openai
    
    @property
    def whisper_groq(self) -> WhisperTranscriber:
        """Lazy initialization of Groq Whisper transcriber."""
        if self._whisper_groq is None:
            self._whisper_groq = WhisperTranscriber(provider="groq")
        return self._whisper_groq
    
    async def fetch_transcript(
        self,
        video_id: str,
        youtube_url: str,
        use_cache: bool = True,
        preferred_language: Optional[str] = None,
        output_language: Optional[str] = None,
        fallback_to_whisper: bool = False
    ) -> TranscriptResult:
        """
        Fetch transcript using robust test_yt.py approach.
        
        Args:
            video_id: YouTube video ID
            youtube_url: Full YouTube URL
            use_cache: Whether to use cached results
            preferred_language: Preferred language code (overrides config)
            output_language: Target language for translation
            fallback_to_whisper: Whether to use Whisper as fallback
            
        Returns:
            TranscriptResult with success status and data
        """
        start_time = time.time()
        
        # Check cache first
        if use_cache:
            cached_result = await self._get_cached_transcript(video_id, preferred_language, output_language)
            if cached_result:
                logger.debug(f"Using cached transcript for {video_id}")
                return cached_result
        
        # Try main robust approach
        try:
            s = new_session()
            vtt_content, metadata = get_clean_vtt_for_video(
                s, video_id, preferred_language, output_language
            )
            
            # Convert VTT to segments
            segments = vtt_to_segments(vtt_content)
            transcript_text = " ".join(seg["text"] for seg in segments)
            
            result = TranscriptResult(
                success=True,
                transcript=transcript_text,
                segments=segments,
                source=TranscriptSource.ROBUST_YOUTUBE,
                language=metadata.get("sourceLanguage"),
                spoken_language=metadata.get("spokenLanguage"),
                is_auto=metadata.get("is_auto", False),
                output_language=metadata.get("outputLanguage"),
                fetch_time_ms=int((time.time() - start_time) * 1000)
            )
            
            # Cache the result
            if use_cache:
                await self._cache_transcript_result(video_id, result, preferred_language, output_language)
            
            logger.info(f"Successfully fetched transcript for {video_id} using robust YouTube method")
            return result
            
        except Exception as e:
            logger.warning(f"Robust YouTube method failed for {video_id}: {e}")
            
            # Fallback to Whisper if enabled
            if fallback_to_whisper:
                return await self._fetch_with_whisper(video_id, preferred_language or "en", start_time)
            
            return TranscriptResult(
                success=False,
                error=f"Failed to fetch transcript: {e}",
                fetch_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _fetch_with_whisper(self, video_id: str, language: str, start_time: float) -> TranscriptResult:
        """Fallback to Whisper transcription."""
        try:
            logger.info(f"Falling back to Whisper for {video_id}")
            transcript_obj = await self.whisper_openai.get(
                video_id=video_id, 
                language=language
            )
            
            if transcript_obj and transcript_obj.segments:
                segments = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration or 0
                    }
                    for seg in transcript_obj.segments
                ]
                
                return TranscriptResult(
                    success=True,
                    transcript=transcript_obj.text,
                    segments=segments,
                    source=TranscriptSource.WHISPER_OPENAI,
                    language=language,
                    fetch_time_ms=int((time.time() - start_time) * 1000)
                )
            else:
                raise TranscriptUnavailableError("Whisper returned empty transcript")
                
        except Exception as e:
            return TranscriptResult(
                success=False,
                error=f"Whisper fallback failed: {e}",
                fetch_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _get_cached_transcript(self, video_id: str, preferred_language: Optional[str], output_language: Optional[str]) -> Optional[TranscriptResult]:
        """Get cached transcript result."""
        cache_key = f"robust_transcript_{video_id}_{preferred_language or 'auto'}_{output_language or 'none'}"
        cached = self.cache.get("transcripts", cache_key)
        
        if cached:
            return TranscriptResult(
                success=True,
                transcript=cached.get("transcript"),
                segments=cached.get("segments"),
                source=TranscriptSource(cached.get("source", "robust_youtube")),
                language=cached.get("language"),
                spoken_language=cached.get("spoken_language"),
                is_auto=cached.get("is_auto", False),
                output_language=cached.get("output_language")
            )
        
        return None
    
    async def _cache_transcript_result(self, video_id: str, result: TranscriptResult, preferred_language: Optional[str], output_language: Optional[str]):
        """Cache successful transcript result."""
        if result.success:
            cache_key = f"robust_transcript_{video_id}_{preferred_language or 'auto'}_{output_language or 'none'}"
            cache_data = {
                "transcript": result.transcript,
                "segments": result.segments,
                "source": result.source.value if result.source else None,
                "language": result.language,
                "spoken_language": result.spoken_language,
                "is_auto": result.is_auto,
                "output_language": result.output_language,
                "cached_at": time.time()
            }
            self.cache.set("transcripts", cache_key, cache_data)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            'implementation': 'robust_youtube',
            'total_requests': 0,
            'success_rate': 0.0,
            'avg_response_time': 0.0
        }
    
    def reset_circuit_breakers(self):
        """Reset circuit breakers (placeholder for compatibility)."""
        logger.info("Circuit breakers reset (not applicable to robust implementation)")