# AI Quality Kit - Test Quality Charter

**Version**: 2.1  
**Last Updated**: 2024-12-21  
**Status**: Active

## Overview

This charter defines the quality standards, evaluation procedures, and consistency requirements for the AI Quality Kit test framework. It establishes the principles governing how test cases are evaluated, when results are quarantined, and what constitutes acceptable quality thresholds.

## Test Case Classification

### Canonical vs Expanded Test Sets

- **Canonical Set**: SME-curated, core test cases that must never be mutated
  - Hand-crafted by subject matter experts
  - Represents essential functionality and critical edge cases
  - 100% pass rate required for production readiness
  - Stored in `data/golden/` directory
  - Version controlled and immutable

- **Expanded Set**: Volume-oriented test cases for broader coverage
  - Generated programmatically or sourced from external datasets
  - Includes metamorphic variants and counterfactual pairs
  - Used for statistical confidence and edge case discovery
  - May include experimental or exploratory scenarios

## Oracle Priority and Evaluation

### Two-Stage Evaluation Process

1. **Primary Oracle** (Stage 1):
   - `exact`: Strict normalized string equality (highest precision)
   - `contains`: Normalized substring containment (balanced)
   - `regex`: Word-boundary aware pattern matching (structured)
   - `semantic`: Similarity scoring with fallback to contains (flexible)

2. **Secondary Guards** (Stage 2):
   - Applied only to `semantic` and `contains` oracles
   - Detects common failure patterns: errors, refusals, unavailability
   - Overrides positive oracle results when failure indicators present

### Oracle Selection Guidelines

- **Critical cases**: Use `exact` or `regex` for maximum precision
- **Content verification**: Use `contains` for key information presence
- **Semantic understanding**: Use `semantic` with appropriate thresholds
- **Pattern validation**: Use `regex` for structured data verification

## Anti-Flake Policy

### Stability Testing

Test cases marked as `severity: "critical"` are automatically subjected to stability testing when `quality_guard.enabled=true`:

- **Repeat Count**: Default 2 repetitions with identical inputs
- **Deterministic Seeding**: Uses `deterministic_seed` for reproducible behavior
- **Variance Threshold**: Score variance >10% indicates instability

### Quarantine Rules

- **Unstable Cases**: Cases with inconsistent outcomes across repetitions
- **Quarantine Action**: Excluded from pass/fail calculations, marked `unstable=true`
- **Reporting**: Quarantined cases reported separately in quality metrics
- **Resolution**: Manual review required to determine root cause

## Metamorphic and Counterfactual Rules

### Metamorphic Consistency

Cases within the same `metamorphic_group` must show consistent behavior:

- **Invariant Preservation**: Core functionality must remain unchanged
- **Surface Variation**: Punctuation, politeness, ordering may vary
- **Consistency Check**: All group members must have identical pass/fail outcomes
- **Violation Handling**: Metamorphic breaks counted but don't affect individual case results

### Counterfactual Parity

Demographic and contextual substitutions must maintain fairness:

- **Parity Tolerance**: Score differences <10% between variants
- **Bias Detection**: Systematic outcome differences indicate potential bias
- **Protected Attributes**: Gender, age, location, socioeconomic status
- **Escalation**: Parity violations trigger manual bias review

## Severity Levels and SLO Gates

### Severity Classification

- **Critical**: Must pass 100% - production blockers
  - Security vulnerabilities
  - Data leakage scenarios
  - Core functionality failures

- **Major**: Per-suite threshold (default 90%)
  - Feature completeness
  - Performance requirements
  - Standard compliance

- **Minor**: Informational only
  - Edge cases
  - Usability improvements
  - Documentation gaps

### SLO Gates

- **Critical Gate**: No critical failures allowed for production deployment
- **Major Gate**: ≥90% pass rate per test suite
- **Minor Gate**: Trend monitoring only, no blocking
- **Stability Gate**: <5% quarantine rate for critical cases

## Quality Guard Configuration

### Default Settings

