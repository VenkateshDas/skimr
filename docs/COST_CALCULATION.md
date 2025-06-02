# Dynamic LLM Cost Calculation System

This document describes the new dynamic cost calculation system that uses the [Glama.ai Cost Calculator API](https://dev.to/punkpeye/api-for-calculating-openai-and-other-llm-costs-28i2) to provide real-time, accurate cost estimates for LLM usage.

## Overview

The system replaces static, environment variable-based cost estimates with dynamic, API-based calculations that:

- ✅ Use real-time pricing data from 30+ LLM providers
- ✅ Support accurate token counting and cost breakdown
- ✅ Provide input/output token cost separation  
- ✅ Include fallback mechanisms for reliability
- ✅ Cache results to minimize API calls
- ✅ Maintain backward compatibility

## Architecture

### Cost Service (`src/youtube_analysis/services/cost_service.py`)

The core component that handles:
- **API Integration**: Direct communication with Glama.ai API
- **Caching**: Smart caching to reduce API calls and improve performance  
- **Fallback Logic**: Graceful degradation to static costs when API is unavailable
- **Token Estimation**: Accurate token counting for cost calculations

### Key Components

```python
from youtube_analysis.services.cost_service import get_cost_service, calculate_cost_for_tokens

# Get the global cost service instance
cost_service = get_cost_service()

# Calculate cost for known token counts
total_cost = calculate_cost_for_tokens("gpt-4o-mini", input_tokens=1000, output_tokens=200)
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Glama.ai API key (get from https://glama.ai/settings/api-keys)
GLAMA_API_KEY=your_glama_api_key_here

# Enable/disable dynamic cost calculation
ENABLE_DYNAMIC_COSTS=true
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GLAMA_API_KEY` | None | Your Glama.ai API key |
| `ENABLE_DYNAMIC_COSTS` | true | Whether to use dynamic costs |

## Getting Started

### 1. Get Your API Key

1. Sign up at [glama.ai](https://glama.ai)
2. Go to [API Keys Settings](https://glama.ai/settings/api-keys)
3. Generate a new API key
4. Add it to your `.env` file

### 2. Update Your Configuration

```env
GLAMA_API_KEY=your_actual_api_key_here
ENABLE_DYNAMIC_COSTS=true
```

### 3. Test the Integration

Run the test script to verify everything works:

```bash
python scripts/test_cost_api.py
```

## Usage Examples

### Basic Cost Calculation

```python
from youtube_analysis.services.cost_service import CostService

cost_service = CostService()

# Calculate cost for a conversation
messages = [
    {"role": "user", "content": "Hello, how are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you!"}
]

result = await cost_service.calculate_cost("gpt-4o-mini", messages)
print(f"Total cost: ${result.total_cost:.6f}")
```

### Token-Based Calculation

```python
from youtube_analysis.services.cost_service import calculate_cost_for_tokens

# Calculate cost for known token counts
cost = calculate_cost_for_tokens("gpt-4o", input_tokens=1000, output_tokens=200)
print(f"Estimated cost: ${cost:.6f}")
```

### Batch Model Information

```python
cost_service = CostService()

# Get all supported models
models = await cost_service.get_supported_models()
print(f"Supported models: {len(models)}")
```

## Integration Points

### WebApp Integration

The cost calculation is automatically integrated into:

- **Token Usage Display**: Shows dynamic vs static cost comparison
- **Analysis Results**: Real-time cost tracking during analysis
- **Chat Interface**: Accurate cost tracking for chat interactions

### CLI Integration  

The command-line interface shows:
- Dynamic cost calculations in the summary
- Cost source indication (dynamic/static/fallback)
- Improved precision (6 decimal places)

## API Response Format

The Glama.ai API returns cost data in this format:

```json
{
  "totalCost": 0.000123,
  "inputTokens": 25,
  "outputTokens": 15, 
  "totalTokens": 40,
  "inputCost": 0.000075,
  "outputCost": 0.000048
}
```

## Caching Strategy

The cost service implements intelligent caching:

- **Model List Cache**: 24 hours (models don't change frequently)
- **Cost Cache**: 1 hour (prices may update periodically)
- **Fallback Cache**: Persistent until app restart

## Error Handling & Fallback

The system gracefully handles various error conditions:

### API Unavailable
```
API Error → Static Cost Calculation → Continue Operation
```

### Missing API Key
```
No API Key → Static Cost Calculation → Log Warning
```

### Invalid Model
```
Unknown Model → Fallback Cost (0.0001) → Continue Operation
```

### Network Issues
```
Network Error → Cached Data → Static Fallback → Continue Operation
```

## Performance Considerations

### Optimization Features

- **Async/Await Support**: Non-blocking API calls
- **Connection Pooling**: Efficient HTTP connections
- **Smart Caching**: Reduces API calls by 90%+
- **Batch Processing**: Multiple calculations in single request

### Monitoring

Track cost service performance:

```python
cost_service = get_cost_service()
cache_info = cost_service.get_cache_info()

print(f"API key configured: {cache_info['api_key_configured']}")
print(f"Models cached: {cache_info['models_cached']}")
print(f"Cost cache entries: {cache_info['cost_cache_entries']}")
```

## Supported Models

The API supports 30+ providers including:

- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
- **Anthropic**: claude-3-5-sonnet, claude-3-haiku, claude-3-opus
- **Google**: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
- **Meta**: llama-3.1-405b, llama-3.1-70b, llama-3.1-8b
- **OpenRouter**: Many additional models
- **Replicate**: Various open-source models

For a complete list, run:

```bash
python scripts/test_cost_api.py
```

## Troubleshooting

### Common Issues

#### 1. API Key Not Working
```bash
# Check if key is set
echo $GLAMA_API_KEY

# Test with curl
curl -X GET https://glama.ai/api/cost-calculator/models \
  -H "x-api-key: $GLAMA_API_KEY"
```

#### 2. Models Not Loading
- Check internet connection
- Verify API key is valid
- Check application logs for error details

#### 3. Costs Seem Wrong
- Run comparison test: `python scripts/test_cost_api.py`
- Check if using cached vs real-time data
- Verify token counts are accurate

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("cost_service").setLevel(logging.DEBUG)
```

## Migration Guide

### From Static Costs

If you're migrating from static costs:

1. **Keep existing config**: Static costs remain as fallback
2. **Add API key**: Get key from Glama.ai  
3. **Enable feature**: Set `ENABLE_DYNAMIC_COSTS=true`
4. **Test thoroughly**: Run test suite to verify
5. **Monitor usage**: Check logs for any issues

### Rollback Plan

To rollback to static costs:

```env
ENABLE_DYNAMIC_COSTS=false
```

Or remove the API key:

```env
# GLAMA_API_KEY=your_key_here
```

## Future Enhancements

Planned improvements:

- **Real-time Model Discovery**: Auto-update available models
- **Cost Alerting**: Notifications when costs exceed thresholds  
- **Usage Analytics**: Detailed cost tracking and reporting
- **Budget Controls**: Automatic limits and warnings
- **Provider Comparison**: Side-by-side cost comparisons

## API Limits

The Glama.ai API has generous limits:

- **Free Tier**: Suitable for most use cases
- **No Rate Limits**: For reasonable usage
- **High Availability**: 99.9% uptime
- **Global CDN**: Fast response times worldwide

## Security

### API Key Protection

- Store API keys in environment variables
- Never commit keys to version control
- Use different keys for different environments
- Rotate keys periodically

### Data Privacy

- API calls include only necessary message content
- No sensitive data is cached permanently
- All communication is encrypted (HTTPS)
- Glama.ai doesn't store your data

## Support

For issues related to:

- **Cost Service**: Check application logs and GitHub issues
- **Glama.ai API**: Contact frank@glama.ai
- **Integration**: Use the test script for debugging

## Contributing

To contribute to the cost calculation system:

1. **Test Changes**: Run `python scripts/test_cost_api.py`
2. **Add Tests**: Include tests for new functionality  
3. **Update Docs**: Keep documentation current
4. **Maintain Compatibility**: Ensure fallback mechanisms work

---

*This system was implemented based on the [Glama.ai Cost Calculator API](https://dev.to/punkpeye/api-for-calculating-openai-and-other-llm-costs-28i2) blog post to provide accurate, real-time LLM cost calculations.* 