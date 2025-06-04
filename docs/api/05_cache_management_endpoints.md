# Cache Management Endpoints Specification

## Overview

Cache management endpoints that integrate with the existing [`WebAppAdapter`](../../../src/youtube_analysis/adapters/webapp_adapter.py:20) cache methods to provide administrative control over analysis results, token usage tracking, and system performance optimization.

## Cache Router

### Base Configuration
```python
# Pseudocode: Cache router setup
router = APIRouter(prefix="/api/v1/cache", tags=["cache"])
```

## Data Models

### Request Models
```python
# Pseudocode: Cache request models
CLASS CacheStatsRequest(BaseModel):
    PROPERTY include_details: bool = Field(default=False, description="Include detailed cache statistics")
    PROPERTY video_id: Optional[str] = Field(default=None, description="Filter stats by video ID")

CLASS CacheClearRequest(BaseModel):
    PROPERTY cache_type: str = Field(..., description="Type of cache to clear")
    PROPERTY video_id: Optional[str] = Field(default=None, description="Specific video ID to clear")
    PROPERTY older_than_days: Optional[int] = Field(default=None, ge=1, description="Clear entries older than N days")
    
    @validator("cache_type")
    FUNCTION validate_cache_type(cls, v):
        valid_types = ["analysis", "token_usage", "transcript", "all"]
        IF v NOT IN valid_types:
            RAISE ValueError(f"Invalid cache type. Must be one of: {valid_types}")
        RETURN v

CLASS TokenUsageRequest(BaseModel):
    PROPERTY start_date: Optional[date] = Field(default=None, description="Start date for usage report")
    PROPERTY end_date: Optional[date] = Field(default=None, description="End date for usage report")
    PROPERTY group_by: str = Field(default="day", description="Grouping period")
    PROPERTY user_id: Optional[str] = Field(default=None, description="Filter by user ID")
    
    @validator("group_by")
    FUNCTION validate_group_by(cls, v):
        valid_groups = ["hour", "day", "week", "month"]
        IF v NOT IN valid_groups:
            RAISE ValueError(f"Invalid group_by. Must be one of: {valid_groups}")
        RETURN v
```

### Response Models
```python
# Pseudocode: Cache response models
CLASS CacheEntry(BaseModel):
    PROPERTY key: str
    PROPERTY video_id: str
    PROPERTY created_at: datetime
    PROPERTY last_accessed: datetime
    PROPERTY access_count: int
    PROPERTY size_bytes: int
    PROPERTY expires_at: Optional[datetime]

CLASS CacheStats(BaseModel):
    PROPERTY total_entries: int
    PROPERTY total_size_bytes: int
    PROPERTY hit_rate: float
    PROPERTY miss_rate: float
    PROPERTY oldest_entry: Optional[datetime]
    PROPERTY newest_entry: Optional[datetime]
    PROPERTY cache_type_breakdown: Dict[str, int]
    PROPERTY entries: Optional[List[CacheEntry]]

CLASS TokenUsageStats(BaseModel):
    PROPERTY period: str
    PROPERTY total_tokens: int
    PROPERTY input_tokens: int
    PROPERTY output_tokens: int
    PROPERTY cost_estimate: float
    PROPERTY request_count: int

CLASS TokenUsageReport(BaseModel):
    PROPERTY start_date: date
    PROPERTY end_date: date
    PROPERTY total_usage: TokenUsageStats
    PROPERTY usage_by_period: List[TokenUsageStats]
    PROPERTY usage_by_model: Dict[str, TokenUsageStats]
    PROPERTY top_videos: List[Dict[str, Any]]

CLASS CacheOperationResult(BaseModel):
    PROPERTY operation: str
    PROPERTY affected_entries: int
    PROPERTY freed_bytes: int
    PROPERTY execution_time: float
```

## Cache Statistics Endpoints

