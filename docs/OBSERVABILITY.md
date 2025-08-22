# Observability Guide

## Overview

The AI Quality Kit provides comprehensive observability features including API logging, live quality evaluation, and response caching. This guide explains how to enable and use these production-grade features.

## Features

### 1. API Response Logging
- **Request/Response Tracking**: Log every API call with metadata
- **Performance Monitoring**: Track response times and latency
- **Error Tracking**: Capture and log errors with context
- **Source Identification**: Distinguish between cache hits and live responses

### 2. Live Quality Evaluation
- **Real-time Metrics**: Ragas faithfulness and context recall scores
- **Guardrails Validation**: JSON schema compliance checking
- **Safety Scanning**: Content safety violation detection
- **Automatic Logging**: Quality metrics stored in Snowflake

### 3. Response Caching
- **Query-based Caching**: Cache responses by normalized query hash
- **Version-aware**: Context versioning for cache invalidation
- **TTL Management**: Configurable cache expiration
- **Performance Boost**: Significantly faster responses for repeated queries

## Configuration

### Environment Variables

```env
# Enable/Disable Features
ENABLE_API_LOGGING=false      # Enable API request/response logging
ENABLE_LIVE_EVAL=false        # Enable live quality evaluation
CACHE_ENABLED=true            # Enable response caching
CACHE_TTL_SECONDS=86400      # Cache TTL in seconds (24 hours)
CONTEXT_VERSION=v1            # Context version for cache invalidation
```

### Snowflake Tables

Create the following tables in your Snowflake schema:

```sql
-- Request/response logging (one row per API call)
CREATE TABLE IF NOT EXISTS LLM_API_LOGS (
  ID STRING DEFAULT UUID_STRING() PRIMARY KEY,
  RUN_ID STRING,
  REQUEST_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  RESPONSE_AT TIMESTAMP_NTZ,
  PROVIDER STRING,
  MODEL_NAME STRING,
  QUERY_HASH STRING,
  QUERY_TEXT STRING,
  CONTEXT ARRAY,
  ANSWER STRING,
  SOURCE STRING,              -- 'live' | 'cache'
  LATENCY_MS NUMBER,
  STATUS STRING,              -- 'ok' | 'error'
  ERROR_MSG STRING
);

-- Live evaluation results (one row per metric per API call)
CREATE TABLE IF NOT EXISTS LLM_API_EVAL_RESULTS (
  LOG_ID STRING,              -- foreign key to LLM_API_LOGS.ID
  METRIC_GROUP STRING,        -- 'ragas' | 'guardrails' | 'safety'
  METRIC_NAME STRING,         -- e.g., 'faithfulness'
  METRIC_VALUE FLOAT,
  EXTRA JSON,
  RECORDED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Response cache (normalized by query hash and context version)
CREATE TABLE IF NOT EXISTS LLM_RESPONSE_CACHE (
  QUERY_HASH STRING,
  CONTEXT_VERSION STRING,
  ANSWER STRING,
  CONTEXT ARRAY,
  CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  EXPIRES_AT TIMESTAMP_NTZ
);
```

## How to Enable

### Step 1: Create Snowflake Tables
Run the DDL statements above in your Snowflake schema.

### Step 2: Configure Environment
Set the following in your `.env` file:

```env
# Enable features
ENABLE_API_LOGGING=true
ENABLE_LIVE_EVAL=true
CACHE_ENABLED=true

# Configure caching
CACHE_TTL_SECONDS=86400
CONTEXT_VERSION=v1

# Ensure Snowflake credentials are set
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=your_role
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
```

### Step 3: Start Service
Start the RAG service:

```bash
uvicorn apps.rag_service.main:app --reload --port 8000
```

### Step 4: Test Features
Make API calls to test the features:

```bash
# First call - should miss cache and log live response
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is data quality validation?"}'

# Second call - should hit cache and log cache response
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is data quality validation?"}'
```

## Monitoring and Analysis

### Query Snowflake Tables

#### API Logs
```sql
-- Recent API calls
SELECT 
  REQUEST_AT,
  QUERY_TEXT,
  SOURCE,
  LATENCY_MS,
  STATUS
FROM LLM_API_LOGS 
ORDER BY REQUEST_AT DESC
LIMIT 10;

-- Performance analysis
SELECT 
  SOURCE,
  AVG(LATENCY_MS) as avg_latency,
  COUNT(*) as call_count
FROM LLM_API_LOGS 
WHERE STATUS = 'ok'
GROUP BY SOURCE;
```

