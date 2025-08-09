#!/usr/bin/env python3
import os, sys, re
from pathlib import Path
from yt_dlp import YoutubeDL

if len(sys.argv) < 2:
    print("Usage: OUT_DIR=./captions python download_subs_manual_then_english_auto.py <youtube_url>")
    sys.exit(1)

URL = sys.argv[1]
OUT_DIR = Path(os.environ.get("OUT_DIR", "./captions")).resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTTMPL = str(OUT_DIR / "%(id)s.%(ext)s")

def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 10,
        "socket_timeout": 20,
        "sleep_requests": 1,
        "max_sleep_requests": 3,
    }

def probe_info(url: str):
    with YoutubeDL(base_opts()) as ydl:
        return ydl.extract_info(url, download=False)

def list_sub_files():
    return set(OUT_DIR.glob("*.srt")) | set(OUT_DIR.glob("*.vtt"))

# Minimal VTT -> SRT (no styling/position cues)
VTT_RE = re.compile(r"^\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})")
def vtt_to_srt(vtt_path: Path) -> Path:
    cues, out_lines = [], []
    with vtt_path.open("r", encoding="utf-8", errors="ignore") as f:
        block = []
        for line in f:
            if line.strip().startswith(("WEBVTT","NOTE","STYLE","REGION")):
                continue
            if line.strip() == "":
                if block:
                    cues.append(block); block = []
            else:
                block.append(line.rstrip("\n"))
        if block:
            cues.append(block)
    idx = 1
    for block in cues:
        tline = next((l for l in block if "-->" in l), None)
        if not tline: 
            continue
        m = VTT_RE.match(tline)
        if not m:
            continue
        start = m.group(1).replace(".", ",")
        end   = m.group(2).replace(".", ",")
        text  = [l for l in block if l is not tline and l.strip() != ""]
        if not text:
            continue
        out_lines.append(str(idx))
        out_lines.append(f"{start} --> {end}")
        out_lines.extend(text)
        out_lines.append("")
        idx += 1
    srt_path = vtt_path.with_suffix(".srt")
    with srt_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    return srt_path

def ensure_srt_conversion(created_files):
    """If ffmpeg wasn't available and we got .vtt, convert to .srt here."""
    srts = []
    for f in created_files:
        if f.suffix.lower() == ".srt":
            srts.append(f)
        elif f.suffix.lower() == ".vtt":
            srts.append(vtt_to_srt(f))
            try: f.unlink()
            except: pass
    return srts

def download_subs(langs, include_auto: bool):
    if not langs:
        return []
    opts = base_opts() | {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": include_auto,
        "subtitleslangs": list(langs),
        "convertsubtitles": "srt",     # uses ffmpeg if available
        "outtmpl": OUTTMPL,
    }
    before = list_sub_files()
    with YoutubeDL(opts) as ydl:
        ydl.download([URL])
    after = list_sub_files()
    return sorted(after - before)

# -------- flow --------
info = probe_info(URL)
manual = info.get("subtitles") or {}
auto   = info.get("automatic_captions") or {}

# 1) Try ALL manual subs first (download what's advertised)
manual_langs = list(manual.keys())
if manual_langs:
    created = download_subs(manual_langs, include_auto=False)
    srt_files = ensure_srt_conversion(created)
    if srt_files:
        print("Manual subtitles saved (SRT):")
        for f in srt_files:
            print(" -", f)
        sys.exit(0)

# 2) If no manual subs saved, allow auto-subs ONLY for English video + English auto
# Detect video language
video_lang = (info.get("audio_language") or info.get("language") or info.get("original_language") or "").lower()

def pick_english_auto_keys(auto_dict):
    keys = [k for k in auto_dict.keys()]
    # Prefer exact 'en', then common variants in a tight order
    priority = ["en", "en-US", "en-GB", "en-IN", "en-CA", "en-AU"]
    picked = [k for k in priority if k in keys]
    if not picked:
        picked = [k for k in keys if k.lower() == "en" or k.lower().startswith("en-")]
    # keep it tiny to avoid 429s
    return picked[:2]

if video_lang.startswith("en"):
    en_auto = pick_english_auto_keys(auto)
    if en_auto:
        created = download_subs(en_auto, include_auto=True)
        srt_files = ensure_srt_conversion(created)
        if srt_files:
            print("Auto-generated English subtitles saved (SRT):")
            for f in srt_files:
                print(" -", f)
            sys.exit(0)

print("No suitable subtitles available (manual missing; English auto not eligible or unavailable).")
sys.exit(2)