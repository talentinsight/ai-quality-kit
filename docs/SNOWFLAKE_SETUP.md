# Snowflake Integration Setup

## Purpose

The Snowflake integration in AI Quality Kit enables:

- **Evaluation Result Logging**: Store quality assessment results for trend analysis and reporting
- **Golden Dataset Management**: Version-controlled test datasets stored in Snowflake tables
- **Analytics and Reporting**: Long-term storage and analysis of AI quality metrics
- **Compliance Auditing**: Persistent records of safety testing and quality validation

This integration is optional and does not affect the core functionality of the AI Quality Kit. It provides additional capabilities for enterprise deployments requiring data persistence and analytics.

## Prerequisites

Before setting up Snowflake integration, ensure you have:

1. **Active Snowflake Account**: A working Snowflake account with appropriate permissions
2. **Database Access**: Access to a database, schema, and warehouse for storing evaluation data
3. **User Credentials**: Username, password, and role with necessary privileges
4. **Network Access**: Ability to connect to Snowflake from your deployment environment

### Required Snowflake Permissions

Your Snowflake user/role should have the following minimum permissions:

- `USAGE` on the specified warehouse
- `USAGE` on the specified database and schema
- `CREATE TABLE` and `INSERT` privileges for logging evaluation results
- `SELECT` privileges for reading golden datasets

## Setup Instructions

### 1. Install Dependencies

Ensure you have the latest dependencies installed:

```bash
pip install -r infra/requirements.txt
```

This will install the `snowflake-connector-python` package along with other required dependencies.

### 2. Configure Environment Variables

Copy the environment template and configure Snowflake credentials:

```bash
cp .env.example .env
```

Edit the `.env` file and populate the Snowflake configuration section:

```env
# Snowflake Configuration (optional for data logging and analytics)
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=your_role
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
```

#### Configuration Details

- **SNOWFLAKE_ACCOUNT**: Your Snowflake account identifier (e.g., `abc12345.us-east-1`)
- **SNOWFLAKE_USER**: Your Snowflake username
- **SNOWFLAKE_PASSWORD**: Your Snowflake password
- **SNOWFLAKE_ROLE**: Role with appropriate permissions (e.g., `ANALYST`, `DEVELOPER`)
- **SNOWFLAKE_WAREHOUSE**: Compute warehouse for query execution
- **SNOWFLAKE_DATABASE**: Target database for storing evaluation data
- **SNOWFLAKE_SCHEMA**: Schema within the database for organizing tables

### 3. Test Connection

Run the smoke test script to verify connectivity:

```bash
python scripts/snowflake_smoke.py
```

Expected output for successful connection:

```
Snowflake Connectivity Smoke Test
========================================
Environment configuration: OK
Database connection: OK

Snowflake Environment Details:
  Account:   ABC12345
  Region:    US-EAST-1
  Role:      ANALYST
  Warehouse: COMPUTE_WH
  Database:  AI_QUALITY_DB
  Schema:    EVALUATIONS
  Timestamp: 2024-01-15 10:30:45.123

Snowflake connectivity test: PASSED
```

### 4. Run Optional Tests

Execute the Snowflake integration tests:

```bash
pytest -q tests/test_snowflake_connection.py
```

If environment variables are not configured, tests will be skipped with an informative message.

## Usage Examples

### Basic Connection Test

```python
from apps.db.snowflake_client import snowflake_cursor

# Test connection and run a simple query
with snowflake_cursor() as cursor:
    cursor.execute("SELECT CURRENT_TIMESTAMP()")
    result = cursor.fetchone()
    print(f"Current time: {result[0]}")
```

### Environment Status Check

```python
from apps.db.snowflake_client import env_summary

# Check configuration status
status = env_summary()
for var, info in status.items():
    print(f"{var}: {'✓' if info['present'] else '✗'}")
```

## Troubleshooting

### Common Connection Issues

**Issue**: `Failed to connect to Snowflake: Incorrect username or password`
- **Solution**: Verify `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD` are correct
- **Check**: Ensure the user account is not locked or expired

**Issue**: `Failed to connect to Snowflake: Role 'ROLE_NAME' does not exist`
- **Solution**: Verify `SNOWFLAKE_ROLE` exists and is assigned to your user
- **Check**: Contact your Snowflake administrator to confirm role assignment

