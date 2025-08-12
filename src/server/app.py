from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from nicegui import ui
import os
import sys

# Ensure 'src' is on sys.path so 'youtube_analysis' is importable when running from repo root
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from youtube_analysis.adapters.webapp_adapter import WebAppAdapter
from youtube_analysis.core.config import setup_logging
from youtube_analysis.service_factory import get_service_factory
from .schemas import (
    AnalyzeRequest, AnalyzeResponse,
    GenerateRequest, GenerateResponse,
    TranscriptRequest, TranscriptResponse,
    TranslateRequest, TranslateResponse,
    CacheClearRequest, ErrorResponse,
)


# ----------------------------------------------------------------------------
# FastAPI lifecycle
# ----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    # Warm up service factory
    get_service_factory()
    yield
    # Cleanup will be handled by service factory if needed later


app = FastAPI(lifespan=lifespan)

# Optional CORS (configure via env if needed)
allow_origins = os.environ.get('CORS_ALLOW_ORIGINS', '')
if allow_origins:
    origins = [o.strip() for o in allow_origins.split(',') if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse(error={"message": message}).model_dump())


def _normalize_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not settings:
        return {}
    # Convert pydantic model to dict if needed
    if hasattr(settings, 'model_dump'):
        return settings.model_dump(exclude_none=True)
    return {k: v for k, v in settings.items() if v is not None}


# ----------------------------------------------------------------------------
# API Routes
# ----------------------------------------------------------------------------

