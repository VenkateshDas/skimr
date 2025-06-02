"""Factory for creating and configuring services."""

from .core import CacheManager, YouTubeClient, LLMManager
from .repositories import CacheRepository, YouTubeRepository
from .services import AnalysisService, TranscriptService, ChatService, ContentService
from .workflows.video_analysis_workflow import VideoAnalysisWorkflow
from .utils.logging import get_logger

logger = get_logger("service_factory")


class ServiceFactory:
    """Factory for creating and managing service dependencies."""
    
    def __init__(self):
        self._cache_manager = None
        self._youtube_client = None
        self._llm_manager = None
        self._cache_repository = None
        self._youtube_repository = None
        self._analysis_service = None
        self._transcript_service = None
        self._chat_service = None
        self._content_service = None
        self._workflow = None
        
        logger.info("Initialized ServiceFactory")
    
    def get_cache_manager(self) -> CacheManager:
        """Get or create cache manager."""
        if self._cache_manager is None:
            self._cache_manager = CacheManager()
        return self._cache_manager
    
    def get_youtube_client(self) -> YouTubeClient:
        """Get or create YouTube client."""
        if self._youtube_client is None:
            cache_manager = self.get_cache_manager()
            self._youtube_client = YouTubeClient(cache_manager)
        return self._youtube_client
    
    def get_llm_manager(self) -> LLMManager:
        """Get or create LLM manager."""
        if self._llm_manager is None:
            self._llm_manager = LLMManager()
        return self._llm_manager
    
    def get_cache_repository(self) -> CacheRepository:
        """Get or create cache repository."""
        if self._cache_repository is None:
            cache_manager = self.get_cache_manager()
            self._cache_repository = CacheRepository(cache_manager)
        return self._cache_repository
    
    def get_youtube_repository(self) -> YouTubeRepository:
        """Get or create YouTube repository."""
        if self._youtube_repository is None:
            youtube_client = self.get_youtube_client()
            self._youtube_repository = YouTubeRepository(youtube_client)
        return self._youtube_repository
    
    def get_analysis_service(self) -> AnalysisService:
        """Get or create analysis service."""
        if self._analysis_service is None:
            cache_repo = self.get_cache_repository()
            youtube_repo = self.get_youtube_repository()
            llm_manager = self.get_llm_manager()
            self._analysis_service = AnalysisService(cache_repo, youtube_repo, llm_manager)
        return self._analysis_service
    
    def get_transcript_service(self) -> TranscriptService:
        """Get or create transcript service."""
        if self._transcript_service is None:
            cache_repo = self.get_cache_repository()
            youtube_repo = self.get_youtube_repository()
            self._transcript_service = TranscriptService(cache_repo, youtube_repo)
        return self._transcript_service
    
    def get_chat_service(self) -> ChatService:
        """Get or create chat service."""
        if self._chat_service is None:
            cache_repo = self.get_cache_repository()
            youtube_repo = self.get_youtube_repository()
            self._chat_service = ChatService(cache_repo, youtube_repo)
        return self._chat_service
    
    def get_content_service(self) -> ContentService:
        """Get or create content service."""
        if self._content_service is None:
            cache_repo = self.get_cache_repository()
            self._content_service = ContentService(cache_repo)
        return self._content_service
    
    def get_video_analysis_workflow(self) -> VideoAnalysisWorkflow:
        """Get or create video analysis workflow."""
        if self._workflow is None:
            analysis_service = self.get_analysis_service()
            transcript_service = self.get_transcript_service()
            chat_service = self.get_chat_service()
            content_service = self.get_content_service()
            
            self._workflow = VideoAnalysisWorkflow(
                analysis_service,
                transcript_service,
                chat_service,
                content_service
            )
        return self._workflow
    
    async def cleanup(self):
        """Cleanup all services."""
        if self._cache_repository:
            await self._cache_repository.cleanup()
        
        if self._youtube_repository:
            await self._youtube_repository.cleanup()
        
        logger.info("ServiceFactory cleanup completed")


# Global service factory instance
_service_factory = None


def get_service_factory() -> ServiceFactory:
    """Get the global service factory instance."""
    global _service_factory
    if _service_factory is None:
        _service_factory = ServiceFactory()
    return _service_factory


# Convenience functions for direct access
def get_video_analysis_workflow() -> VideoAnalysisWorkflow:
    """Get the video analysis workflow."""
    return get_service_factory().get_video_analysis_workflow()


def get_analysis_service() -> AnalysisService:
    """Get the analysis service."""
    return get_service_factory().get_analysis_service()


def get_transcript_service() -> TranscriptService:
    """Get the transcript service."""
    return get_service_factory().get_transcript_service()


def get_chat_service() -> ChatService:
    """Get the chat service."""
    return get_service_factory().get_chat_service()


async def cleanup_services():
    """Cleanup all services."""
    global _service_factory
    if _service_factory:
        await _service_factory.cleanup()
        _service_factory = None