# AI Integration Quickstart

## Overview

The AI Quality Kit provides a complete AI-powered testing framework for LLM outputs, covering quality, safety, and output format validation. This guide will help you get started with the core AI integration features.

## Prerequisites

1. **Python 3.11** - Virtual environment activated
2. **API Keys** - OpenAI and/or Anthropic API keys configured in `.env`
3. **Dependencies** - All packages installed via `pip install -r infra/requirements.txt`

## Quick Start

### 1. Start the RAG Service

```bash
# Start the FastAPI service
uvicorn apps.rag_service.main:app --reload --port 8000
```

The service will:
- Build a FAISS index from `data/golden/passages.jsonl`
- Initialize the RAG pipeline with your configured LLM provider
- Start the `/ask` endpoint for query processing

### 2. Test the RAG Service

```bash
# Test with a simple query
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is data quality validation?"}'
```

Expected response:
```json
{
  "answer": "Data quality validation is crucial in ETL pipelines...",
  "context": ["Passage 1 content...", "Passage 2 content..."]
}
```

### 3. Run Quality Tests

```bash
# Run all tests (may skip if API keys missing)
pytest -q

# Run specific test categories
pytest evals/test_ragas_quality.py -v      # Quality metrics
pytest guardrails/test_guardrails.py -v    # JSON schema validation
pytest safety/test_safety_basic.py -v      # Safety checks
```

## Test Categories

### Quality Evaluation (Ragas)
- **Faithfulness**: Measures how well answers are grounded in provided context
- **Context Recall**: Evaluates retrieval system effectiveness
- **Thresholds**: Faithfulness ≥ 0.75, Context Recall ≥ 0.80

### Guardrails
- **JSON Schema Validation**: Ensures outputs conform to required structure
- **PII Detection**: Heuristic checks for sensitive information
- **Format Consistency**: Validates response structure across queries

### Safety Testing
- **Attack Prompt Detection**: Tests against adversarial inputs
- **Context Injection**: Prevents manipulation of system instructions
- **Zero Tolerance**: All safety violations must be properly refused

## Configuration

### Environment Variables

```env
# LLM Provider Configuration
OPENAI_API_KEY=your_openai_key
MODEL_NAME=gpt-4o-mini
PROVIDER=openai

# Alternative: Anthropic
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-3-5-sonnet

# RAG Configuration
RAG_TOP_K=4
```

### Provider Selection

The system automatically selects the provider based on available API keys:
- **OpenAI**: Uses `OPENAI_API_KEY` + `MODEL_NAME`
- **Anthropic**: Uses `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`
- **Fallback**: Gracefully handles missing keys with informative messages

## Optional: Snowflake Logging

Enable evaluation result logging to Snowflake:

```env
# Enable logging
LOG_TO_SNOWFLAKE=true
EVAL_RUN_ID=my_evaluation_run
EVAL_NOTES=Testing new model version

# Snowflake credentials (see SNOWFLAKE_SETUP.md)
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=...
# ... other Snowflake variables
```

When enabled, test results are automatically logged to the `LLM_EVAL_RESULTS` table for trend analysis.

## Troubleshooting

### Common Issues

**API Key Errors**
```bash
# Check environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Verify .env file loading
python -c "from dotenv import load_dotenv; load_dotenv(); print('Keys loaded')"
```

**Test Failures**
```bash
# Run with verbose output
pytest -v --tb=short

# Check specific test
pytest evals/test_ragas_quality.py::TestRagasQuality::test_faithfulness_threshold -v
```

**Service Startup Issues**
```bash
# Check logs
uvicorn apps.rag_service.main:app --reload --port 8000 --log-level debug

# Verify data files exist
ls -la data/golden/
```

## Next Steps

1. **Customize Prompts**: Modify `llm/prompts.py` for your use case
2. **Add Test Data**: Extend `data/golden/` with domain-specific examples
3. **Adjust Thresholds**: Modify quality thresholds in test files
4. **Extend Metrics**: Add custom evaluation metrics to `evals/metrics.py`
5. **Production Deployment**: Use Docker and environment-specific configs

## Support

- **Documentation**: Check `docs/` directory for detailed guides
- **Issues**: Create GitHub issues for bugs or feature requests
- **Tests**: Use `pytest --collect-only` to see all available tests