@app.post('/api/analyze', response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    adapter = WebAppAdapter()
    settings = _normalize_settings(req.settings)
    if not adapter.validate_youtube_url(req.youtube_url):
        raise HTTPException(status_code=422, detail='Invalid YouTube URL')
    results, error = await adapter.analyze_video(req.youtube_url, settings)
    if error:
        raise HTTPException(status_code=500, detail=error)
    if not results:
        raise HTTPException(status_code=500, detail='Analysis failed to produce results')
    # Remove non-serializable/heavy fields
    try:
        if 'chat_details' in results:
            # Chat is handled via WS; do not return internal agent objects
            results.pop('chat_details', None)
        # Some adapters may include full video_data objects; drop them if present
        results.pop('video_data', None)
    except Exception:
        pass
    return AnalyzeResponse(result=results)


@app.get('/healthz')
async def healthz():
    return {"status": "ok"}


@app.get('/api/analysis/{video_id}', response_model=AnalyzeResponse)
async def get_analysis(video_id: str):
    # Fetch from cache via service factory
    cache_repo = get_service_factory().get_cache_repository()
    result = await cache_repo.get_analysis_result(video_id)
    if not result:
        raise HTTPException(status_code=404, detail='Analysis not found')
    return AnalyzeResponse(result=result.to_dict())


@app.post('/api/generate', response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    adapter = WebAppAdapter()
    settings = _normalize_settings(req.settings)
    if 'custom_instruction' in req.model_fields_set and req.custom_instruction:
        settings['custom_instruction'] = req.custom_instruction
    content, error, token_usage = await adapter.generate_additional_content(
        youtube_url=req.youtube_url,
        video_id=req.video_id,
        transcript_text=req.transcript_text,
        content_type=req.content_type,
        settings=settings,
    )
    if error:
        raise HTTPException(status_code=500, detail=error)
    return GenerateResponse(content=content, token_usage=token_usage)


@app.post('/api/transcript', response_model=TranscriptResponse)
async def transcript(req: TranscriptRequest):
    # Call transcript service directly to avoid asyncio.run collisions
    transcript_service = get_service_factory().get_transcript_service()
    timestamped, segments = await transcript_service.get_formatted_transcripts(
        youtube_url=req.youtube_url, video_id=req.video_id, use_cache=req.use_cache
    )
    if not timestamped or segments is None:
        raise HTTPException(status_code=500, detail='Could not retrieve transcript')
    return TranscriptResponse(transcript=timestamped, segments=segments)


@app.post('/api/translate', response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    translation_service = get_service_factory().get_translation_service()
    try:
        translated_text, translated_segments = await translation_service.translate_transcript(
            segments=req.segments,
            source_language=req.source_language or 'en',
            target_language=req.target_language,
            video_id=req.video_id,
            use_cache=True,
        )
        return TranslateResponse(translated_text=translated_text, translated_segments=translated_segments)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/cache/clear')
async def cache_clear(req: CacheClearRequest):
    # Avoid adapter (it uses asyncio.run). Clear caches directly via repository
    try:
        workflow = get_service_factory().get_video_analysis_workflow()
        cache_repo = workflow.analysis_service.cache_repo
        await cache_repo.clear_video_cache(req.video_id)
        await cache_repo.clear_token_usage_cache(req.video_id)
        # Clear translations for this video
        await cache_repo.delete_custom_data('translations', f'translated_transcript_{req.video_id}_*')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/token_usage/{video_id}')
async def token_usage(video_id: str):
    adapter = WebAppAdapter()
    data = await adapter.get_cached_token_usage(video_id)
    return data or {}


@app.get('/api/performance')
async def performance_stats():
    analysis_service = get_service_factory().get_analysis_service()
    try:
        return analysis_service.get_performance_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------------
# Chat WebSocket (streaming)
# ----------------------------------------------------------------------------

@app.websocket('/ws/chat/{video_id}')
async def chat_ws(websocket: WebSocket, video_id: str):
    await websocket.accept()
    adapter = WebAppAdapter()
    try:
        while True:
            payload = await websocket.receive_json()
            history = payload.get('history', [])
            question = payload.get('question', '')
            settings = payload.get('settings', {})

            async for chunk, token_usage in adapter.get_chat_response_stream(
                video_id=video_id,
                chat_history=history,
                current_question=question,
                settings=settings,
            ):
                if chunk:
                    await websocket.send_json({"chunk": chunk})
                if token_usage is not None:
                    # Persist chat token usage to cache
                    try:
                        await adapter.save_token_usage_to_cache(video_id, "chat", token_usage)
                    except Exception:
                        pass
                    await websocket.send_json({"token_usage": token_usage, "done": True})
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
        await websocket.close(code=1011)


# ----------------------------------------------------------------------------
# NiceGUI UI (Co-hosted)
# ----------------------------------------------------------------------------

# Mount NiceGUI onto this FastAPI app
ui.run_with(app)

def _build_header() -> None:
    with ui.header().classes('items-center justify-between'):
        ui.label('Skimr').classes('text-2xl font-bold')
        with ui.row():
            ui.link('Home', '/').props('no-caps')
            ui.link('Analysis', '/analysis').props('no-caps')


@ui.page('/')
def home_page() -> None:
    _build_header()
    ui.separator()
    ui.label('Skim through YouTube. Know what matters fast.').classes('text-stone-600')
    url_input = ui.input(label='YouTube URL', placeholder='https://www.youtube.com/watch?v=...').classes('w-full')
    progress = ui.linear_progress(show_value=False).props('rounded').classes('w-full').bind_visibility_from(url_input, 'value')
    status_text = ui.label('').classes('text-sm text-stone-500')

    async def on_analyze() -> None:
        status_text.text = 'Starting analysis...'
        try:
            req = AnalyzeRequest(youtube_url=url_input.value or '', settings=None)
            resp = await analyze(req)  # call local handler to keep logic in one place
            video_id = resp.result.get('video_id')
            status_text.text = 'Analysis complete'
            ui.navigate.to(f'/analysis?video_id={video_id}')
        except Exception as e:
            status_text.text = f'Error: {e}'

    ui.button('Analyze', on_click=on_analyze).props('unelevated color=primary').bind_enabled_from(url_input, 'value')
    ui.space()
    ui.label('Tip: You can generate Action Plan, Blog, LinkedIn, and X content after analysis.').classes('text-sm text-stone-500')


@ui.page('/analysis')
def analysis_page(client: ui.Client, video_id: Optional[str] = None):
    _build_header()
    ui.separator()
    params = client.request.args
    vid = params.get('video_id', video_id)
    if not vid:
        ui.label('No video selected.').classes('text-negative')
        return

    info_card = ui.card().classes('w-full')
    with info_card:
        ui.label(f'Video: {vid}').classes('text-lg')
        ui.separator()
        content_area = ui.markdown('Loading analysis...')

    async def load_analysis() -> None:
        try:
            resp = await get_analysis(vid)  # use API handler for consistency
            result = resp.result
            title = result.get('video_info', {}).get('title') or 'YouTube Video'
            ui.label(title).classes('text-xl font-medium')
            tabs = ui.tabs().classes('w-full')
            with ui.tab_panels(tabs, value='summary').classes('w-full'):
                with ui.tab_panel('summary'):
                    content = _extract_content(result, 'classify_and_summarize_content')
                    ui.markdown(content or 'No summary').classes('prose max-w-none')
                with ui.tab_panel('action_plan'):
                    content = _extract_content(result, 'analyze_and_plan_content')
                    ui.markdown(content or 'Not generated').classes('prose max-w-none')
                with ui.tab_panel('blog'):
                    content = _extract_content(result, 'write_blog_post')
                    ui.markdown(content or 'Not generated').classes('prose max-w-none')
                with ui.tab_panel('linkedin'):
                    content = _extract_content(result, 'write_linkedin_post')
                    ui.markdown(content or 'Not generated').classes('prose max-w-none')
                with ui.tab_panel('tweet'):
                    content = _extract_content(result, 'write_tweet')
                    ui.markdown(content or 'Not generated').classes('prose max-w-none')
                with ui.tab_panel('transcript'):
                    t = result.get('transcript') or ''
                    ui.textarea(value=t, label='Transcript', autogrow=True).props('readonly').classes('w-full h-80')
            content_area.set_text('')
        except Exception as e:
            content_area.set_text(f'Error loading analysis: {e}')

    asyncio.create_task(load_analysis())


def _extract_content(result: Dict[str, Any], task_key: str) -> Optional[str]:
    task_outputs = result.get('task_outputs') or {}
    item = task_outputs.get(task_key)
    if isinstance(item, dict):
        return item.get('content')
    if isinstance(item, str):
        return item
    return None


if __name__ in {"__main__", "server.app"}:  # pragma: no cover
    # Run via: python -m server.app
    from uvicorn import run
    run('server.app:app', host='0.0.0.0', port=8000, reload=True)


