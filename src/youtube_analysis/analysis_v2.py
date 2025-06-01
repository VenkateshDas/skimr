"""
Optimized analysis module using the new service layer architecture.
This is the Phase 2 implementation with advanced performance optimizations.
"""

import asyncio
from typing import Dict, Any, Optional, Tuple, List, Callable

from .service_factory import get_video_analysis_workflow
from .utils.logging import get_logger

logger = get_logger("analysis_v2")


async def run_analysis_optimized(
    youtube_url: str,
    progress_callback: Optional[Callable[[int], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    use_cache: bool = True,
    analysis_types: Optional[List[str]] = None,
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.2
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Optimized video analysis using the new service layer architecture.
    
    Features:
    - Service layer architecture for better separation of concerns
    - Smart caching with background refresh
    - Connection pooling for better performance
    - Memory optimization and monitoring
    - Advanced error handling and recovery
    
    Args:
        youtube_url: YouTube video URL
        progress_callback: Optional progress callback (0-100)
        status_callback: Optional status message callback
        use_cache: Whether to use cached results
        analysis_types: Types of analysis to perform
        model_name: LLM model to use
        temperature: LLM temperature setting
        
    Returns:
        Tuple of (results_dict, error_message)
    """
    logger.info(f"Starting optimized analysis for {youtube_url}")
    
    try:
        # Get the workflow from service factory
        workflow = get_video_analysis_workflow()
        
        # Run the complete analysis workflow
        results, error = await workflow.analyze_video_complete(
            youtube_url=youtube_url,
            analysis_types=analysis_types,
            use_cache=use_cache,
            progress_callback=progress_callback,
            status_callback=status_callback,
            model_name=model_name,
            temperature=temperature
        )
        
        if error:
            logger.error(f"Analysis failed: {error}")
            return None, error
        
        if not results:
            logger.error("Analysis returned no results")
            return None, "Analysis failed to produce results"
        
        logger.info(f"Optimized analysis completed successfully for {youtube_url}")
        return results, None
        
    except Exception as e:
        error_msg = f"Error in optimized analysis: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def run_analysis_v2(
    youtube_url: str,
    progress_callback: Optional[Callable[[int], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    use_cache: bool = True,
    analysis_types: Optional[List[str]] = None,
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.2
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Synchronous wrapper for the optimized analysis function.
    
    This provides backward compatibility while using the new architecture.
    """
    return asyncio.run(run_analysis_optimized(
        youtube_url=youtube_url,
        progress_callback=progress_callback,
        status_callback=status_callback,
        use_cache=use_cache,
        analysis_types=analysis_types,
        model_name=model_name,
        temperature=temperature
    ))


async def get_analysis_status(video_id: str) -> Optional[Dict[str, Any]]:
    """Get analysis status for a video."""
    workflow = get_video_analysis_workflow()
    return await workflow.get_analysis_status(video_id)


async def invalidate_cache(video_id: str) -> bool:
    """Invalidate cache for a specific video."""
    workflow = get_video_analysis_workflow()
    return await workflow.invalidate_cache(video_id)


def get_performance_stats() -> Dict[str, Any]:
    """Get comprehensive performance statistics."""
    workflow = get_video_analysis_workflow()
    return workflow.get_performance_stats()


async def cleanup_analysis_resources():
    """Cleanup analysis resources."""
    from .service_factory import cleanup_services
    await cleanup_services()
    logger.info("Analysis resources cleaned up")