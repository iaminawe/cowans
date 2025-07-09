# Icon Generation Test Guide

This guide documents the comprehensive test suite for the icon generation and sync workflow.

## Test Suite Overview

### 1. **Comprehensive Test Suite** (`icon-generation-test-suite.py`)
Full end-to-end testing of the icon generation system including:
- Test collection creation
- Single icon generation with various styles
- Bulk icon generation
- Error handling scenarios
- Shopify sync verification
- UI responsiveness testing

### 2. **Quick Test Script** (`quick-icon-test.py`)
Rapid testing for development and debugging:
- Single icon generation
- Batch processing
- Icon library retrieval
- Statistics checking

### 3. **UI Responsiveness Test** (`ui-responsiveness-test.py`)
Performance testing under load:
- Concurrent API calls
- WebSocket message delivery
- Simultaneous generation requests
- Error recovery testing
- Heavy load scenarios

## Prerequisites

1. **Backend API Running**
   ```bash
   cd web_dashboard/backend
   python app.py
   ```

2. **Frontend Running** (for WebSocket tests)
   ```bash
   cd frontend
   npm start
   ```

3. **Python Dependencies**
   ```bash
   pip install aiohttp asyncio websockets
   ```

4. **Environment Variables**
   Ensure your `.env` file contains:
   - `OPENAI_API_KEY`
   - `SHOPIFY_*` credentials

## Running the Tests

### Quick Test (Development)
```bash
# From frontend/tests directory
python quick-icon-test.py
```

Expected output:
```
🚀 Quick Icon Generation Tests
==================================================
✅ API is healthy

📈 Testing Generation Stats
--------------------------------------------------
✅ Generation Statistics:
  Total Generated: 15
  Total Failed: 2
  Active Batches: 0
  Cached Icons: 12
  Avg Generation Time: 3.45s

🎨 Testing Single Icon Generation
--------------------------------------------------
Generating icon for: Quick Test Electronics
Style: modern, Color: brand_colors
✅ Success! Generated in 3.21s
```

### Comprehensive Test Suite
```bash
# Run full test suite
python icon-generation-test-suite.py
```

This will:
1. Create 5 test collections
2. Generate icons with different styles
3. Test bulk generation
4. Verify error handling
5. Test Shopify sync
6. Generate detailed JSON report

### UI Responsiveness Test
```bash
# Test UI performance
python ui-responsiveness-test.py
```

Tests:
- API response times under load
- WebSocket message latency
- Concurrent request handling
- Error recovery speed
- Heavy load performance

## Test Scenarios

### 1. Single Icon Generation
Tests generation of individual icons with:
- Different styles (modern, minimalist, detailed, abstract, flat)
- Various color schemes (brand colors, monochrome, vibrant, pastel, natural)
- Custom elements specific to each category

### 2. Bulk Icon Generation
Tests batch processing:
- Multiple categories (5-10 at once)
- Progress tracking via WebSocket
- Concurrent generation handling
- Batch cancellation

### 3. Error Scenarios
- Empty category name
- Invalid style values
- Missing required parameters
- API timeout handling
- Rate limit recovery

### 4. Shopify Integration
- Collection image upload
- Image URL validation
- Alt text generation
- Sync status verification

### 5. Performance Metrics
- Response time percentiles (p50, p95, p99)
- WebSocket latency
- Concurrent request handling
- Memory usage under load

## Expected Results

### Success Criteria
- **Single Generation**: < 5 seconds per icon
- **Batch Processing**: Linear scaling with batch size
- **API Response**: < 200ms for status endpoints
- **WebSocket Latency**: < 100ms message delivery
- **Error Recovery**: < 2 seconds to recover
- **Concurrent Requests**: Handle 10+ simultaneous

### Common Issues

1. **OpenAI Rate Limits**
   - Solution: Add delays between requests
   - Use lower quality for testing

2. **WebSocket Connection Failed**
   - Ensure frontend is running
   - Check CORS configuration

3. **Shopify Sync Failures**
   - Verify API credentials
   - Check collection permissions

4. **Timeout Errors**
   - Increase timeout values
   - Check network connectivity

## Test Data Cleanup

After testing, clean up:

1. **Remove Test Collections**
   ```python
   # Use Shopify admin or API to delete collections starting with "Test"
   ```

2. **Clear Icon Cache**
   ```bash
   curl -X POST http://localhost:5001/api/icons/cache/clear
   ```

3. **Delete Test Images**
   ```bash
   rm -rf static/icons/test-*
   ```

## Continuous Testing

For CI/CD integration:

```yaml
# .github/workflows/test-icons.yml
name: Icon Generation Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install aiohttp asyncio websockets
      - name: Run quick tests
        run: python frontend/tests/quick-icon-test.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Monitoring Production

After deployment, monitor:

1. **Generation Success Rate**
   ```sql
   SELECT 
     COUNT(*) as total,
     SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
     AVG(generation_time) as avg_time
   FROM icon_generations
   WHERE created_at > NOW() - INTERVAL '24 hours';
   ```

2. **API Performance**
   - Use APM tools (DataDog, New Relic)
   - Monitor p95 response times
   - Track error rates

3. **User Experience**
   - Generation completion rate
   - Time to first icon
   - Batch job success rate

## Troubleshooting

### Debug Mode
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Errors

1. **"API is not healthy"**
   - Check backend is running
   - Verify port 5001 is available

2. **"WebSocket connection failed"**
   - Frontend must be running
   - Check WebSocket URL matches

3. **"Generation timeout"**
   - Increase timeout values
   - Check OpenAI API status

4. **"Batch failed"**
   - Check individual error messages
   - Verify all categories are valid

## Performance Optimization

1. **Caching**
   - Enable Redis for API responses
   - Cache generated prompts

2. **Parallel Processing**
   - Increase batch concurrency
   - Use connection pooling

3. **Image Optimization**
   - Compress generated images
   - Use CDN for delivery

4. **Database Queries**
   - Add indexes on category lookups
   - Batch database operations