#### Quality Metrics
```sql
-- Recent quality scores
SELECT 
  er.RECORDED_AT,
  al.QUERY_TEXT,
  er.METRIC_GROUP,
  er.METRIC_NAME,
  er.METRIC_VALUE
FROM LLM_API_EVAL_RESULTS er
JOIN LLM_API_LOGS al ON er.LOG_ID = al.ID
ORDER BY er.RECORDED_AT DESC
LIMIT 20;

-- Quality trends
SELECT 
  DATE_TRUNC('hour', er.RECORDED_AT) as hour,
  er.METRIC_NAME,
  AVG(er.METRIC_VALUE) as avg_score
FROM LLM_API_EVAL_RESULTS er
WHERE er.METRIC_GROUP = 'ragas'
GROUP BY hour, er.METRIC_NAME
ORDER BY hour DESC;
```

#### Cache Performance
```sql
-- Cache hit rates
SELECT 
  DATE_TRUNC('hour', al.REQUEST_AT) as hour,
  al.SOURCE,
  COUNT(*) as call_count
FROM LLM_API_LOGS al
GROUP BY hour, al.SOURCE
ORDER BY hour DESC;

-- Cache efficiency
SELECT 
  SOURCE,
  COUNT(*) as total_calls,
  AVG(LATENCY_MS) as avg_latency_ms
FROM LLM_API_LOGS 
WHERE STATUS = 'ok'
GROUP BY SOURCE;
```

## Troubleshooting

### Common Issues

#### 1. Logging Not Working
**Symptoms**: No rows in `LLM_API_LOGS` table
**Check**:
- `ENABLE_API_LOGGING=true` in `.env`
- Snowflake credentials are correct
- Snowflake tables exist and are accessible

#### 2. Live Evaluation Failing
**Symptoms**: No rows in `LLM_API_EVAL_RESULTS` table
**Check**:
- `ENABLE_LIVE_EVAL=true` in `.env`
- Provider API keys are set (OpenAI/Anthropic)
- Evaluation dependencies are installed

#### 3. Caching Not Working
**Symptoms**: No cache hits, all responses show `source='live'`
**Check**:
- `CACHE_ENABLED=true` in `.env`
- Snowflake connectivity
- Cache TTL configuration

#### 4. Performance Issues
**Symptoms**: High latency, slow responses
**Check**:
- Cache hit rates
- Snowflake warehouse size
- Network connectivity

### Debug Mode

Enable debug logging by setting log level:

```bash
uvicorn apps.rag_service.main:app --reload --port 8000 --log-level debug
```

### Health Checks

Check system health:

```bash
# Health endpoint
curl http://localhost:8000/health

# Snowflake connectivity
python scripts/run_snowflake_ping.py
```

## Best Practices

### 1. Monitoring Setup
- Set up alerts for quality score drops
- Monitor cache hit rates for performance
- Track error rates and response times

### 2. Cache Management
- Use appropriate TTL values for your use case
- Monitor cache size and performance
- Implement cache warming for common queries

### 3. Quality Thresholds
- Set minimum quality thresholds for production
- Alert on quality degradation
- Track quality trends over time

### 4. Performance Optimization
- Monitor Snowflake warehouse usage
- Optimize query patterns
- Use appropriate cache TTL values

## Advanced Features

### Custom Metrics
Extend the evaluation system with custom metrics:

```python
# In apps/observability/live_eval.py
def custom_metric(answer: str) -> Dict[str, float]:
    """Custom quality metric."""
    # Your custom logic here
    return {"custom_score": 0.85}
```

### Cache Invalidation
Invalidate cache when context changes:

```python
# Update context version to invalidate cache
os.environ["CONTEXT_VERSION"] = "v2"
```

### Batch Processing
Process multiple queries efficiently:

```python
# Batch evaluation for multiple responses
def batch_evaluate(queries: List[str]) -> List[Dict[str, float]]:
    """Evaluate multiple queries in batch."""
    # Implementation here
    pass
```

## Support

For additional help:

1. **Check Logs**: Review application logs for errors
2. **Verify Configuration**: Ensure all environment variables are set
3. **Test Connectivity**: Use Snowflake ping script
4. **Review Documentation**: Check other guides in the docs/ directory
5. **Create Issues**: Report bugs or request features through GitHub
