from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from youtube_analysis.models.analysis import AnalysisRequest, AnalysisResponse
from youtube_analysis.services.analysis_service import analyze_youtube_video
from youtube_analysis.utils.cache_utils import (
    get_cached_analysis,
    cache_analysis,
    clear_analysis_cache,
)

router = APIRouter()

@router.post("/analyze")
async def analyze_video(request: AnalysisRequest) -> AnalysisResponse:
    """
    Analyze a YouTube video and return insights.
    
    Args:
        request: The analysis request containing the video ID and options
        
    Returns:
        The analysis results
    """
    video_id = request.video_id
    use_cache = request.use_cache if request.use_cache is not None else True
    
    # Check cache first if enabled
    if use_cache:
        cached_result = get_cached_analysis(video_id)
        if cached_result:
            return AnalysisResponse(
                video_id=video_id,
                analysis=cached_result,
                source="cache"
            )
    
    # Perform analysis
    try:
        analysis_result = await analyze_youtube_video(video_id)
        
        # Cache the result
        if use_cache:
            cache_analysis(video_id, analysis_result)
        
        return AnalysisResponse(
            video_id=video_id,
            analysis=analysis_result,
            source="api"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.delete("/cache/{video_id}")
async def clear_cache(video_id: str) -> dict:
    """
    Clear the cached analysis for a specific video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        A dictionary with the status of the operation
    """
    success = clear_analysis_cache(video_id)
    
    if success:
        return {"status": "success", "message": f"Cache cleared for video {video_id}"}
    else:
        return {"status": "not_found", "message": f"No cache found for video {video_id}"} 