### GET /api/v1/cache/stats
```python
# Pseudocode: Get cache statistics
@router.get("/stats", response_model=SuccessResponse[CacheStats])
ASYNC FUNCTION get_cache_stats(
    include_details: bool = Query(False, description="Include detailed cache entries"),
    video_id: Optional[str] = Query(default=None, description="Filter by video ID"),
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[CacheStats]:
    """
    Get comprehensive cache statistics.
    
    Requires admin privileges.
    """
    TRY:
        webapp_adapter = get_webapp_adapter()
        cache_repo = get_cache_repository()
        
        # Get basic cache statistics
        total_entries = AWAIT cache_repo.count_entries(video_id=video_id)
        total_size = AWAIT cache_repo.get_total_size(video_id=video_id)
        
        # Calculate hit/miss rates from metrics
        metrics = AWAIT cache_repo.get_metrics()
        hit_rate = metrics.get("hit_rate", 0.0)
        miss_rate = 1.0 - hit_rate
        
        # Get date range
        oldest_entry = AWAIT cache_repo.get_oldest_entry_date(video_id=video_id)
        newest_entry = AWAIT cache_repo.get_newest_entry_date(video_id=video_id)
        
        # Get cache type breakdown
        type_breakdown = AWAIT cache_repo.get_type_breakdown(video_id=video_id)
        
        # Get detailed entries if requested
        entries = None
        IF include_details:
            cache_entries = AWAIT cache_repo.get_entries(
                video_id=video_id,
                limit=100  # Limit for performance
            )
            entries = [
                CacheEntry(
                    key=entry.key,
                    video_id=entry.video_id,
                    created_at=entry.created_at,
                    last_accessed=entry.last_accessed,
                    access_count=entry.access_count,
                    size_bytes=entry.size_bytes,
                    expires_at=entry.expires_at
                )
                FOR entry IN cache_entries
            ]
        
        stats = CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            oldest_entry=oldest_entry,
            newest_entry=newest_entry,
            cache_type_breakdown=type_breakdown,
            entries=entries
        )
        
        logger.info(f"Cache stats retrieved by admin {current_user.email}")
        
        RETURN SuccessResponse(data=stats)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve cache statistics")
```

### GET /api/v1/cache/token-usage
```python
# Pseudocode: Get token usage statistics
@router.get("/token-usage", response_model=SuccessResponse[TokenUsageReport])
ASYNC FUNCTION get_token_usage_stats(
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    group_by: str = Query(default="day", description="Grouping period"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[TokenUsageReport]:
    """
    Get detailed token usage statistics and cost analysis.
    
    Requires admin privileges.
    """
    TRY:
        # Set default date range if not provided
        IF NOT end_date:
            end_date = date.today()
        IF NOT start_date:
            start_date = end_date - timedelta(days=30)
        
        webapp_adapter = get_webapp_adapter()
        
        # Get token usage data from WebAppAdapter
        usage_data = AWAIT webapp_adapter.get_token_usage_stats(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            user_id=user_id
        )
        
        # Calculate total usage
        total_usage = TokenUsageStats(
            period="total",
            total_tokens=usage_data.get("total_tokens", 0),
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cost_estimate=usage_data.get("cost_estimate", 0.0),
            request_count=usage_data.get("request_count", 0)
        )
        
        # Transform period-based usage
        usage_by_period = [
            TokenUsageStats(
                period=period_data["period"],
                total_tokens=period_data["total_tokens"],
                input_tokens=period_data["input_tokens"],
                output_tokens=period_data["output_tokens"],
                cost_estimate=period_data["cost_estimate"],
                request_count=period_data["request_count"]
            )
            FOR period_data IN usage_data.get("by_period", [])
        ]
        
        # Transform model-based usage
        usage_by_model = {
            model: TokenUsageStats(
                period="total",
                total_tokens=model_data["total_tokens"],
                input_tokens=model_data["input_tokens"],
                output_tokens=model_data["output_tokens"],
                cost_estimate=model_data["cost_estimate"],
                request_count=model_data["request_count"]
            )
            FOR model, model_data IN usage_data.get("by_model", {}).items()
        }
        
        report = TokenUsageReport(
            start_date=start_date,
            end_date=end_date,
            total_usage=total_usage,
            usage_by_period=usage_by_period,
            usage_by_model=usage_by_model,
            top_videos=usage_data.get("top_videos", [])
        )
        
        logger.info(f"Token usage report generated by admin {current_user.email}")
        
        RETURN SuccessResponse(data=report)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting token usage stats: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve token usage statistics")
```

## Cache Management Endpoints

### POST /api/v1/cache/clear
```python
# Pseudocode: Clear cache entries
@router.post("/clear", response_model=SuccessResponse[CacheOperationResult])
ASYNC FUNCTION clear_cache(
    request: CacheClearRequest,
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[CacheOperationResult]:
    """
    Clear cache entries based on specified criteria.
    
    Requires admin privileges.
    """
    TRY:
        start_time = time.time()
        webapp_adapter = get_webapp_adapter()
        
        # Determine clear operation based on cache type
        IF request.cache_type == "analysis":
            result = AWAIT webapp_adapter.clear_analysis_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
        
        ELIF request.cache_type == "token_usage":
            result = AWAIT webapp_adapter.clear_token_usage_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
        
        ELIF request.cache_type == "transcript":
            result = AWAIT webapp_adapter.clear_transcript_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
        
        ELIF request.cache_type == "all":
            # Clear all cache types
            analysis_result = AWAIT webapp_adapter.clear_analysis_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
            token_result = AWAIT webapp_adapter.clear_token_usage_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
            transcript_result = AWAIT webapp_adapter.clear_transcript_cache(
                video_id=request.video_id,
                older_than_days=request.older_than_days
            )
            
            result = {
                "affected_entries": (
                    analysis_result.get("affected_entries", 0) +
                    token_result.get("affected_entries", 0) +
                    transcript_result.get("affected_entries", 0)
                ),
                "freed_bytes": (
                    analysis_result.get("freed_bytes", 0) +
                    token_result.get("freed_bytes", 0) +
                    transcript_result.get("freed_bytes", 0)
                )
            }
        
        execution_time = time.time() - start_time
        
        operation_result = CacheOperationResult(
            operation=f"clear_{request.cache_type}",
            affected_entries=result.get("affected_entries", 0),
            freed_bytes=result.get("freed_bytes", 0),
            execution_time=execution_time
        )
        
        logger.info(
            f"Cache cleared by admin {current_user.email}: "
            f"{operation_result.affected_entries} entries, "
            f"{operation_result.freed_bytes} bytes freed"
        )
        
        RETURN SuccessResponse(data=operation_result)
        
    EXCEPT Exception as e:
        logger.error(f"Error clearing cache: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to clear cache")
```

### POST /api/v1/cache/optimize
```python
# Pseudocode: Optimize cache performance
@router.post("/optimize", response_model=SuccessResponse[CacheOperationResult])
ASYNC FUNCTION optimize_cache(
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[CacheOperationResult]:
    """
    Optimize cache by removing expired entries and compacting storage.
    
    Requires admin privileges.
    """
    TRY:
        start_time = time.time()
        webapp_adapter = get_webapp_adapter()
        
        # Run cache optimization
        result = AWAIT webapp_adapter.optimize_cache()
        
        execution_time = time.time() - start_time
        
        operation_result = CacheOperationResult(
            operation="optimize",
            affected_entries=result.get("cleaned_entries", 0),
            freed_bytes=result.get("freed_bytes", 0),
            execution_time=execution_time
        )
        
        logger.info(
            f"Cache optimized by admin {current_user.email}: "
            f"{operation_result.affected_entries} entries cleaned, "
            f"{operation_result.freed_bytes} bytes freed"
        )
        
        RETURN SuccessResponse(data=operation_result)
        
    EXCEPT Exception as e:
        logger.error(f"Error optimizing cache: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to optimize cache")
```

### GET /api/v1/cache/health
```python
# Pseudocode: Cache health check
@router.get("/health", response_model=SuccessResponse[Dict[str, Any]])
ASYNC FUNCTION get_cache_health(
    current_user: UserProfile = Depends(get_current_user_admin)
) -> SuccessResponse[Dict[str, Any]]:
    """
    Get cache health status and performance metrics.
    
    Requires admin privileges.
    """
    TRY:
        webapp_adapter = get_webapp_adapter()
        cache_repo = get_cache_repository()
        
        # Get cache health metrics
        health_data = AWAIT cache_repo.get_health_metrics()
        
        # Check cache connectivity
        connectivity_ok = AWAIT cache_repo.test_connection()
        
        # Get memory usage if available
        memory_usage = AWAIT cache_repo.get_memory_usage()
        
        # Calculate cache efficiency
        hit_rate = health_data.get("hit_rate", 0.0)
        efficiency_status = "excellent" IF hit_rate > 0.8 ELSE (
            "good" IF hit_rate > 0.6 ELSE (
                "fair" IF hit_rate > 0.4 ELSE "poor"
            )
        )
        
        health_status = {
            "status": "healthy" IF connectivity_ok ELSE "unhealthy",
            "connectivity": connectivity_ok,
            "hit_rate": hit_rate,
            "efficiency": efficiency_status,
            "memory_usage": memory_usage,
            "total_entries": health_data.get("total_entries", 0),
            "expired_entries": health_data.get("expired_entries", 0),
            "last_cleanup": health_data.get("last_cleanup"),
            "uptime": health_data.get("uptime", 0)
        }
        
        RETURN SuccessResponse(data=health_status)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting cache health: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve cache health status")
```

## User Cache Endpoints

### GET /api/v1/cache/my-usage
```python
# Pseudocode: Get user's cache usage
@router.get("/my-usage", response_model=SuccessResponse[Dict[str, Any]])
ASYNC FUNCTION get_my_cache_usage(
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[Dict[str, Any]]:
    """
    Get current user's cache usage statistics.
    """
    TRY:
        webapp_adapter = get_webapp_adapter()
        
        # Get user's cache usage
        usage_data = AWAIT webapp_adapter.get_user_cache_usage(current_user.id)
        
        user_usage = {
            "user_id": current_user.id,
            "analysis_count": usage_data.get("analysis_count", 0),
            "cache_hits": usage_data.get("cache_hits", 0),
            "cache_misses": usage_data.get("cache_misses", 0),
            "total_token_usage": usage_data.get("total_token_usage", 0),
            "estimated_cost": usage_data.get("estimated_cost", 0.0),
            "last_activity": usage_data.get("last_activity")
        }
        
        RETURN SuccessResponse(data=user_usage)
        
    EXCEPT Exception as e:
        logger.error(f"Error getting user cache usage: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve cache usage")
```

### DELETE /api/v1/cache/my-data
```python
# Pseudocode: Clear user's cache data
@router.delete("/my-data", response_model=SuccessResponse[CacheOperationResult])
ASYNC FUNCTION clear_my_cache_data(
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[CacheOperationResult]:
    """
    Clear all cache data associated with the current user.
    """
    TRY:
        start_time = time.time()
        webapp_adapter = get_webapp_adapter()
        
        # Clear user's cache data
        result = AWAIT webapp_adapter.clear_user_cache_data(current_user.id)
        
        execution_time = time.time() - start_time
        
        operation_result = CacheOperationResult(
            operation="clear_user_data",
            affected_entries=result.get("affected_entries", 0),
            freed_bytes=result.get("freed_bytes", 0),
            execution_time=execution_time
        )
        
        logger.info(f"User cache data cleared for {current_user.email}")
        
        RETURN SuccessResponse(data=operation_result)
        
    EXCEPT Exception as e:
        logger.error(f"Error clearing user cache data: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to clear cache data")
```

## TDD Test Anchors

### Cache Statistics Tests
```python
# Test anchor: Cache stats retrieval
TEST test_get_cache_stats():
    WITH TestClient(app) AS client:
        # Login as admin
        admin_token = get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = client.get("/api/v1/cache/stats", headers=headers)
        ASSERT response.status_code == 200
        ASSERT "total_entries" IN response.json()["data"]
        ASSERT "hit_rate" IN response.json()["data"]

# Test anchor: Token usage report
TEST test_token_usage_report():
    WITH TestClient(app) AS client:
        admin_token = get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = client.get("/api/v1/cache/token-usage", headers=headers)
        ASSERT response.status_code == 200
        ASSERT "total_usage" IN response.json()["data"]
        ASSERT "usage_by_period" IN response.json()["data"]

# Test anchor: Cache clearing
TEST test_clear_cache():
    WITH TestClient(app) AS client:
        admin_token = get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = client.post("/api/v1/cache/clear", 
            json={"cache_type": "analysis"},
            headers=headers
        )
        ASSERT response.status_code == 200
        ASSERT "affected_entries" IN response.json()["data"]

# Test anchor: User cache usage
TEST test_user_cache_usage():
    WITH TestClient(app) AS client:
        user_token = get_user_token()
        headers = {"Authorization": f"Bearer {user_token}"}
        
        response = client.get("/api/v1/cache/my-usage", headers=headers)
        ASSERT response.status_code == 200
        ASSERT "analysis_count" IN response.json()["data"]

# Test anchor: Admin authorization
TEST test_admin_required():
    WITH TestClient(app) AS client:
        user_token = get_user_token()  # Regular user token
        headers = {"Authorization": f"Bearer {user_token}"}
        
        response = client.get("/api/v1/cache/stats", headers=headers)
        ASSERT response.status_code == 403  # Forbidden
```

This specification provides comprehensive cache management capabilities that integrate with the existing WebAppAdapter while offering both administrative control and user-specific cache operations.