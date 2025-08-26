# Promptfoo Interoperability Guide

This document describes the phase-1 Promptfoo YAML reader integration in the AI Quality Kit, allowing users to run existing Promptfoo test assets without rewriting them.

## Overview

The Promptfoo integration provides a minimal YAML reader that can parse common Promptfoo structures and convert them to internal test format. This allows teams with existing Promptfoo configurations to leverage the AI Quality Kit's orchestration and reporting capabilities.

## Key Features

- **Optional Integration**: Only activated when `promptfoo_files` is provided in request options
- **Variable Expansion**: Supports `variables` and `testMatrix` for generating multiple test cases
- **Basic Assertions**: Supports `contains` and `equals` string assertions
- **Graceful Degradation**: Unsupported features are noted but don't fail the run
- **Deterministic**: No JavaScript execution or network calls from YAML

## Supported Features (Phase 1)

### Prompts
- Simple string prompts with variable placeholders
- Prompt objects with `content` or `text` fields
- Variable substitution using `{{variable}}` syntax

### Variables
- Global variables defined in `variables` section
- Variable overrides in `testMatrix` entries
- String interpolation in prompts

### Test Matrix
- Array of variable override objects
- Automatic expansion to individual test cases
- Combination with base variables

### Assertions
- **contains**: Check if output contains specified string
- **equals**: Check if output exactly matches specified string
- List format: `[{type: 'contains', value: 'text'}]`
- Simple string format: `'text'` (treated as contains)

### Providers (Limited)
- Provider hints extracted when `force_provider_from_yaml: true`
- Supports simple provider strings and objects with `id`/`name`
- Orchestrator request provider/model takes precedence by default

## Unsupported Features (Phase 1)

The following Promptfoo features are **not supported** in phase 1 and will be noted in test results:

- **JavaScript Hooks**: No `beforeAll`, `afterAll`, or custom functions
- **Custom Scorers**: Only basic string assertions supported
- **Complex Providers**: Advanced provider configurations
- **File References**: External file imports
- **Advanced Assertions**: Regex, similarity, custom evaluators
- **Datasets**: External dataset loading
- **Transforms**: Output transformations

## Configuration

### Request Options

Add Promptfoo files to your orchestrator request:

```json
{
  "target_mode": "api",
  "api_base_url": "http://localhost:8000",
  "provider": "openai",
  "model": "gpt-4",
  "suites": ["promptfoo"],
  "options": {
    "promptfoo_files": [
      "./tests/promptfoo-config.yaml",
      "./tests/another-config.yaml"
    ],
    "force_provider_from_yaml": false
  }
}
```

### Options

- **promptfoo_files**: Array of file paths to Promptfoo YAML configurations
- **force_provider_from_yaml**: If `true`, use provider from YAML; if `false` (default), use orchestrator request provider

## Example Promptfoo Configuration

### Basic Configuration

```yaml
# promptfoo-basic.yaml
prompts:
  - "Summarize this text: {{text}}"
  - "What is the main topic of: {{text}}"

variables:
  text: "The quick brown fox jumps over the lazy dog."

tests:
  - assert:
      - type: contains
        value: "fox"
      - type: contains
        value: "dog"
```

### Advanced Configuration with Test Matrix

```yaml
# promptfoo-advanced.yaml
prompts:
  - "Translate to {{language}}: {{text}}"
  - "Summarize in {{language}}: {{text}}"

variables:
  text: "Hello world"
  language: "Spanish"

testMatrix:
  - text: "The weather is nice today"
  - text: "AI is transforming technology"
    language: "French"
  - language: "German"

tests:
  - assert:
      - type: contains
        value: "{{language}}"
      - type: equals
        value: "Hola mundo"

providers:
  - openai:gpt-4
```

This configuration will generate 6 tests (2 prompts × 3 matrix combinations).

## Usage Examples

### Running Promptfoo Tests Only

```bash
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "api_base_url": "http://localhost:8000",
    "provider": "openai",
    "model": "gpt-4",
    "suites": ["promptfoo"],
    "options": {
      "promptfoo_files": ["./my-promptfoo-config.yaml"]
    }
  }'
```

### Combining with Other Suites

```bash
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "suites": ["rag_quality", "safety", "promptfoo"],
    "options": {
      "promptfoo_files": ["./promptfoo-tests.yaml"]
    }
  }'
```

### Using Provider from YAML

```bash
curl -X POST "http://localhost:8000/orchestrator/run_tests" \
  -H "Content-Type: application/json" \
  -d '{
    "target_mode": "api",
    "suites": ["promptfoo"],
    "options": {
      "promptfoo_files": ["./config.yaml"],
      "force_provider_from_yaml": true
    }
  }'
```

## Report Integration

### JSON Reports

Promptfoo tests appear in JSON reports under `suite: "promptfoo"`:

```json
{
  "summary": {
    "promptfoo": {
      "total": 6,
      "passed": 5,
      "pass_rate": 0.83
    }
  },
  "detailed": [
    {
      "suite": "promptfoo",
      "test_id": "prompt_1_case_1_text=Hello",
      "query": "Translate to Spanish: Hello world",
      "actual_answer": "Hola mundo",
      "status": "pass",
      "origin": "promptfoo",
      "source": "config.yaml"
    }
  ]
}
```

