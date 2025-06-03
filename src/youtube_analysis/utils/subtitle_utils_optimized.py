"""
Optimized subtitle utilities with high-performance subtitle synchronization.
This is the enhanced version with better performance for large video transcripts.
"""

def get_optimized_custom_video_player_html(
    video_id: str,
    subtitles_data: dict,
    width: int = 700, 
    height: int = 394
) -> str:
    """
    Generate optimized HTML for a custom video player with high-performance subtitles.
    
    Performance improvements:
    - Binary search instead of linear search
    - RequestAnimationFrame instead of setInterval
    - Current segment index tracking
    - Optimized fullscreen handling
    
    Args:
        video_id: YouTube video ID
        subtitles_data: Dictionary mapping language codes to subtitle segments
        width: Video width in pixels
        height: Video height in pixels
    Returns:
        HTML string for optimized custom player with subtitles overlay
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
        <div id="{container_id}" style="position: relative;">
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
                background: rgba(0,0,0,0.3);
                padding: 4px 8px;
                border-radius: 4px;
                max-width: 90%;
                margin: 0 auto;
                word-wrap: break-word;
            "></div>
            <button id="fullscreen_btn_{video_id}" style="position: absolute; top: 10px; right: 10px; z-index: 20; background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 4px; padding: 6px 10px; cursor: pointer; font-size: 1.2em;">⛶</button>
        </div>
    </div>
    <script src="https://www.youtube.com/iframe_api"></script>
    <script type="text/javascript">
        // Optimized subtitle player for {video_id}
        var ytPlayer_{video_id} = null;
        var subtitleSegments_{video_id} = {segments_json};
        var currentSubtitle_{video_id} = '';
        var currentSegmentIndex_{video_id} = 0;
        var fullscreenOverlay_{video_id} = null;
        var updateTimer_{video_id} = null;
        var lastUpdateTime_{video_id} = 0;
        
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
                    'iv_load_policy': 3,
                    'fs': 0
                }}
            }});
        }}
        
        function onPlayerReady_{video_id}(event) {{
            console.log('YouTube player ready for {video_id}. Subtitle segments:', subtitleSegments_{video_id}.length);
            startSubtitleUpdates_{video_id}();
        }}
        
        function onPlayerStateChange_{video_id}(event) {{
            if (event.data === YT.PlayerState.PLAYING) {{
                startSubtitleUpdates_{video_id}();
            }} else if (event.data === YT.PlayerState.PAUSED || event.data === YT.PlayerState.ENDED) {{
                stopSubtitleUpdates_{video_id}();
            }}
        }}
        
        function startSubtitleUpdates_{video_id}() {{
            if (updateTimer_{video_id}) return; // Already running
            
            function updateLoop() {{
                updateSubtitle_{video_id}();
                updateTimer_{video_id} = requestAnimationFrame(updateLoop);
            }}
            updateLoop();
        }}
        
        function stopSubtitleUpdates_{video_id}() {{
            if (updateTimer_{video_id}) {{
                cancelAnimationFrame(updateTimer_{video_id});
                updateTimer_{video_id} = null;
            }}
        }}
        
        // Optimized binary search for subtitle segments
        function findCurrentSubtitle_{video_id}(time, segments) {{
            if (!segments || segments.length === 0) return null;
            
            // Performance optimization: check if we're still in the same segment
            var currentIdx = currentSegmentIndex_{video_id};
            if (currentIdx < segments.length) {{
                var current = segments[currentIdx];
                if (time >= current.start && time < current.end) {{
                    return current;
                }}
            }}
            
            // Check next segment (common case for sequential playback)
            if (currentIdx + 1 < segments.length) {{
                var next = segments[currentIdx + 1];
                if (time >= next.start && time < next.end) {{
                    currentSegmentIndex_{video_id} = currentIdx + 1;
                    return next;
                }}
            }}
            
            // Check previous segment (for seeking backwards)
            if (currentIdx > 0) {{
                var prev = segments[currentIdx - 1];
                if (time >= prev.start && time < prev.end) {{
                    currentSegmentIndex_{video_id} = currentIdx - 1;
                    return prev;
                }}
            }}
            
            // Binary search for larger jumps (seeking far)
            var left = 0;
            var right = segments.length - 1;
            
            while (left <= right) {{
                var mid = Math.floor((left + right) / 2);
                var segment = segments[mid];
                
                if (time >= segment.start && time < segment.end) {{
                    currentSegmentIndex_{video_id} = mid;
                    return segment;
                }} else if (time < segment.start) {{
                    right = mid - 1;
                }} else {{
                    left = mid + 1;
                }}
            }}
            
            return null;
        }}
        
        function updateSubtitle_{video_id}() {{
            var player = ytPlayer_{video_id};
            if (!player || typeof player.getCurrentTime !== 'function') return;
            
            var time = player.getCurrentTime();
            
            // Throttle updates slightly for performance (no need to update 60fps)
            if (Math.abs(time - lastUpdateTime_{video_id}) < 0.05) return; // 50ms throttle
            lastUpdateTime_{video_id} = time;
            
            var segments = subtitleSegments_{video_id};
            var overlay = document.getElementById('{overlay_id}');
            
            // Use optimized search
            var sub = findCurrentSubtitle_{video_id}(time, segments);
            var newText = sub ? sub.text : '';
            
            // Only update if text actually changed
            if (newText !== currentSubtitle_{video_id}) {{
                currentSubtitle_{video_id} = newText;
                
                if (document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement) {{
                    // Fullscreen mode
                    if (!fullscreenOverlay_{video_id}) {{
                        fullscreenOverlay_{video_id} = document.createElement('div');
                        fullscreenOverlay_{video_id}.id = 'fullscreen_{overlay_id}';
                        Object.assign(fullscreenOverlay_{video_id}.style, {{
                            position: 'fixed',
                            bottom: '10%',
                            left: '0',
                            width: '100vw',
                            textAlign: 'center',
                            color: 'white',
                            fontSize: '2.5em',
                            textShadow: '2px 2px 4px #000',
                            pointerEvents: 'none',
                            zIndex: '2147483647',
                            background: 'rgba(0,0,0,0.4)',
                            padding: '8px 16px',
                            borderRadius: '8px',
                            maxWidth: '90%',
                            margin: '0 auto',
                            wordWrap: 'break-word'
                        }});
                        document.body.appendChild(fullscreenOverlay_{video_id});
                    }}
                    fullscreenOverlay_{video_id}.textContent = newText;
                    if (overlay) overlay.style.display = 'none';
                }} else {{
                    // Normal mode
                    if (fullscreenOverlay_{video_id}) {{
                        fullscreenOverlay_{video_id}.remove();
                        fullscreenOverlay_{video_id} = null;
                    }}
                    if (overlay) {{
                        overlay.textContent = newText;
                        overlay.style.display = '';
                    }}
                }}
            }}
        }}
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', function() {{
            stopSubtitleUpdates_{video_id}();
            if (fullscreenOverlay_{video_id}) {{
                fullscreenOverlay_{video_id}.remove();
            }}
        }});
        
        // Listen for fullscreen changes
        ['fullscreenchange', 'webkitfullscreenchange', 'mozfullscreenchange'].forEach(function(event) {{
            document.addEventListener(event, function() {{
                if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.mozFullScreenElement) {{
                    if (fullscreenOverlay_{video_id}) {{
                        fullscreenOverlay_{video_id}.remove();
                        fullscreenOverlay_{video_id} = null;
                    }}
                }}
            }});
        }});
        
        // Custom fullscreen button
        document.getElementById('fullscreen_btn_{video_id}').onclick = function() {{
            var container = document.getElementById('{container_id}');
            if (container.requestFullscreen) {{
                container.requestFullscreen();
            }} else if (container.mozRequestFullScreen) {{
                container.mozRequestFullScreen();
            }} else if (container.webkitRequestFullscreen) {{
                container.webkitRequestFullscreen();
            }} else if (container.msRequestFullscreen) {{
                container.msRequestFullscreen();
            }}
        }};
        
        // Initialize when API is ready
        if (window.YT && window.YT.Player) {{
            onYouTubeIframeAPIReady();
        }}
    </script>
    '''
    return html