**Issue**: `Failed to connect to Snowflake: Account identifier is incorrect`
- **Solution**: Check `SNOWFLAKE_ACCOUNT` format (should include region if not using default)
- **Example**: Use `abc12345.us-east-1` instead of just `abc12345`

**Issue**: `Failed to connect to Snowflake: Network error`
- **Solution**: Verify network connectivity and firewall settings
- **Check**: Ensure your IP address is whitelisted in Snowflake network policies

### Authentication Troubleshooting

1. **Verify Account Format**: Account identifiers vary by region and cloud provider
   - AWS: `account_name.region_id` (e.g., `abc12345.us-east-1`)
   - Azure: `account_name.region_id.azure` (e.g., `abc12345.central-us.azure`)
   - GCP: `account_name.region_id.gcp` (e.g., `abc12345.us-central1.gcp`)

2. **Check Role Permissions**: Ensure your role has the required privileges:
   ```sql
   -- Check current role and privileges
   SELECT CURRENT_ROLE();
   SHOW GRANTS TO ROLE your_role_name;
   ```

3. **Test Manual Connection**: Use Snowflake CLI or web interface to verify credentials

### Performance Optimization

- **Warehouse Size**: Use appropriate warehouse size for your workload
- **Auto-suspend**: Configure warehouse auto-suspend to minimize costs
- **Connection Pooling**: For high-frequency operations, consider connection pooling

## Security Best Practices

### Credential Management

- **Never commit credentials**: Keep `.env` files in `.gitignore`
- **Use strong passwords**: Follow your organization's password policy
- **Rotate credentials regularly**: Update passwords according to security policies
- **Limit permissions**: Use principle of least privilege for database access

### CI/CD Integration

Snowflake tests are optional and disabled by default in CI environments. To enable:

1. **GitHub Actions**: Add Snowflake credentials as repository secrets
2. **Environment Variables**: Configure secrets in your CI platform
3. **Test Selection**: Use pytest markers to conditionally run Snowflake tests

Example GitHub Actions configuration:
```yaml
env:
  SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
  SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
  # ... other Snowflake variables
```

**Note**: Only enable Snowflake tests in CI when you have configured the appropriate secrets. Tests will be automatically skipped if credentials are not available.

## Integration Roadmap

Future enhancements for Snowflake integration:

- **Automated Schema Creation**: Scripts to set up required tables and views
- **Evaluation Result Logging**: Automatic storage of quality assessment results
- **Golden Dataset Sync**: Bidirectional sync between local files and Snowflake tables
- **Analytics Dashboards**: Pre-built dashboards for evaluation trend analysis
- **Data Retention Policies**: Configurable retention and archival strategies

## Support

For additional help:

1. **Snowflake Documentation**: [docs.snowflake.com](https://docs.snowflake.com)
2. **Connector Documentation**: [python-connector-api](https://docs.snowflake.com/en/user-guide/python-connector-api)
3. **Project Issues**: Create an issue in the AI Quality Kit repository
4. **Community Support**: Reach out through project communication channels

## Evaluation Logging

The AI Quality Kit can optionally log evaluation results to Snowflake for long-term analysis and trend monitoring.

### Enable Evaluation Logging

To enable evaluation logging, set the following environment variables:

```env
LOG_TO_SNOWFLAKE=true
EVAL_RUN_ID=optional_custom_run_id
EVAL_NOTES=optional_notes_about_this_run
```

### Required Table Structure

Create the following table in your Snowflake schema:

```sql
CREATE TABLE LLM_EVAL_RESULTS (
    RUN_ID VARCHAR(255),
    METRIC_GROUP VARCHAR(100),
    METRIC_NAME VARCHAR(100),
    METRIC_VALUE FLOAT,
    EXTRA VARIANT,
    RECORDED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

## API Logging, Live Evaluation, and Caching Tables

To enable production-grade API logging, live evaluation, and caching, create the following tables in your Snowflake schema:

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
  SOURCE STRING,              -- "live" | "cache"
  LATENCY_MS NUMBER,
  STATUS STRING,              -- "ok" | "error"
  ERROR_MSG STRING
);

-- Live evaluation results (one row per metric per API call)
CREATE TABLE IF NOT EXISTS LLM_API_EVAL_RESULTS (
  LOG_ID STRING,              -- foreign key to LLM_API_LOGS.ID
  METRIC_GROUP STRING,        -- "ragas" | "guardrails" | "safety"
  METRIC_NAME STRING,         -- e.g., "faithfulness"
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