### Excel Reports

Promptfoo metrics appear in the Summary sheet:
- `promptfoo_total`: Total number of tests
- `promptfoo_passed`: Number of passed tests  
- `promptfoo_pass_rate`: Pass rate percentage

Individual test results appear in the Detailed sheet with `suite=promptfoo`.

## Variable Expansion

The reader supports automatic variable expansion:

### Base Variables
```yaml
variables:
  name: "World"
  greeting: "Hello"
```

### Test Matrix Overrides
```yaml
testMatrix:
  - name: "Alice"
  - name: "Bob"
    greeting: "Hi"
```

Results in combinations:
1. `{name: "Alice", greeting: "Hello"}`
2. `{name: "Bob", greeting: "Hi"}`

## Assertion Evaluation

### Supported Assertions

**Contains Assertion:**
```yaml
assert:
  - type: contains
    value: "expected text"
```
Passes if the output contains the specified text (case-sensitive).

**Equals Assertion:**
```yaml
assert:
  - type: equals
    value: "exact match"
```
Passes if the output exactly matches the specified text (after trimming).

**Simple String Assertion:**
```yaml
assert: "expected text"
```
Treated as a `contains` assertion.

### Unsupported Assertions

Unsupported assertion types are noted in results but don't fail the test:

```yaml
assert:
  - type: regex
    value: "pattern.*"
  - type: similarity
    value: "reference text"
    threshold: 0.8
```

These will appear in results with `supported: false` and explanatory notes.

## Error Handling

The Promptfoo reader is designed to fail gracefully:

### File Loading Errors
- Missing files: Logged and skipped, other files continue processing
- Invalid YAML: Logged and skipped
- Parse errors: Logged with details

### Conversion Errors
- Missing prompts: Returns empty test list
- Invalid variables: Skipped with warning
- Malformed assertions: Noted as unsupported

### Runtime Errors
- Import failures: Promptfoo tests skipped, other suites continue
- Assertion evaluation errors: Individual test marked as failed with error details

## Best Practices

### File Organization
```
tests/
├── promptfoo/
│   ├── basic-tests.yaml
│   ├── advanced-tests.yaml
│   └── regression-tests.yaml
└── orchestrator-config.json
```

### Variable Management
- Use descriptive variable names
- Keep testMatrix entries focused and minimal
- Avoid deeply nested variable structures

### Assertion Design
- Prefer `contains` for flexible matching
- Use `equals` for exact validation
- Keep assertion values simple and clear
- Document unsupported assertions for future migration

### Performance Considerations
- Limit testMatrix combinations to avoid excessive test generation
- Use meaningful test names for easier debugging
- Consider file size and parsing time for large configurations

## Migration from Promptfoo

### Phase 1 Migration Strategy
1. **Inventory**: Identify supported vs unsupported features
2. **Simplify**: Convert complex assertions to basic contains/equals
3. **Test**: Validate behavior with small test sets
4. **Document**: Note unsupported features for future phases

### Common Conversions

**From regex to contains:**
```yaml
# Before (unsupported)
assert:
  - type: regex
    value: "Hello.*world"

# After (supported)
assert:
  - type: contains
    value: "Hello"
  - type: contains
    value: "world"
```

**From custom scorer to basic assertion:**
```yaml
# Before (unsupported)
assert:
  - type: javascript
    value: "output.length > 10"

# After (supported - manual validation)
assert:
  - type: contains
    value: "expected content"
```

## Troubleshooting

### Common Issues

**No tests generated:**
- Check that `prompts` field exists and is not empty
- Verify YAML syntax is valid
- Ensure file paths are correct

**Variables not resolved:**
- Check variable names match exactly (case-sensitive)
- Verify `{{variable}}` syntax is used
- Ensure variables are defined in `variables` or `testMatrix`

**Assertions not working:**
- Verify assertion type is `contains` or `equals`
- Check that assertion values are strings
- Review case sensitivity for `contains` assertions

**Provider not used:**
- Set `force_provider_from_yaml: true` in options
- Verify provider format in YAML
- Check that provider is supported by orchestrator

### Debug Information

Enable detailed logging to see:
- File loading progress
- Variable resolution steps
- Test generation details
- Assertion evaluation results

## Limitations and Future Enhancements

### Current Limitations
- No JavaScript execution
- Limited assertion types
- No external file references
- No advanced provider configurations
- No dataset integration

### Planned Enhancements (Future Phases)
- Additional assertion types (regex, similarity)
- External dataset support
- Advanced provider configurations
- Custom scorer integration
- Performance optimizations

## Integration Architecture

The Promptfoo reader follows these principles:

- **Additive**: Extends existing orchestrator without breaking changes
- **Optional**: Only activated when explicitly requested
- **Deterministic**: No external dependencies or network calls
- **Graceful**: Degrades gracefully on unsupported features
- **Observable**: Full logging and error reporting

For implementation details, see:
- `apps/orchestrator/importers/promptfoo_reader.py` - Core reader logic
- `apps/orchestrator/run_tests.py` - Integration with orchestrator
- `apps/orchestrator/importers/tests/test_promptfoo_reader.py` - Test suite
