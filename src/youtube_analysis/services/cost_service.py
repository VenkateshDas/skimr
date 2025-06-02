"""
Service for calculating LLM costs using Glama.ai API.

This service provides dynamic cost calculation using real-time model pricing data
from the Glama.ai cost calculator API, replacing static environment variable-based costs.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
import requests
from ..utils.logging import get_logger
from ..core.config import config

logger = get_logger("cost_service")


@dataclass
class ModelInfo:
    """Information about a supported model."""
    name: str
    provider: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    max_context: Optional[int] = None
    description: Optional[str] = None


@dataclass
class CostCalculation:
    """Result of a cost calculation."""
    total_cost: float
    input_cost: float
    output_cost: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    calculated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_cost": self.total_cost,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "calculated_at": self.calculated_at.isoformat()
        }


class CostService:
    """Service for calculating LLM costs using Glama.ai API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the cost service.
        
        Args:
            api_key: Glama.ai API key. If None, will attempt to get from environment.
        """
        self.api_key = api_key or self._get_api_key_from_env()
        self.base_url = "https://glama.ai/api/cost-calculator"
        
        # Cache for model information and costs
        self._models_cache: Optional[List[str]] = None
        self._models_cache_expiry: Optional[datetime] = None
        self._cost_cache: Dict[str, Tuple[float, datetime]] = {}
        
        # Cache expiry settings
        self.models_cache_duration = timedelta(hours=24)  # Cache models for 24 hours
        self.cost_cache_duration = timedelta(hours=1)     # Cache costs for 1 hour
        
        logger.info("Initialized CostService with Glama.ai API")
    
    def _get_api_key_from_env(self) -> Optional[str]:
        """Get API key from environment variables."""
        import os
        return os.getenv('GLAMA_API_KEY')
    
    def _is_cache_valid(self, cache_time: Optional[datetime], duration: timedelta) -> bool:
        """Check if cache is still valid."""
        if not cache_time:
            return False
        return datetime.now() - cache_time < duration
    
    async def get_supported_models(self, force_refresh: bool = False) -> List[str]:
        """
        Get list of supported models from Glama.ai API.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of model names supported by the API
        """
        # Check cache first
        if (not force_refresh and 
            self._models_cache and 
            self._is_cache_valid(self._models_cache_expiry, self.models_cache_duration)):
            logger.debug("Returning cached model list")
            return self._models_cache
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/models"
                async with session.get(url) as response:
                    if response.status == 200:
                        models = await response.json()
                        # Cache the results
                        self._models_cache = models
                        self._models_cache_expiry = datetime.now()
                        logger.info(f"Fetched {len(models)} supported models from Glama.ai")
                        return models
                    else:
                        logger.error(f"Failed to fetch models: HTTP {response.status}")
                        return self._get_fallback_models()
        except Exception as e:
            logger.error(f"Error fetching supported models: {e}")
            return self._get_fallback_models()
    
    def get_supported_models_sync(self, force_refresh: bool = False) -> List[str]:
        """Synchronous version of get_supported_models."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=10)
            if response.status_code == 200:
                models = response.json()
                self._models_cache = models
                self._models_cache_expiry = datetime.now()
                logger.info(f"Fetched {len(models)} supported models from Glama.ai")
                return models
            else:
                logger.error(f"Failed to fetch models: HTTP {response.status_code}")
                return self._get_fallback_models()
        except Exception as e:
            logger.error(f"Error fetching supported models: {e}")
            return self._get_fallback_models()
    
    def _get_fallback_models(self) -> List[str]:
        """Get fallback model list when API is unavailable."""
        if self._models_cache:
            logger.info("Using cached model list as fallback")
            return self._models_cache
        
        # Return the models currently configured in the system
        fallback_models = config.llm.available_models
        logger.info(f"Using configured model list as fallback: {len(fallback_models)} models")
        return fallback_models
    
    async def calculate_cost(
        self, 
        model: str, 
        messages: List[Dict[str, str]],
        use_cache: bool = True
    ) -> Optional[CostCalculation]:
        """
        Calculate cost for a conversation using Glama.ai API.
        
        Args:
            model: Model name (e.g., 'gpt-4o-mini')
            messages: List of message dictionaries with 'content' and 'role'
            use_cache: Whether to use cached cost data
            
        Returns:
            CostCalculation object or None if calculation failed
        """
        if not self.api_key:
            logger.warning("No Glama API key configured, using fallback calculation")
            return self._calculate_fallback_cost(model, messages)
        
        try:
            # Prepare the request payload
            payload = {
                "model": model,
                "messages": messages
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/calculate-chat-cost"
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_cost_response(data, model, messages)
                    else:
                        error_text = await response.text()
                        logger.error(f"Cost calculation failed: HTTP {response.status} - {error_text}")
                        return self._calculate_fallback_cost(model, messages)
                        
        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return self._calculate_fallback_cost(model, messages)
    
    def calculate_cost_sync(
        self, 
        model: str, 
        messages: List[Dict[str, str]],
        use_cache: bool = True
    ) -> Optional[CostCalculation]:
        """Synchronous version of calculate_cost."""
        if not self.api_key:
            logger.warning("No Glama API key configured, using fallback calculation")
            return self._calculate_fallback_cost(model, messages)
        
        try:
            payload = {
                "model": model,
                "messages": messages
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
            
            response = requests.post(
                f"{self.base_url}/calculate-chat-cost",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_cost_response(data, model, messages)
            else:
                logger.error(f"Cost calculation failed: HTTP {response.status_code} - {response.text}")
                return self._calculate_fallback_cost(model, messages)
                
        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return self._calculate_fallback_cost(model, messages)
    
    def _parse_cost_response(self, data: Dict[str, Any], model: str, messages: List[Dict[str, str]]) -> CostCalculation:
        """Parse the response from Glama.ai API."""
        total_cost = float(data.get("totalCost", 0.0))
        
        # Extract token counts from the response if available - ensure they're integers
        input_tokens = int(data.get("inputTokens", 0)) if data.get("inputTokens") is not None else 0
        output_tokens = int(data.get("outputTokens", 0)) if data.get("outputTokens") is not None else 0
        total_tokens = int(data.get("totalTokens", input_tokens + output_tokens)) if data.get("totalTokens") is not None else input_tokens + output_tokens
        
        # If token counts not provided, estimate them
        if input_tokens == 0 and output_tokens == 0:
            input_tokens = self._estimate_input_tokens(messages)
            # Assume output tokens is roughly 20% of input for estimation
            output_tokens = max(1, int(input_tokens * 0.2))
            total_tokens = input_tokens + output_tokens
        
        # Calculate cost breakdown if not provided - ensure they're floats
        input_cost = float(data.get("inputCost", 0.0)) if data.get("inputCost") is not None else 0.0
        output_cost = float(data.get("outputCost", 0.0)) if data.get("outputCost") is not None else 0.0
        
        if input_cost == 0.0 and output_cost == 0.0 and total_cost > 0:
            # Estimate breakdown (typically input:output ratio is about 3:1 for costs)
            input_cost = total_cost * 0.75
            output_cost = total_cost * 0.25
        
        return CostCalculation(
            total_cost=total_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            calculated_at=datetime.now()
        )
    
    def _estimate_input_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate token count for input messages."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # Rough estimation: 1 token ≈ 4 characters
        return max(1, total_chars // 4)
    
    def _calculate_fallback_cost(self, model: str, messages: List[Dict[str, str]]) -> CostCalculation:
        """Calculate cost using fallback static pricing when API is unavailable."""
        logger.debug(f"Using fallback cost calculation for model {model}")
        
        # Use the existing static costs from config
        cost_per_1k = config.llm.model_costs.get(model, 0.0001)
        
        # Estimate tokens
        input_tokens = self._estimate_input_tokens(messages)
        output_tokens = max(1, int(input_tokens * 0.2))  # Estimate output as 20% of input
        total_tokens = input_tokens + output_tokens
        
        # Calculate costs (assuming same rate for input and output for simplicity)
        total_cost = (total_tokens / 1000) * cost_per_1k
        input_cost = (input_tokens / 1000) * cost_per_1k
        output_cost = (output_tokens / 1000) * cost_per_1k
        
        return CostCalculation(
            total_cost=total_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            calculated_at=datetime.now()
        )
    
    def calculate_token_cost(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> Optional[CostCalculation]:
        """
        Calculate cost for known token counts.
        
        This is useful when you already have accurate token usage from the LLM provider.
        """
        # Create dummy messages for the API call to get accurate pricing
        messages = [
            {"role": "user", "content": "x" * (input_tokens * 4)},  # Rough approximation
            {"role": "assistant", "content": "x" * (output_tokens * 4)}
        ]
        
        # Use sync version for simplicity when we have token counts
        result = self.calculate_cost_sync(model, messages, use_cache=True)
        
        if result:
            # Override with actual token counts
            total_tokens = input_tokens + output_tokens
            
            # Recalculate costs based on actual tokens if we got a cost per token rate
            if result.total_tokens > 0:
                cost_per_token = result.total_cost / result.total_tokens
                total_cost = cost_per_token * total_tokens
                input_cost = cost_per_token * input_tokens
                output_cost = cost_per_token * output_tokens
            else:
                total_cost = result.total_cost
                input_cost = result.input_cost
                output_cost = result.output_cost
            
            return CostCalculation(
                total_cost=total_cost,
                input_cost=input_cost,
                output_cost=output_cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                model=model,
                calculated_at=datetime.now()
            )
        
        return None
    
    def clear_cache(self):
        """Clear all cached data."""
        self._models_cache = None
        self._models_cache_expiry = None
        self._cost_cache.clear()
        logger.info("Cleared all cost service caches")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cache status."""
        return {
            "models_cached": self._models_cache is not None,
            "models_cache_expiry": self._models_cache_expiry.isoformat() if self._models_cache_expiry else None,
            "cost_cache_entries": len(self._cost_cache),
            "api_key_configured": bool(self.api_key)
        }


# Global instance
_cost_service: Optional[CostService] = None


def get_cost_service() -> CostService:
    """Get or create the global cost service instance."""
    global _cost_service
    if _cost_service is None:
        _cost_service = CostService()
    return _cost_service


def calculate_cost_for_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Convenience function to calculate cost for known token counts.
    
    Returns the total cost as a float, or falls back to static calculation if API fails.
    """
    cost_service = get_cost_service()
    result = cost_service.calculate_token_cost(model, input_tokens, output_tokens)
    
    if result:
        return result.total_cost
    
    # Fallback to static calculation
    cost_per_1k = config.llm.model_costs.get(model, 0.0001)
    total_tokens = input_tokens + output_tokens
    return (total_tokens / 1000) * cost_per_1k


def get_model_cost_per_1k(model: str) -> float:
    """
    Get cost per 1K tokens for a model.
    
    This maintains compatibility with the existing get_model_cost function
    while potentially using dynamic pricing.
    """
    # For now, return static costs to maintain compatibility
    # TODO: Could be enhanced to fetch real-time pricing per token
    return config.llm.model_costs.get(model, 0.0001) 