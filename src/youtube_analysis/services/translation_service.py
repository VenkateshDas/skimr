"""Service for transcript translation using OpenAI models."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import os
import re

from langchain_core.messages import SystemMessage, HumanMessage

from ..core.llm_manager import LLMManager, LLMConfig
from ..repositories import CacheRepository, YouTubeRepository
from ..utils.logging import get_logger
from ..utils.language_utils import get_language_name, validate_language_code, get_supported_languages

logger = get_logger("translation_service")

class TranslationService:
    """Service for translating transcripts and generating subtitle files."""
    
    def __init__(
        self, 
        cache_repository: CacheRepository, 
        youtube_repository: YouTubeRepository, 
        llm_manager: LLMManager
    ):
        """Initialize the translation service."""
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        self.llm_manager = llm_manager
        logger.info("Initialized TranslationService")
    
    async def translate_transcript(
        self,
        segments: List[Dict[str, Any]],
        source_language: str,
        target_language: str,
        video_id: str = None,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Translate transcript segments to target language.
        
        Args:
            segments: List of transcript segments
            source_language: ISO-639-1 language code for source
            target_language: ISO-639-1 language code for target
            video_id: YouTube video ID (for caching)
            use_cache: Whether to use cached translations
            
        Returns:
            Tuple of (translated transcript text, translated segment list)
        """
        if not segments:
            logger.error("No segments provided for translation")
            return None, None
            
        # Validate languages
        if not validate_language_code(target_language):
            logger.error(f"Invalid target language code: {target_language}")
            return None, None
            
        if source_language and not validate_language_code(source_language):
            logger.warning(f"Invalid source language code: {source_language}, will auto-detect")
            source_language = "en"  # Default to English
        
        # Check if source and target are the same
        if source_language == target_language:
            logger.info(f"Source and target languages are the same ({target_language}), no translation needed")
            return " ".join([seg.get("text", "") for seg in segments]), segments
        
        # Create a unique cache key for this translation
        cache_key = f"translated_transcript_{video_id or 'unknown'}_{source_language}_{target_language}"
        
        # Try to get from cache first
        if use_cache and video_id:
            cached_data = await self.cache_repo.get_custom_data("translations", cache_key)
            if cached_data:
                logger.info(f"Using cached translation for {video_id} to {target_language}")
                return cached_data.get("text"), cached_data.get("segments")
        
        # Perform translation
        try:
            translated_text, translated_segments = await self._translate_segments(
                segments, 
                source_language,
                target_language
            )
            
            # Cache the results
            if use_cache and video_id:
                await self.cache_repo.store_custom_data(
                    "translations",
                    cache_key,
                    {
                        "text": translated_text,
                        "segments": translated_segments
                    }
                )
            
            logger.info(f"Successfully translated transcript to {target_language}")
            return translated_text, translated_segments
            
        except Exception as e:
            logger.error(f"Error translating transcript: {str(e)}")
            return None, None
    
    async def _translate_segments(
        self,
        segments: List[Dict[str, Any]],
        source_language: str,
        target_language: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Translate transcript segments to the target language in parallel batches.
        """
        import asyncio
        source_language_name = get_language_name(source_language) or source_language
        target_language_name = get_language_name(target_language) or target_language
        batch_size = 8
        segment_batches = [segments[i:i+batch_size] for i in range(0, len(segments), batch_size)]
        semaphore = asyncio.Semaphore(3)

        async def translate_batch(batch_idx, batch):
            async with semaphore:
                logger.debug(f"Translating batch {batch_idx+1}/{len(segment_batches)} with {len(batch)} segments")
                start_idx = batch_idx * batch_size
                texts_to_translate = [
                    f"[{start_idx + i}] {segment.get('text', '')}"
                    for i, segment in enumerate(batch)
                ]
                combined_text = "\n".join(texts_to_translate)
                system_message = (
                    f"You are a professional translator specialized in translating from {source_language_name} "
                    f"to {target_language_name}. Translate the following subtitles accurately, preserving the "
                    f"original meaning, tone, and formatting. You MUST return exactly {len(batch)} lines, one for each numbered input segment, "
                    f"and each line must start with the same [index] as the input. Do not skip or merge any segments. "
                    f"If a segment is empty, return an empty translation for that index."
                )
                user_message_content = (
                    f"Translate each of these numbered segments from {source_language_name} to {target_language_name}. "
                    f"Return exactly {len(batch)} lines, each starting with the [number] from the input.\n\n"
                    f"{combined_text}\n\n"
                    f"Important: Your response MUST include ALL segment numbers from the original text, in the same order, one per line. "
                    f"Do not skip, merge, or reorder any segments."
                )
                try:
                    model_name = os.environ.get("LLM_DEFAULT_MODEL", "gpt-4.1-mini")
                    provider = None
                    if model_name.startswith("gpt"):
                        provider = "openai"
                    elif model_name.startswith("gemini"):
                        provider = "google"
                    elif model_name.startswith("claude"):
                        provider = "anthropic"
                    llm_config = LLMConfig(
                        model=model_name,
                        temperature=0.3,
                        provider=provider
                    )
                    logger.info(f"Translation with model: {llm_config.model} (provider: {provider or 'auto'})")
                    langchain_llm = self.llm_manager.get_langchain_llm(config=llm_config)
                    messages = [
                        SystemMessage(content=system_message),
                        HumanMessage(content=user_message_content)
                    ]
                    response = await langchain_llm.ainvoke(messages)
                    translated_text = response.content.strip()
                    translated_lines = [line.strip() for line in translated_text.split("\n") if line.strip()]
                    processed_translations = {}
                    for line in translated_lines:
                        # Robust: allow for extra whitespace, colon, dash, etc.
                        m = re.match(r"\[\s*(\d+)\s*\][\s:.-]*(.*)", line)
                        if m:
                            idx = int(m.group(1))
                            batch_relative_index = idx - start_idx
                            if 0 <= batch_relative_index < len(batch):
                                processed_translations[batch_relative_index] = m.group(2).strip()
                    # If any segment is missing, log the full LLM output
                    missing_segments = [i for i in range(len(batch)) if i not in processed_translations]
                    if missing_segments:
                        logger.warning(f"Batch {batch_idx+1} missing segments {missing_segments}. LLM output:\n{translated_text}")
                        # Immediately fill missing segments with individual translation
                        for i in missing_segments:
                            segment = batch[i]
                            translated_segment = segment.copy()
                            try:
                                single_segment_message = f"Translate this from {source_language_name} to {target_language_name}: {segment.get('text', '')}"
                                single_response = await langchain_llm.ainvoke([HumanMessage(content=single_segment_message)])
                                single_translation = single_response.content.strip()
                                if single_translation:
                                    processed_translations[i] = single_translation
                                    logger.info(f"Successfully translated segment {start_idx + i} individually")
                                else:
                                    logger.warning(f"Individual translation for segment {start_idx + i} failed, using original")
                                    processed_translations[i] = segment.get("text", "")
                            except Exception as e:
                                logger.warning(f"Individual translation for segment {start_idx + i} failed: {str(e)}, using original")
                                processed_translations[i] = segment.get("text", "")
                    # Create translated segments in order
                    batch_translated_segments = []
                    for i, segment in enumerate(batch):
                        translated_segment = segment.copy()
                        translated_segment["text"] = processed_translations.get(i, segment.get("text", ""))
                        batch_translated_segments.append(translated_segment)
                    return batch_idx, batch_translated_segments
                except Exception as e:
                    logger.error(f"Error in batch translation: {str(e)}")
                    batch_translated_segments = []
                    for segment in batch:
                        translated_segment = segment.copy()
                        batch_translated_segments.append(translated_segment)
                    return batch_idx, batch_translated_segments

        tasks = [translate_batch(idx, batch) for idx, batch in enumerate(segment_batches)]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda x: x[0])
        translated_segments = [seg for _, batch in results for seg in batch]
        full_translated_text = " ".join([segment.get("text", "") for segment in translated_segments])
        return full_translated_text, translated_segments
    
    def translate_transcript_sync(
        self,
        segments: List[Dict[str, Any]],
        source_language: str,
        target_language: str,
        video_id: str = None,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Synchronous wrapper for translate_transcript.
        
        Args:
            segments: List of transcript segments
            source_language: ISO-639-1 language code for source
            target_language: ISO-639-1 language code for target
            video_id: YouTube video ID (for caching)
            use_cache: Whether to use cached translations
            
        Returns:
            Tuple of (translated transcript text, translated segment list)
        """
        try:
            # Run the async method in a new event loop
            return asyncio.run(self.translate_transcript(
                segments=segments,
                source_language=source_language,
                target_language=target_language,
                video_id=video_id,
                use_cache=use_cache
            ))
        except RuntimeError as re:
            # Handle case when event loop is already running
            if "already running" in str(re):
                logger.warning("Event loop already running, using threaded execution")
                
                # Execute in a thread
                import threading
                import concurrent.futures
                
                result = [None, None]
                
                def run_in_thread():
                    try:
                        # Create a new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Run the async function and store result
                        translation_result = loop.run_until_complete(self.translate_transcript(
                            segments=segments,
                            source_language=source_language,
                            target_language=target_language,
                            video_id=video_id,
                            use_cache=use_cache
                        ))
                        
                        # Update the result
                        if translation_result:
                            result[0] = translation_result[0]
                            result[1] = translation_result[1]
                        
                        # Clean up
                        loop.close()
                    except Exception as e:
                        logger.error(f"Thread execution error: {str(e)}")
                
                # Execute in a thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    future.result()  # Wait for completion
                
                return tuple(result)
            else:
                # For other RuntimeError cases, re-raise
                raise
        except Exception as e:
            logger.error(f"Error in translate_transcript_sync: {str(e)}")
            return None, None
    
    def estimate_translation_cost(self, segments: List[Dict[str, Any]], model: str = None) -> float:
        """
        Estimate the cost of translating segments.
        
        Args:
            segments: List of transcript segments
            model: OpenAI model to use (defaults to the configured model)
            
        Returns:
            Estimated cost in USD
        """
        if not segments:
            return 0.0
        
        # Estimate token count (rough approximation)
        total_text = " ".join([seg.get("text", "") for seg in segments])
        word_count = len(total_text.split())
        
        # Estimate token count (1.3 tokens per word is a common estimate)
        token_count = word_count * 1.3
        
        # Add overhead for system messages, etc.
        token_count *= 1.2
        
        # Calculate cost based on model
        # Default to gpt-3.5-turbo rates
        input_cost_per_1k = 0.0015  # $0.0015 per 1K input tokens
        output_cost_per_1k = 0.002   # $0.002 per 1K output tokens
        
        # If model specified, use specific rates
        if model and "gpt-4" in model:
            input_cost_per_1k = 0.03  # $0.03 per 1K input tokens
            output_cost_per_1k = 0.06  # $0.06 per 1K output tokens
        
        # Calculate costs (assuming output tokens roughly equal to input)
        input_cost = token_count * input_cost_per_1k / 1000
        output_cost = token_count * output_cost_per_1k / 1000
        
        return input_cost + output_cost 