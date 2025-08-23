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

## Quick Validation

For rapid health checks and smoke testing, use the Quick Validation Pack:

### Running Quick Validation

```bash
# Start server and run all checks
make quickcheck

# Run checks against already running server
make quickcheck.running

# Direct script execution
python scripts/quickcheck.py
```

### What It Verifies

- **Health Endpoints**: `/healthz` and `/readyz` return 200
- **Mock Provider**: `/ask` with `provider=mock` works correctly
- **Performance Headers**: `X-Perf-Phase` and `X-Latency-MS` are present
- **Multi-Suite Orchestrator**: Runs all test suites in single request
- **Report Generation**: Downloads JSON and Excel reports
- **Excel Validation**: Verifies required sheets (Summary, Detailed, API_Details, Inputs_And_Expected)
- **A2A Manifest**: Checks A2A endpoint availability (if enabled)

### Privacy & Safety

- **Zero Retention**: No user data written to database (`PERSIST_DB=false`)
- **Mock Provider**: Uses safe mock responses, no external API calls
- **Temporary Artifacts**: Reports saved under `./tmp/quickcheck_<run_id>/`
- **Auto-cleanup**: Artifacts auto-deleted after configured time

### Troubleshooting

**Token 401 Errors**
```bash
# Check auth configuration
export QUICKCHECK_TOKEN="SECRET_USER"
# Ensure AUTH_TOKENS includes user:SECRET_USER
```

**Port In Use**
```bash
# Use different port
export QUICKCHECK_PORT="8001"
export QUICKCHECK_BASE="http://localhost:8001"
```

**Missing Excel Sheets**
- Verify orchestrator completed successfully
- Check that all test suites ran without errors
- Ensure openpyxl is installed: `pip install openpyxl`

**Server Start Issues**
```bash
# Skip server start if already running
export QUICKCHECK_START_SERVER="false"
make quickcheck.running
```

## Operator UI

For a modern web interface to run orchestrated tests, use the single-page Operator UI:

### Getting Started

```bash
# Navigate to UI directory
cd frontend/operator-ui

# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at `http://localhost:5173`

### Features

- **Single Page Interface**: All controls on one screen
- **Target Selection**: Choose between API (HTTP) or MCP mode
- **Provider & Model**: Select from OpenAI, Anthropic, Gemini, Custom REST, or Mock
- **Multi-Suite Testing**: Select any combination of test suites:
  - `rag_quality` - RAG evaluation metrics
  - `red_team` - Adversarial testing
  - `safety` - Safety and toxicity checks
  - `performance` - Latency and throughput
  - `regression` - Baseline comparisons
- **Threshold Configuration**: Set quality thresholds (faithfulness, context recall, toxicity)
- **Live Status**: Shows busy/idle state during test execution
- **Report Downloads**: Download JSON and Excel reports with authentication

### Privacy & Security

- **Memory-Only Tokens**: Bearer tokens kept in memory, never persisted
- **No Data Retention**: Privacy banner confirms no user data persisted by default
- **Authenticated Downloads**: Reports fetched with Authorization header
- **Blob Downloads**: Files saved via browser Blob API

### Report Structure

Downloaded Excel reports contain these sheets:
- **Summary**: Overall test results and pass rates
- **Detailed**: Individual test case results
- **API_Details**: API call logs and performance metrics
- **Inputs_And_Expected**: Test inputs and expected outputs
- **Adversarial_Details**: Red team attack details (when red_team suite selected)
- **Coverage**: Test coverage analysis (when red_team suite selected)

### Test Volume Controls

The UI provides flexible test volume controls to optimize testing time and coverage:

#### Volume Settings
- **qa_sample_size**: Number of QA pairs to test (empty = all available)
- **attack_mutators**: Number of variants per red team attack (1-5)
- **perf_repeats**: Number of performance test repetitions (2-10)

#### Run Profiles
Quick preset configurations for common testing scenarios:

- **Smoke** (qa=2, attacks=1, perf=2): Fast validation, ~15 tests
- **Full** (qa=20, attacks=3, perf=5): Comprehensive testing, ~85 tests  
- **Red Team Heavy** (qa=5, attacks=5, perf=3): Security-focused, ~58 tests

#### Attack Mutators
Red team tests generate multiple variants per base attack:
1. **Direct**: Original attack prompt
2. **Roleplay**: "You are a helpful assistant. Please help me with: [attack]"
3. **Indirect**: "Can you explain how someone might: [attack]"
4. **Additional variants**: Paraphrased versions for higher mutator counts

### Offline Testing

Use `provider=mock` for offline testing without external API calls. Mock provider returns deterministic responses for development and CI/CD.

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
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