```json
{
  "quality_guard": {
    "enabled": true,
    "repeat_n": 2,
    "sample_criticals": 5
  }
}
```

### Adaptive Thresholds

- **High-Stakes Domains**: Increase `repeat_n` to 3-5
- **Performance Testing**: Reduce repetitions for latency-sensitive cases
- **Development Mode**: Disable quality guard for rapid iteration

## Resilience Testing Standards

### Scenario Catalog Principles

- **Deterministic Generation**: Fixed seeds ensure reproducible scenario matrices
- **Comprehensive Coverage**: All critical failure modes represented (timeout, 5xx, 429, circuit_open, burst, idle_stream)
- **Parameter Matrix**: Systematic coverage of timeout values, concurrency levels, circuit breaker settings
- **Enterprise Patterns**: Scenarios derived from production failure analysis and industry best practices

### Catalog Governance

- **Scenario Count**: Minimum 48 scenarios across failure mode combinations
- **Version Control**: Dated scenario catalogs (`data/resilience_catalog/YYYYMMDD/`)
- **Idempotent Generation**: Re-running generator on same date produces identical scenarios
- **Legacy Compatibility**: Catalog usage optional via `use_catalog=false` fallback

### Failure Mode Classification

- **Infrastructure Failures**: `timeout`, `upstream_5xx`, `upstream_429`
- **Circuit Protection**: `circuit_open` scenarios with varied sensitivity settings
- **Load Patterns**: `burst` (spike handling) and `idle_stream` (TTFB/connection reuse)
- **Cascading Failures**: Multi-layer timeout/retry/circuit combinations

### Resilience Quality Gates

- **Success Rate Threshold**: ≥80% success rate under normal conditions
- **Graceful Degradation**: Proper error handling and retry behavior
- **Performance Under Load**: Latency targets maintained during `burst` scenarios
- **Circuit Recovery**: Breaker reset functionality verified in `circuit_open` tests

### Reporting and Analytics

- **Failure Mode Distribution**: `by_failure_mode` counters for pattern analysis
- **Scenario Metadata**: Additive Excel columns (scenario_id, failure_mode, payload_size, target_timeout_ms, fail_rate, circuit_*)
- **Trend Monitoring**: Resilience degradation alerts on success rate changes
- **Capacity Planning**: Performance data for infrastructure scaling decisions

## Compliance and Privacy

### Enhanced PII Detection

- **Anchored Patterns**: Word-boundary aware regex compilation
- **Luhn Validation**: Credit card number mathematical verification
- **Allowlist Protection**: Demo/test data explicitly excluded
- **Confidence Scoring**: Low-confidence matches filtered out

### False Positive Reduction

- **Multi-Stage Validation**: Pattern + mathematical + allowlist checks
- **Context Awareness**: Domain-specific validation rules
- **Human Review**: High-confidence violations escalated to privacy team

## Reporting and Metrics

### Quality Metrics Dashboard

- **Stability Rate**: Percentage of stable vs unstable cases
- **Consistency Rate**: Metamorphic group agreement percentage
- **Parity Score**: Counterfactual fairness measurement
- **Confidence Distribution**: PII detection accuracy metrics

### Trend Analysis

- **Quality Degradation**: Alert on increasing quarantine rates
- **Bias Drift**: Monitor counterfactual parity over time
- **Oracle Performance**: Track secondary guard trigger rates

## Governance and Updates

### Charter Maintenance

- **Quarterly Review**: Assess effectiveness and update thresholds
- **Stakeholder Input**: Engineering, Product, Security, Legal teams
- **Version Control**: All changes tracked with rationale

### Exception Handling

- **Temporary Waivers**: Critical deployments with planned remediation
- **Threshold Adjustments**: Based on empirical data and business needs
- **New Oracle Types**: Extended evaluation for emerging requirements

---

**Contact**: AI Quality Team  
**Repository**: ai-quality-kit  
**Last Audit**: 2024-12-21  
**Changelog**: v2.1 - Added Resilience Testing Standards for scenario catalog and failure mode coverage
