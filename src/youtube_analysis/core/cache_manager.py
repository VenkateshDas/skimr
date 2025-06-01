"""Unified cache management for YouTube analysis."""

import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

from ..utils.logging import get_logger

logger = get_logger("cache_manager")

@dataclass
class CacheConfig:
    """Cache configuration settings."""
    cache_dir: str
    expiry_days: int = 7
    max_size_mb: int = 500
    hash_algorithm: str = "sha256"

class CacheManager:
    """Unified cache manager for all caching operations."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig(
            cache_dir=os.environ.get("CACHE_DIR", "analysis_cache"),
            expiry_days=int(os.environ.get("CACHE_EXPIRY_DAYS", "7")),
            max_size_mb=int(os.environ.get("CACHE_MAX_SIZE_MB", "500"))
        )
        self._setup_cache_directory()
    
    def _setup_cache_directory(self) -> None:
        """Setup cache directories."""
        Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.cache_dir, "analysis").mkdir(exist_ok=True)
        Path(self.config.cache_dir, "transcripts").mkdir(exist_ok=True)
        Path(self.config.cache_dir, "highlights").mkdir(exist_ok=True)
        Path(self.config.cache_dir, "video_data").mkdir(exist_ok=True)
    
    def _get_cache_key(self, data: Union[str, Dict[str, Any]]) -> str:
        """Generate cache key using configured hash algorithm."""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        
        if self.config.hash_algorithm == "md5":
            return hashlib.md5(data.encode()).hexdigest()
        else:
            return hashlib.sha256(data.encode()).hexdigest()
    
    def _get_cache_path(self, cache_type: str, key: str) -> Path:
        """Get cache file path."""
        return Path(self.config.cache_dir, cache_type, f"{key}.json")
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False
        
        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = datetime.now() - timedelta(days=self.config.expiry_days)
        return file_time > expiry_time
    
    def get(self, cache_type: str, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data."""
        cache_key = self._get_cache_key(key)
        cache_path = self._get_cache_path(cache_type, cache_key)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Cache hit for {cache_type}:{key[:20]}...")
            return data
        except Exception as e:
            logger.warning(f"Error reading cache {cache_path}: {e}")
            return None
    
    def set(self, cache_type: str, key: str, data: Any) -> bool:
        """Set cached data."""
        cache_key = self._get_cache_key(key)
        cache_path = self._get_cache_path(cache_type, cache_key)
        
        try:
            # Ensure the directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Ensure data is a dictionary or convert it to one
            if isinstance(data, str):
                try:
                    # Try to parse as JSON
                    parsed_data = json.loads(data)
                    if isinstance(parsed_data, dict):
                        data = parsed_data
                    else:
                        data = {"value": parsed_data}
                except json.JSONDecodeError:
                    # Not valid JSON, wrap as value
                    data = {"value": data}
            elif not isinstance(data, dict):
                # Handle non-dictionary data by wrapping it
                data = {"value": str(data)}
            
            # Remove non-serializable objects
            clean_data = self._clean_data_for_serialization(data)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Cached {cache_type}:{key[:20]}...")
            return True
        except Exception as e:
            logger.error(f"Error writing cache {cache_path}: {e}")
            return False
    
    def _clean_data_for_serialization(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-serializable objects from data."""
        clean_data = {}
        for key, value in data.items():
            if key in ['agent', 'vectorstore', 'chat_details']:
                continue
            try:
                json.dumps(value)
                clean_data[key] = value
            except (TypeError, ValueError):
                logger.debug(f"Skipping non-serializable field: {key}")
        return clean_data
    
    def delete(self, cache_type: str, key: str) -> bool:
        """Delete cached data."""
        cache_key = self._get_cache_key(key)
        cache_path = self._get_cache_path(cache_type, cache_key)
        
        try:
            if cache_path.exists():
                cache_path.unlink()
                logger.debug(f"Deleted cache {cache_type}:{key[:20]}...")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache {cache_path}: {e}")
            return False
    
    def clear(self, cache_type: Optional[str] = None) -> int:
        """Clear cache files."""
        count = 0
        if cache_type:
            cache_dir = Path(self.config.cache_dir, cache_type)
            if cache_dir.exists():
                for cache_file in cache_dir.glob("*.json"):
                    try:
                        cache_file.unlink()
                        count += 1
                    except Exception as e:
                        logger.error(f"Error deleting {cache_file}: {e}")
        else:
            for subdir in ["analysis", "transcripts", "highlights"]:
                count += self.clear(subdir)
        
        logger.info(f"Cleared {count} cache files")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {"total_files": 0, "total_size_mb": 0, "by_type": {}}
        
        for cache_type in ["analysis", "transcripts", "highlights"]:
            cache_dir = Path(self.config.cache_dir, cache_type)
            if cache_dir.exists():
                files = list(cache_dir.glob("*.json"))
                size_bytes = sum(f.stat().st_size for f in files)
                stats["by_type"][cache_type] = {
                    "files": len(files),
                    "size_mb": round(size_bytes / (1024 * 1024), 2)
                }
                stats["total_files"] += len(files)
                stats["total_size_mb"] += stats["by_type"][cache_type]["size_mb"]
        
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats