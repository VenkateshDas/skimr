# Enhanced Token Usage Tracking Implementation

## Overview

This document describes the comprehensive token usage tracking system implemented for the YouTube Analysis WebApp. The system tracks token consumption across all operations and provides detailed breakdowns for analysis, content generation, and chat interactions.

## Key Features

### 1. **Cumulative Token Tracking**
- Tracks total token usage across all operations in a session
- Updates in real-time as new operations are performed
- Displays overall metrics: Total, Prompt, and Completion tokens

### 2. **Detailed Breakdown by Operation Type**
- **Initial Analysis**: Token usage from the first video analysis
- **Additional Content Generation**: Token usage for each content type (Action Plan, Blog Post, LinkedIn Post, X Tweet)
- **Chat Interactions**: Cumulative token usage from all chat messages with message count

### 3. **Cost Estimation**
- Provides rough cost estimates based on current model pricing
- Supports multiple models: GPT-4o-mini, Gemini-2.0-flash, Gemini-2.0-flash-lite
- Updates cost estimates in real-time

### 4. **Persistent Session Tracking**
- Token usage persists throughout the session
- Properly resets when starting a new analysis
- Maintains separate tracking for different operation types

## Implementation Details

### Session Manager Enhancements (`src/youtube_analysis/ui/session_manager.py`)

#### New Methods Added:
- `initialize_token_tracking()`: Sets up token tracking data structures
- `add_token_usage(operation_type, token_usage, operation_name)`: Adds token usage for specific operations
- `get_cumulative_token_usage()`: Returns total token usage across all operations
- `get_token_usage_breakdown()`: Returns detailed breakdown by operation type
- `reset_token_tracking()`: Resets all token tracking for new analysis
- `_recalculate_cumulative_usage()`: Internal method to update cumulative totals

#### Data Structure:
```python
{
    "cumulative_token_usage": {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0
    },
    "token_usage_breakdown": {
        "initial_analysis": None,
        "additional_content": {
            "analyze_and_plan_content": {...},
            "write_blog_post": {...},
            "write_linkedin_post": {...},
            "write_tweet": {...}
        },
        "chat": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "message_count": 0
        }
    }
}
```

### Service Layer Updates

#### Content Service (`src/youtube_analysis/services/content_service.py`)
- Modified `generate_single_content()` to return tuple: `(content, token_usage_dict)`
- Extracts token usage from CrewAI results
- Updates cached analysis results with token usage information

#### Chat Service (`src/youtube_analysis/services/chat_service.py`)
- Modified `stream_response()` to return tuple: `(chunk, token_usage_dict)`
- Estimates token usage for chat interactions (1 token ≈ 4 characters)
- Provides final token usage after streaming completes
- Maintains backward compatibility with `stream_response_original()`

### WebApp Adapter Updates (`src/youtube_analysis/adapters/webapp_adapter.py`)

#### Enhanced Methods:
- `generate_additional_content()`: Now returns `(content, error, token_usage)`
- `get_chat_response_stream()`: Now yields `(chunk, token_usage)` tuples
- Maintains backward compatibility with original methods

### Main WebApp Updates (`youtube_analysis_webapp.py`)

#### Enhanced Token Usage Display:
- **Overall Token Usage**: Prominent display of cumulative metrics
- **Detailed Breakdown**: Expandable section with per-operation breakdowns
- **Cost Estimation**: Real-time cost estimates based on current model
- **Usage Summary**: Model information and estimated costs

#### Event Handler Updates:
- `_handle_generate_additional_content()`: Tracks token usage from content generation
- `_process_chat_ai_response()`: Tracks token usage from chat interactions
- Automatic token tracking integration with session manager

## Usage Examples

### Tracking Additional Content Generation
```python
# In _handle_generate_additional_content
content, error, token_usage = await self.webapp_adapter.generate_additional_content(...)
if token_usage:
    self.session_manager.add_token_usage("additional_content", token_usage, task_key)
```

### Tracking Chat Interactions
```python
# In _process_chat_ai_response
async for chunk, token_usage in self.webapp_adapter.get_chat_response_stream(...):
    if token_usage:
        self.session_manager.add_token_usage("chat", token_usage)
```

### Displaying Token Usage
```python
# Get current usage
cumulative = self.session_manager.get_cumulative_token_usage()
breakdown = self.session_manager.get_token_usage_breakdown()

# Display metrics
st.metric("Total Tokens", f"{cumulative['total_tokens']:,}")
```

## UI Components

### Main Token Usage Section
- Displays overall token consumption prominently
- Shows Total, Prompt, and Completion tokens
- Updates automatically after each operation

### Breakdown Expander
- **Initial Analysis**: Shows tokens used for first video analysis
- **Additional Content Generation**: Shows tokens for each content type generated
- **Chat Interactions**: Shows cumulative chat tokens and message count
- **Usage Summary**: Model info and cost estimation

### Cost Estimation
- Rough estimates based on model pricing
- Supports multiple models with different rates
- Updates in real-time as tokens are consumed

## Benefits

1. **Transparency**: Users can see exactly how many tokens each operation consumes
2. **Cost Awareness**: Real-time cost estimates help users understand usage costs
3. **Optimization**: Detailed breakdowns help identify high-token operations
4. **Session Management**: Proper tracking across the entire user session
5. **Scalability**: Easy to add new operation types for token tracking

## Future Enhancements

1. **Exact Token Counting**: Replace estimation with actual token counting from LLM APIs
2. **Historical Tracking**: Store token usage across sessions for registered users
3. **Usage Limits**: Implement token-based usage limits for different user tiers
4. **Advanced Analytics**: Provide insights on token usage patterns
5. **Export Functionality**: Allow users to export token usage reports

## Technical Notes

- Token estimation for chat uses 1 token ≈ 4 characters approximation
- Cost estimates are rough and may not reflect exact API pricing
- Token tracking is session-based and resets with new analysis
- All token usage is tracked in session state for real-time updates
- Backward compatibility is maintained for existing functionality 