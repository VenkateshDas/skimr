"""Unified LLM management for consistent model initialization."""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai import LLM

from ..utils.logging import get_logger

logger = get_logger("llm_manager")

@dataclass
class LLMConfig:
    """LLM configuration settings."""
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    timeout: int = 60

class LLMManager:
    """Unified LLM manager for consistent model initialization."""
    
    def __init__(self):
        self._llm_cache: Dict[str, Any] = {}
    
    def get_config(self) -> LLMConfig:
        """Get LLM configuration from environment or defaults."""
        return LLMConfig(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "0")) or None,
            timeout=int(os.environ.get("LLM_TIMEOUT", "60"))
        )
    
    def _get_cache_key(self, config: LLMConfig, llm_type: str) -> str:
        """Generate cache key for LLM instance."""
        return f"{llm_type}_{config.model}_{config.temperature}_{config.max_tokens}"
    
    def get_langchain_llm(self, config: Optional[LLMConfig] = None) -> Any:
        """Get LangChain LLM instance."""
        config = config or self.get_config()
        cache_key = self._get_cache_key(config, "langchain")
        
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        logger.info(f"Creating LangChain LLM: {config.model} (temp: {config.temperature})")
        
        if config.model.startswith("gpt"):
            llm = ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout
            )
        elif config.model.startswith("claude"):
            llm = ChatAnthropic(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        elif config.model.startswith("gemini"):
            llm = ChatGoogleGenerativeAI(
                model=config.model,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                timeout=config.timeout,
                google_api_key=os.getenv("GEMINI_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported model: {config.model}")
        
        self._llm_cache[cache_key] = llm
        return llm
    
    def get_crewai_llm(self, config: Optional[LLMConfig] = None) -> LLM:
        """Get CrewAI LLM instance."""
        config = config or self.get_config()
        cache_key = self._get_cache_key(config, "crewai")
        
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        logger.info(f"Creating CrewAI LLM: {config.model} (temp: {config.temperature})")
        
        if config.model.startswith("gpt"):
            llm = LLM(
                model=config.model,
                temperature=config.temperature,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        elif config.model.startswith("claude"):
            llm = LLM(
                model=f"anthropic/{config.model}",
                temperature=config.temperature,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        elif config.model.startswith("gemini"):
            llm = LLM(
                model=f"gemini/{config.model}",
                temperature=config.temperature,
                api_key=os.getenv("GEMINI_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported model: {config.model}")
        
        self._llm_cache[cache_key] = llm
        return llm
    
    def clear_cache(self) -> None:
        """Clear LLM cache."""
        logger.info(f"Clearing LLM cache ({len(self._llm_cache)} instances)")
        self._llm_cache.clear()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        return {
            "cached_instances": len(self._llm_cache),
            "cache_keys": list(self._llm_cache.keys())
        }