#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube captions with robust spoken-language selection.

Features:
- Video + playlist support (no login).
- Spoken language detection (LID) with faster-whisper on a local 50s clip
  downloaded via yt-dlp (avoids SABR/403/range issues). Falls back to URL/range, then heuristics.
- Prefers manual captions in the spoken language; if coverage is low, auto-switches to ASR.
- Optional translation via timedtext tlang.
- Loud, helpful logging (stderr) so stdout can stay pure VTT when needed.

Install:
  pip install requests faster-whisper yt-dlp
  apt-get install -y ffmpeg

Examples:
  python yt_transcript_clean.py "<video_or_playlist>" --lid faster --lid-resolver ytdlp
  python yt_transcript_clean.py "<video>" --lid faster --lid-resolver ytdlp --min-coverage 0.85
"""

import argparse, io, json, os, random, re, sys, time, tempfile, shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

YOUTUBE = "https://www.youtube.com"
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
]

def log(msg: str): print(f"LOG: {msg}", file=sys.stderr)

# -------------------- small utils

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

def get_playlist_id(url: str) -> Optional[str]:
    u = urlparse(url)
    if "youtube.com" not in (u.netloc or "").lower(): return None
    pid = (parse_qs(u.query).get("list") or [None])[0]
    if pid and re.fullmatch(r"[A-Za-z0-9_-]{10,}", pid): return pid
    return None

def is_playlist_url(url: str) -> bool:
    return ("/playlist" in url) or (get_playlist_id(url) is not None)

def sanitize_filename(s: str) -> str:
    s = re.sub(r"[\\/*?\":<>|]+", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "untitled"

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

def jitter_sleep(base_seconds: float): time.sleep(base_seconds*(0.75+random.random()*0.5))

# -------------------- bootstrap key/version

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

# -------------------- player & captions

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

# -------------------- LID: faster-whisper + yt-dlp (local clip preferred)

def detect_language_from_file_fwhisper(path: str) -> Optional[Tuple[str, float]]:
    try:
        from faster_whisper import WhisperModel
    except Exception:
        log("LID: faster-whisper not installed. `pip install faster-whisper` and ensure ffmpeg.")
        return None
    try:
        log("LID: loading faster-whisper model 'tiny' (cpu,int8)")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            path,
            task="transcribe",
            language=None,
            beam_size=1,
            best_of=1,
            vad_filter=False,
            without_timestamps=True
        )
        # trigger generator minimally
        for _ in segments: break
        lang = normalize_lang(info.language)
        prob = float(getattr(info, "language_probability", 0.0))
        log(f"LID: detected language={lang} (p={prob:.3f})")
        return (lang or None, prob)
    except Exception as e:
        log(f"LID: faster-whisper failed on file: {e}")
        return None

def download_audio_clip_with_ytdlp(video_id: str, seconds: int = 50) -> Optional[str]:
    try:
        import yt_dlp, tempfile, os
    except Exception:
        log("LID: yt-dlp not installed; cannot download audio clip.")
        return None
    tmpdir = tempfile.mkdtemp(prefix="ytlid_")
    outtmpl = os.path.join(tmpdir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": False,
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "paths": {"home": tmpdir},
        "download_ranges": (lambda info, ydl: [{"start_time": 0, "end_time": max(1, int(seconds))}]),
        "postprocessors": [{"key": "FFmpegCopyAudio"}],
        "noplaylist": True,
        "nocheckcertificate": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            log(f"LID: yt-dlp downloading first ~{seconds}s of audio…")
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            path = ydl.prepare_filename(info)
            base = os.path.splitext(path)[0]
            for ext in (".m4a", ".webm", ".opus", ".mp3"):
                cand = base + ext
                if os.path.exists(cand) and os.path.getsize(cand) > 128 * 1024:
                    log(f"LID: clip saved: {cand} ({os.path.getsize(cand)} bytes)")
                    return cand
            if os.path.exists(path) and os.path.getsize(path) > 128 * 1024:
                log(f"LID: clip saved: {path} ({os.path.getsize(path)} bytes)")
                return path
    except Exception as e:
        log(f"LID: yt-dlp clip download failed: {e}")
        try: shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception: pass
        return None
    # cleanup deferred to caller
    return None

def pick_audio_url_direct(player: Dict[str,Any]) -> Optional[str]:
    sd=player.get("streamingData") or {}
    formats=(sd.get("adaptiveFormats") or []) + (sd.get("formats") or [])
    cand=[]
    for f in formats:
        mime=f.get("mimeType","")
        if "audio" in mime and "url" in f:
            br=f.get("bitrate") or f.get("averageBitrate") or 0
            cand.append((br, f["url"]))
    if not cand: return None
    cand.sort(key=lambda x: x[0])
    return cand[0][1]

def resolve_audio_with_ytdlp(video_id: str) -> Optional[str]:
    try:
        import yt_dlp
    except Exception:
        log("LID: yt-dlp not installed; cannot resolve ciphered audio URL")
        return None
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "format": "bestaudio/best",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        if "url" in info and isinstance(info["url"], str) and info["url"].startswith("http"):
            return info["url"]
        for key in ("requested_formats","formats"):
            for f in info.get(key) or []:
                if f.get("acodec") and f.get("url"):
                    return f["url"]
    return None

def detect_language_fwhisper_from_url(s: requests.Session, audio_url: str, sample_seconds: int = 50) -> Optional[Tuple[str,float]]:
    try:
        from faster_whisper import WhisperModel
    except Exception:
        log("LID: faster-whisper not installed. `pip install faster-whisper` and ensure ffmpeg.")
        return None
    approx_bytes_per_sec = 12_000
    need_bytes = max(1_000_000, sample_seconds * approx_bytes_per_sec)
    headers={"Range": f"bytes=0-{need_bytes}"}
    log(f"LID: fetching ~{sample_seconds}s via HTTP Range ({need_bytes} bytes target)")
    try:
        r = s.get(audio_url, headers=headers, timeout=25); r.raise_for_status()
        size = len(r.content)
        log(f"LID: range fetch ok, got {size} bytes")
        if size < 256 * 1024:
            log(f"LID: fetched only {size} bytes (<256KB); treating as invalid and returning None")
            return None
    except Exception as e:
        log(f"LID: range fetch failed ({e}), trying full GET")
        r = s.get(audio_url, timeout=25); r.raise_for_status()
        size = len(r.content)
        log(f"LID: full fetch ok, got {size} bytes")
        if size < 256 * 1024:
            log(f"LID: fetched only {size} bytes (<256KB); treating as invalid and returning None")
            return None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as f:
        f.write(r.content); tmp_path=f.name
    try:
        log("LID: loading faster-whisper model 'tiny' (cpu,int8)")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(tmp_path, task="transcribe",
                                          language=None, beam_size=1, best_of=1,
                                          vad_filter=False, without_timestamps=True)
        for _ in segments: break
        lang = normalize_lang(info.language); prob = float(getattr(info, "language_probability", 0.0))
        log(f"LID: detected language={lang} (p={prob:.3f})")
        return (lang or None, prob)
    except Exception as e:
        log(f"LID: faster-whisper failed: {e}")
        return None
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

# -------------------- language selection

def infer_spoken_language(player: Dict[str,Any], tracks: List[Dict[str,Any]],
                          lid_method: Optional[str], lid_seconds: int,
                          s: requests.Session, video_id: str, lid_resolver: Optional[str]) -> Optional[str]:
    if lid_method == "faster":
        log("LID: requested = faster-whisper")

        # Preferred path: download a small local clip via yt-dlp and run LID on the file
        if lid_resolver == "ytdlp":
            clip = download_audio_clip_with_ytdlp(video_id, seconds=lid_seconds)
            if clip:
                out = detect_language_from_file_fwhisper(clip)
                try: shutil.rmtree(os.path.dirname(clip), ignore_errors=True)
                except Exception: pass
                if out and out[0]: return out[0]
                log("LID: yt-dlp clip path failed; falling back to URL method")

        # Fallback path: try direct/cipher-resolved URLs and range-fetch
        audio_url = pick_audio_url_direct(player)
        if not audio_url and lid_resolver == "ytdlp":
            log("LID: no direct audio URL; resolving with yt-dlp…")
            audio_url = resolve_audio_with_ytdlp(video_id)
            if audio_url: log("LID: yt-dlp resolved an audio URL")
        if audio_url:
            out = detect_language_fwhisper_from_url(s, audio_url, sample_seconds=lid_seconds)
            if out and out[0]: return out[0]
            log("LID: no result from faster-whisper; falling back to heuristics")
        else:
            log("LID: no audio URL available; falling back to heuristics")

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

def choose_track(player: Dict[str,Any], video_id: str, desired_lang: Optional[str],
                 lid_method: Optional[str], lid_seconds: int, s: requests.Session,
                 lid_resolver: Optional[str], strict_original: bool, allow_fallback: bool,
                 fail_if_mismatch: bool) -> Tuple[Dict[str,Any], str, List[Dict[str,Any]]]:
    tracks=_collect_tracks(player)
    if not tracks: raise RuntimeError("No captions available.")
    langs_summary=", ".join([f"{t['languageCode'] or '?'}{'-asr' if t['is_asr'] else ''}" for t in tracks])
    log(f"Tracks: [{langs_summary}]")
    spoken = infer_spoken_language(player, tracks, lid_method, lid_seconds, s, video_id, lid_resolver)
    log(f"Decision: spoken={spoken} desired={desired_lang or 'auto'}")
    select_lang = normalize_lang(desired_lang) if desired_lang and desired_lang!="auto" else spoken

    if not select_lang:
        if strict_original and not allow_fallback:
            raise RuntimeError("Could not determine the video's spoken language.")
        log("Selecting fallback: any manual, else any")
        for t in tracks:
            if not t.get("is_asr"): return t, spoken or (t.get("languageCode") or "unknown"), tracks
        return tracks[0], spoken or (tracks[0].get("languageCode") or "unknown"), tracks

    track = pick_track_for_language(tracks, select_lang, prefer_manual=True)
    if track:
        if fail_if_mismatch and spoken and track.get("languageCode") != spoken:
            raise RuntimeError(f"LID/track mismatch: LID={spoken}, track={track.get('languageCode')}")
        log(f"Selected track: lang={select_lang} {'ASR' if track.get('is_asr') else 'manual'}")
        return track, spoken or select_lang, tracks

    if strict_original and not allow_fallback:
        raise RuntimeError(f"No captions in spoken/desired language ({select_lang}).")
    log("No exact match. Falling back to any manual, else any")
    for t in tracks:
        if not t.get("is_asr"):
            if fail_if_mismatch and spoken and t.get("languageCode") != spoken:
                raise RuntimeError(f"LID/track mismatch: LID={spoken}, fallback={t.get('languageCode')}")
            return t, spoken or select_lang, tracks
    return tracks[0], spoken or select_lang, tracks

# -------------------- timedtext fetch & merge

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

# -------------------- playlist browse

def _text_from_runs(obj: Dict[str,Any]) -> str:
    runs=(obj or {}).get("runs") or []; return "".join(r.get("text","") for r in runs)

def browse_playlist_initial(s: requests.Session, api_key: str, client_version: str, playlist_id: str) -> Tuple[str, List[Dict[str,Any]], Optional[str]]:
    endpoint=f"{YOUTUBE}/youtubei/v1/browse"; params={"key":api_key,"prettyPrint":"false"}
    payload={"context":{"client":{"clientName":"WEB","clientVersion":client_version}}, "browseId": f"VL{playlist_id}"}
    headers={"X-YouTube-Client-Name":"1","X-YouTube-Client-Version":client_version,"Content-Type":"application/json"}
    jitter_sleep(0.3)
    r=s.post(endpoint, params=params, json=payload, headers=headers, timeout=25); r.raise_for_status()
    data=r.json()

    def find_first(d: Any, key: str) -> Optional[Dict[str,Any]]:
        if isinstance(d, dict):
            if key in d: return d
            for v in d.values():
                res=find_first(v,key)
                if res: return res
        elif isinstance(d, list):
            for v in d:
                res=find_first(v,key)
                if res: return res
        return None

    title=""
    hdr_wr=find_first(data,"playlistHeaderRenderer")
    if hdr_wr:
        hdr=hdr_wr["playlistHeaderRenderer"]
        title=hdr.get("title",{}).get("simpleText") or _text_from_runs(hdr.get("title") or {}) or ""

    videos=[]; cont_token=None
    def walk_collect(d: Any):
        nonlocal cont_token, videos
        if isinstance(d, dict):
            if "playlistVideoRenderer" in d:
                pvr=d["playlistVideoRenderer"]; vid=pvr.get("videoId")
                if vid:
                    ti=pvr.get("title") or {}
                    vtitle=ti.get("simpleText") or _text_from_runs(ti) or ""
                    idx=(pvr.get("index") or {}).get("simpleText") or ""
                    videos.append({"videoId":vid,"title":vtitle,"index":idx})
            if "continuationItemRenderer" in d:
                cir=d["continuationItemRenderer"]
                tok=(((cir.get("continuationEndpoint") or {}).get("continuationCommand") or {}).get("token"))
                if tok: cont_token=tok
            if "continuations" in d:
                cons=d.get("continuations") or []
                if cons:
                    ncd=(cons[0].get("nextContinuationData") or {})
                    tok=ncd.get("continuation")
                    if tok: cont_token=tok
            for v in d.values(): walk_collect(v)
        elif isinstance(d, list):
            for v in d: walk_collect(v)

    walk_collect(data)
    return (title or "playlist"), videos, cont_token

def browse_continuation(s: requests.Session, api_key: str, client_version: str, token: str) -> Tuple[List[Dict[str,Any]], Optional[str]]:
    endpoint=f"{YOUTUBE}/youtubei/v1/browse"; params={"key":api_key,"prettyPrint":"false"}
    payload={"context":{"client":{"clientName":"WEB","clientVersion":client_version}}, "continuation": token}
    headers={"X-YouTube-Client-Name":"1","X-YouTube-Client-Version":client_version,"Content-Type":"application/json"}
    jitter_sleep(0.3)
    r=s.post(endpoint, params=params, json=payload, headers=headers, timeout=25); r.raise_for_status()
    data=r.json()
    videos=[]; next_token=None
    actions=data.get("onResponseReceivedActions") or data.get("onResponseReceivedEndpoints") or []
    def collect(items: List[Dict[str,Any]]):
        nonlocal videos, next_token
        for c in items:
            pvr=c.get("playlistVideoRenderer")
            if pvr:
                vid=pvr.get("videoId")
                if not vid: continue
                ti=pvr.get("title") or {}
                vtitle=ti.get("simpleText") or _text_from_runs(ti) or ""
                idx=(pvr.get("index") or {}).get("simpleText") or ""
                videos.append({"videoId":vid,"title":vtitle,"index":idx})
            else:
                cir=c.get("continuationItemRenderer")
                if cir:
                    nt=(((cir.get("continuationEndpoint") or {}).get("continuationCommand") or {}).get("token"))
                    if nt: next_token=nt
    for act in actions:
        append=act.get("appendContinuationItemsAction") or act.get("reloadContinuationItemsCommand") or {}
        collect(append.get("continuationItems") or [])
    cont=data.get("continuationContents") or {}
    for _, v in cont.items():
        collect(v.get("contents") or [])
        cons=v.get("continuations") or []
        if cons:
            ncd=(cons[0].get("nextContinuationData") or {})
            tok=ncd.get("continuation")
            if tok: next_token=tok
    return videos, next_token

# -------------------- high-level ops

def get_clean_vtt_for_video(
    s: requests.Session, video_id: str,
    desired_lang: Optional[str], lid_method: Optional[str], lid_seconds: int,
    output_lang: Optional[str], allow_fallback: bool, lid_resolver: Optional[str],
    fail_if_mismatch: bool, min_coverage: float, enable_asr_fallback: bool
) -> Tuple[str, Dict[str,Any]]:
    api_key, client_version, _ = bootstrap_client_for_video(s, video_id)
    player = fetch_player(s, video_id, api_key, client_version)

    # Choose initial track (manual preferred)
    track, spoken, all_tracks = choose_track(player, video_id, desired_lang, lid_method, lid_seconds,
                                             s, lid_resolver, True, allow_fallback, fail_if_mismatch)
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

def process_single(url_or_id: str, out_path: Optional[str], desired_lang: Optional[str],
                   lid_method: Optional[str], lid_seconds: int, output_lang: Optional[str],
                   allow_fallback: bool, lid_resolver: Optional[str], fail_if_mismatch: bool,
                   min_coverage: float, enable_asr_fallback: bool):
    vid = parse_video_id(url_or_id)
    log(f"Video: {vid}")
    s = new_session()
    try:
        vtt, meta = get_clean_vtt_for_video(s, vid, desired_lang, lid_method, lid_seconds,
                                            output_lang, allow_fallback, lid_resolver, fail_if_mismatch,
                                            min_coverage, enable_asr_fallback)
    except Exception as e:
        print(f"Failed: {vid}: {e}", file=sys.stderr); sys.exit(1)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(vtt, encoding="utf-8")
        print(f"Wrote {out_path} [spoken={meta['spokenLanguage']}, source={meta['sourceLanguage']}{' (ASR)' if meta['is_auto'] else ''}, output={meta['outputLanguage']}]")
    else:
        sys.stdout.write(vtt)

def process_playlist(url: str, outdir: str, desired_lang: Optional[str],
                     lid_method: Optional[str], lid_seconds: int, output_lang: Optional[str],
                     allow_fallback: bool, lid_resolver: Optional[str], fail_if_mismatch: bool,
                     min_coverage: float, enable_asr_fallback: bool):
    s = new_session()
    pid = get_playlist_id(url) or ""
    api_key, client_version, _ = bootstrap_client_from_url(s, f"{YOUTUBE}/playlist?list={pid}&hl=en" if pid else url)
    title, videos, token = browse_playlist_initial(s, api_key, client_version, pid or "")
    folder = Path(outdir or ".") / sanitize_filename(title); folder.mkdir(parents=True, exist_ok=True)
    print(f"Playlist: {title} | Initial items: {len(videos)}")
    seen=set(v["videoId"] for v in videos)
    while token:
        more, token = browse_continuation(s, api_key, client_version, token)
        new_items=[v for v in more if v["videoId"] not in seen]
        videos.extend(new_items); seen.update(v["videoId"] for v in new_items)
        print(f"Loaded {len(videos)} items...")
    failures=0; total=len(videos)
    for i, v in enumerate(videos, start=1):
        vid=v["videoId"]; title=v.get("title") or vid
        idx=v.get("index") or ""; safe=sanitize_filename(title)
        try: idxn=int(str(idx).strip()) if idx and str(idx).strip().isdigit() else None
        except Exception: idxn=None
        fname=(f"{idxn:03d} - {safe} - {vid}.vtt" if idxn is not None else f"{i:03d} - {safe} - {vid}.vtt")
        path=folder/fname
        log(f"[{i}/{total}] Processing {vid} — {title}")
        try:
            vtt, meta = get_clean_vtt_for_video(s, vid, desired_lang, lid_method, lid_seconds,
                                                output_lang, allow_fallback, lid_resolver, fail_if_mismatch,
                                                min_coverage, enable_asr_fallback)
            path.write_text(vtt, encoding="utf-8")
            print(f"[{i}/{total}] ✓ {fname} [spoken={meta['spokenLanguage']}, source={meta['sourceLanguage']}{' (ASR)' if meta['is_auto'] else ''}, output={meta['outputLanguage']}]")
        except Exception as e:
            failures+=1
            print(f"[{i}/{total}] ✗ {fname} -> {e}", file=sys.stderr)
        jitter_sleep(0.25)
    print(f"Done. Saved in: {folder}")
    if failures: print(f"{failures} item(s) failed.", file=sys.stderr)

# -------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="YouTube captions with faster-whisper LID + yt-dlp local-clip + ASR fallback.")
    ap.add_argument("url", help="YouTube video/playlist URL or 11-char video ID")
    ap.add_argument("-o","--out", help="Output file (videos only). For playlist, use --outdir.")
    ap.add_argument("--outdir", help="Base directory for playlist folder.")
    ap.add_argument("--lang", default="auto", help="Desired source language to select (e.g., en) or 'auto'.")
    ap.add_argument("--lid", choices=["faster"], help="Use faster-whisper to detect spoken language.")
    ap.add_argument("--lid-seconds", type=int, default=50, help="Audio seconds to sample for LID (default 50).")
    ap.add_argument("--lid-resolver", choices=["ytdlp"], help="Prefer yt-dlp local-clip for LID; fallback to URL if needed.")
    ap.add_argument("--output-lang", help="Translate captions to this language (tlang).")
    ap.add_argument("--allow-fallback", action="store_true", help="If no captions in spoken/desired language, pick best available.")
    ap.add_argument("--fail-if-mismatch", action="store_true", help="Fail item if LID != selected track language.")
    ap.add_argument("--min-coverage", type=float, default=0.70, help="Min coverage ratio to keep manual track (default 0.70).")
    ap.add_argument("--no-asr-fallback", action="store_true", help="Disable ASR switch on low coverage.")
    args = ap.parse_args()

    desired_lang = None if args.lang == "auto" else normalize_lang(args.lang)
    enable_asr_fallback = not args.no_asr_fallback

    if is_playlist_url(args.url):
        process_playlist(args.url, args.outdir or ".", desired_lang, args.lid, args.lid_seconds,
                         args.output_lang, args.allow_fallback, args.lid_resolver, args.fail_if_mismatch,
                         args.min_coverage, enable_asr_fallback)
    else:
        process_single(args.url, args.out, desired_lang, args.lid, args.lid_seconds,
                       args.output_lang, args.allow_fallback, args.lid_resolver, args.fail_if_mismatch,
                       args.min_coverage, enable_asr_fallback)

if __name__ == "__main__":
    main()