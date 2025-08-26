# Ragas Integration Guide

This document describes how to use the optional Ragas evaluator plugin for RAG quality assessment in the AI Quality Kit.

## Overview

The Ragas integration provides advanced RAG evaluation metrics that complement the existing quality testing framework. It computes metrics like faithfulness, answer relevancy, context precision, and context recall to provide deeper insights into RAG system performance.

## Key Features

- **Optional and Additive**: Ragas evaluation is OFF by default and doesn't break existing functionality
- **Graceful Degradation**: If Ragas is unavailable or fails, tests continue normally
- **Threshold Support**: Set minimum thresholds for Ragas metrics to define pass/fail criteria
- **Comprehensive Reporting**: Metrics appear in JSON, XLSX, and HTML reports
- **Memory-Only**: No persistent storage beyond existing test artifacts

## Configuration

### Environment Variables

```bash
# Enable Ragas evaluation globally (default: false)
RAGAS_ENABLED=true
```

### Request-Level Toggle

You can also enable Ragas per-request, which takes precedence over the environment setting:

```json
{
  "target_mode": "api",
  "suites": ["rag_quality"],
  "use_ragas": true,
  "provider": "openai",
  "model": "gpt-4"
}
```

## Dependencies

The Ragas integration requires the following additional dependencies:

```
ragas>=0.2.9
```

These are included in the requirements.txt file but Ragas evaluation will be skipped if not installed.

## Metrics Computed

When enabled, the following Ragas metrics are computed for RAG quality suites:

### Core Metrics (Always Available)
- **Faithfulness**: Measures how grounded the answer is in the provided context
- **Answer Relevancy**: Measures how relevant the answer is to the question

### Ground Truth Dependent Metrics
- **Context Precision**: Measures how relevant the retrieved contexts are to the question
- **Context Recall**: Measures how much of the ground truth is captured by the retrieved contexts

*Note: Context precision and context recall require ground truth data to be available in test cases.*

## Threshold Configuration

You can set minimum thresholds for Ragas metrics to define pass/fail criteria:

```json
{
  "target_mode": "api",
  "suites": ["rag_quality"],
  "use_ragas": true,
  "thresholds": {
    "min_faithfulness": 0.8,
    "min_answer_relevancy": 0.85,
    "min_context_precision": 0.7,
    "min_context_recall": 0.75
  }
}
```

### Threshold Behavior

- Thresholds are checked only for the RAG quality suite
- All specified thresholds must be met for the suite to pass Ragas evaluation
- Threshold results appear in reports under `ragas_thresholds_passed`
- Individual test pass/fail status is not affected by Ragas thresholds

## Report Integration

### JSON Reports

Ragas metrics are automatically included in the JSON report under the RAG quality suite summary:

```json
{
  "summary": {
    "rag_quality": {
      "total": 10,
      "passed": 8,
      "pass_rate": 0.8,
      "avg_faithfulness": 0.75,
      "avg_context_recall": 0.70,
      "ragas": {
        "faithfulness": 0.85,
        "answer_relevancy": 0.88,
        "context_precision": 0.82,
        "context_recall": 0.79
      },
      "ragas_thresholds": {
        "min_faithfulness": true,
        "min_answer_relevancy": true,
        "min_context_precision": true,
        "min_context_recall": true
      },
      "ragas_thresholds_passed": true
    }
  }
}
```

### Excel Reports

Ragas metrics appear as additional columns in the Summary sheet:

- `ragas_faithfulness`
- `ragas_answer_relevancy` 
- `ragas_context_precision`
- `ragas_context_recall`
- `ragas_thresholds_passed`

### HTML Reports

HTML reports automatically include Ragas metrics in the RAG quality section when available.

## Usage Examples

### Basic Usage

Enable Ragas evaluation for a RAG quality test run:

```bash
# Set environment variable
export RAGAS_ENABLED=true

# Run tests
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "api_base_url": "http://localhost:8000",
    "suites": ["rag_quality"],
    "provider": "openai",
    "model": "gpt-4"
  }'
```

### With Thresholds

Run tests with Ragas thresholds:

```bash
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "api_base_url": "http://localhost:8000",
    "suites": ["rag_quality"],
    "use_ragas": true,
    "thresholds": {
      "min_faithfulness": 0.8,
      "min_answer_relevancy": 0.85
    },
    "provider": "openai",
    "model": "gpt-4"
  }'
```

### Per-Request Override

Override the global setting for a specific request:

```bash
# Even if RAGAS_ENABLED=false globally
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "suites": ["rag_quality"],
    "use_ragas": true,
    "provider": "openai",
    "model": "gpt-4"
  }'
```

## Error Handling and Degradation

The Ragas integration is designed to fail gracefully:

### Import Failures
If Ragas is not installed or cannot be imported:
- Evaluation is skipped silently
- Tests continue normally
- No Ragas metrics appear in reports

### Evaluation Errors
If Ragas evaluation fails (e.g., API issues, data problems):
- Error is logged but not propagated
- Tests continue normally
- Empty Ragas metrics in reports

### Common Issues

1. **uvloop Compatibility**: Some environments may have uvloop conflicts
   - Automatically detected and handled
   - Evaluation skipped with warning log

2. **OpenAI API Issues**: Ragas may use OpenAI API for some metrics
   - Check API key configuration
   - Monitor rate limits
   - Consider using different models

3. **Insufficient Data**: Ragas requires specific data format
   - Questions, answers, and contexts must be non-empty
   - Invalid samples are filtered out automatically

## Best Practices

1. **Start Small**: Begin with a few test cases to verify Ragas is working
2. **Monitor Performance**: Ragas evaluation adds latency to test runs
3. **Set Reasonable Thresholds**: Start with lower thresholds and adjust based on results
4. **Use Ground Truth**: Include expected answers for full metric coverage
5. **Check Logs**: Monitor logs for Ragas-related warnings or errors

## Troubleshooting

### Ragas Not Running

Check the following:

1. **Environment Variable**: Ensure `RAGAS_ENABLED=true` or `use_ragas: true` in request
2. **Dependencies**: Verify `ragas>=0.2.9` is installed
3. **Suite Selection**: Ragas only runs for `rag_quality` suite
4. **Data Format**: Ensure test cases have question, answer, and contexts

### No Metrics in Reports

If Ragas is enabled but no metrics appear:

1. **Check Logs**: Look for Ragas-related error messages
2. **Verify Data**: Ensure test cases have valid RAG data
3. **API Configuration**: Check OpenAI API key if using OpenAI-dependent metrics
4. **Sample Count**: Ensure there are valid samples after filtering

### Performance Issues

If Ragas evaluation is slow:

1. **Reduce Sample Size**: Use fewer test cases for initial validation
2. **Check API Limits**: Monitor OpenAI API rate limits
3. **Consider Alternatives**: Use existing faithfulness/context_recall metrics for faster evaluation

## Integration Architecture

The Ragas integration follows these principles:

- **Thin Adapter**: Minimal wrapper around Ragas functionality
- **Fail-Safe**: Never breaks existing test runs
- **Additive**: Extends existing metrics without replacing them
- **Configurable**: Multiple levels of control (env, request, thresholds)
- **Observable**: Full logging and error reporting

For more details on the implementation, see:
- `apps/orchestrator/evaluators/ragas_adapter.py` - Core adapter logic
- `apps/orchestrator/run_tests.py` - Integration with test runner
- `apps/settings.py` - Configuration management
