"""Unified LLM management for consistent model initialization."""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai import LLM
from groq import Groq

from ..utils.logging import get_logger
from .config import config

logger = get_logger("llm_manager")

@dataclass
class LLMConfig:
    """LLM configuration settings."""
    model: str = config.llm.default_model
    temperature: float = config.llm.default_temperature
    max_tokens: Optional[int] = config.llm.default_max_tokens
    timeout: int = config.llm.default_timeout
    provider: Optional[str] = None  # Added provider parameter to specify which API to use

class LLMManager:
    """Unified LLM manager for consistent model initialization."""
    
    def __init__(self):
        self._llm_cache: Dict[str, Any] = {}
    
    def get_config(self) -> LLMConfig:
        """Get LLM configuration from environment or defaults."""
        model = os.environ.get("LLM_MODEL", config.llm.default_model)
        
        # Determine provider based on model name if not explicitly set
        provider = os.environ.get("LLM_PROVIDER")
        if not provider:
            if model.startswith("gpt"):
                provider = "openai"
            elif model.startswith("gemini"):
                provider = "google"
            elif model.startswith("claude"):
                provider = "anthropic"
            elif model.startswith("groq") or model.startswith("llama") or model.startswith("mixtral"):
                provider = "groq"
        
        return LLMConfig(
            model=model,
            temperature=float(os.environ.get("LLM_TEMPERATURE", str(config.llm.default_temperature))),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "0")) or config.llm.default_max_tokens,
            timeout=int(os.environ.get("LLM_TIMEOUT", str(config.llm.default_timeout))),
            provider=provider
        )
    
    def _get_cache_key(self, config: LLMConfig, llm_type: str) -> str:
        """Generate cache key for LLM instance."""
        return f"{llm_type}_{config.model}_{config.temperature}_{config.max_tokens}_{config.provider or 'default'}"
    
    def get_langchain_llm(self, config: Optional[LLMConfig] = None) -> Any:
        """Get LangChain LLM instance or Groq LLM instance for translation."""
        config = config or self.get_config()
        cache_key = self._get_cache_key(config, "langchain")
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        logger.info(f"Creating LangChain LLM: {config.model} (temp: {config.temperature}, provider: {config.provider or 'auto'})")
        
        # Determine provider based on explicit provider parameter or model name prefix
        if config.provider == "openai" or (not config.provider and config.model.startswith("gpt")):
            llm = ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout
            )
        elif config.provider == "anthropic" or (not config.provider and config.model.startswith("claude")):
            llm = ChatAnthropic(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        elif config.provider == "google" or (not config.provider and config.model.startswith("gemini")):
            llm = ChatGoogleGenerativeAI(
                model=config.model,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                timeout=config.timeout,
                google_api_key=os.getenv("GEMINI_API_KEY")
            )
        elif config.provider == "groq" or (not config.provider and (config.model.startswith("groq") or 
                                                         config.model.startswith("llama") or 
                                                         config.model.startswith("mixtral"))):
            # Use Groq API for chat completions
            class GroqChatLLM:
                def __init__(self, model, temperature):
                    self.model = model
                    self.temperature = temperature
                    self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
                async def ainvoke(self, messages, **kwargs):
                    # Convert LangChain messages to OpenAI format
                    chat_messages = []
                    for m in messages:
                        role = "system" if getattr(m, "type", None) == "system" else "user"
                        chat_messages.append({"role": role, "content": m.content})
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=chat_messages,
                        temperature=self.temperature,
                        stream=False
                    )
                    class Response:
                        def __init__(self, content):
                            self.content = content
                    return Response(response.choices[0].message.content)
            llm = GroqChatLLM(model=config.model, temperature=config.temperature)
        else:
            raise ValueError(f"Unsupported model/provider combination: {config.model} with provider {config.provider}")
        
        self._llm_cache[cache_key] = llm
        return llm
    
    def get_crewai_llm(self, config: Optional[LLMConfig] = None) -> LLM:
        """Get CrewAI LLM instance."""
        config = config or self.get_config()
        cache_key = self._get_cache_key(config, "crewai")
        
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        logger.info(f"Creating CrewAI LLM: {config.model} (temp: {config.temperature}, provider: {config.provider or 'auto'})")
        
        # Use explicit provider if specified, otherwise infer from model name
        if config.provider == "openai" or (not config.provider and config.model.startswith("gpt")):
            llm = LLM(
                model=config.model,
                temperature=config.temperature,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        elif config.provider == "anthropic" or (not config.provider and config.model.startswith("claude")):
            llm = LLM(
                model=f"anthropic/{config.model}",
                temperature=config.temperature,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        elif config.provider == "google" or (not config.provider and config.model.startswith("gemini")):
            llm = LLM(
                model=f"gemini/{config.model}",
                temperature=config.temperature,
                api_key=os.getenv("GEMINI_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported model/provider combination: {config.model} with provider {config.provider}")
        
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