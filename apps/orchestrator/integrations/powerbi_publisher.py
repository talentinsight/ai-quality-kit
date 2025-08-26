"""Power BI publisher for AI Quality Kit test results."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import time
import json
import httpx
import logging
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)


class PowerBIClient:
    """Power BI REST API client using MSAL for authentication."""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """Initialize Power BI client with Azure AD credentials."""
        self._authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._scope = ["https://analysis.windows.net/powerbi/api/.default"]
        self._app = ConfidentialClientApplication(
            client_id, 
            authority=self._authority, 
            client_credential=client_secret
        )
        self._token_cache: Optional[Dict[str, Any]] = None

    def _get_token(self) -> str:
        """Get access token for Power BI API."""
        # Try to get token from cache first
        result = self._app.acquire_token_silent(scopes=self._scope, account=None)
        
        # If not in cache, acquire new token
        if not result:
            result = self._app.acquire_token_for_client(scopes=self._scope)
        
        if "access_token" not in result:
            error_desc = result.get('error_description', 'Unknown error')
            raise RuntimeError(f"Power BI token acquisition failed: {error_desc}")
        
        return result["access_token"]

    def _headers(self) -> Dict[str, str]:
        """Get HTTP headers with authorization token."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }

    def find_dataset(self, workspace_id: str, name: str) -> Optional[str]:
        """
        Find existing dataset by name in workspace.
        
        Args:
            workspace_id: Power BI workspace (group) ID
            name: Dataset name to search for
            
        Returns:
            Dataset ID if found, None otherwise
        """
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=self._headers())
                response.raise_for_status()
                
                datasets = response.json().get("value", [])
                for dataset in datasets:
                    if dataset.get("name") == name:
                        return dataset.get("id")
                        
                return None
                
        except Exception as e:
            logger.error(f"Failed to find dataset '{name}': {e}")
            raise

    def create_push_dataset(self, workspace_id: str, name: str, tables: List[Dict[str, Any]]) -> str:
        """
        Create a new push dataset in Power BI workspace.
        
        Args:
            workspace_id: Power BI workspace (group) ID
            name: Dataset name
            tables: List of table definitions with columns
            
        Returns:
            Created dataset ID
        """
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets?defaultRetentionPolicy=None"
        body = {"name": name, "tables": tables}
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    url, 
                    headers=self._headers(), 
                    content=json.dumps(body)
                )
                response.raise_for_status()
                
                result = response.json()
                dataset_id = result.get("id")
                
                if not dataset_id:
                    raise RuntimeError(f"Dataset creation response missing ID: {result}")
                
                logger.info(f"Created Power BI dataset '{name}' with ID: {dataset_id}")
                return dataset_id
                
        except Exception as e:
            logger.error(f"Failed to create dataset '{name}': {e}")
            raise

    def add_rows(self, workspace_id: str, dataset_id: str, table: str, rows: List[Dict[str, Any]]) -> None:
        """
        Add rows to a Power BI dataset table.
        
        Args:
            workspace_id: Power BI workspace (group) ID
            dataset_id: Dataset ID
            table: Table name
            rows: List of row data dictionaries
        """
        if not rows:
            logger.debug(f"No rows to add to table '{table}'")
            return
        
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables/{table}/rows"
        body = {"rows": rows}
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    url, 
                    headers=self._headers(), 
                    content=json.dumps(body)
                )
                response.raise_for_status()
                
                logger.info(f"Added {len(rows)} rows to Power BI table '{table}'")
                
        except Exception as e:
            logger.error(f"Failed to add rows to table '{table}': {e}")
            raise


def ensure_dataset(client: PowerBIClient, workspace_id: str, dataset_name: str) -> str:
    """
    Ensure dataset exists in Power BI workspace, create if not found.
    
    Args:
        client: PowerBIClient instance
        workspace_id: Power BI workspace (group) ID
        dataset_name: Dataset name
        
    Returns:
        Dataset ID
    """
    # Try to find existing dataset
    dataset_id = client.find_dataset(workspace_id, dataset_name)
    if dataset_id:
        logger.info(f"Found existing Power BI dataset '{dataset_name}': {dataset_id}")
        return dataset_id
    
    # Define schema for push dataset
    tables = [
        {
            "name": "run_summary",
            "columns": [
                {"name": "run_id", "dataType": "string"},
                {"name": "started_at", "dataType": "DateTime"},
                {"name": "finished_at", "dataType": "DateTime"},
                {"name": "duration_ms", "dataType": "Int64"},
                {"name": "provider", "dataType": "string"},
                {"name": "model", "dataType": "string"},
                {"name": "suites", "dataType": "string"},        # comma-joined
                {"name": "total", "dataType": "Int64"},
                {"name": "passed", "dataType": "Int64"},
                {"name": "pass_rate", "dataType": "double"},
                {"name": "policy_violations", "dataType": "Int64"}
            ]
        },
        {
            "name": "test_detail",
            "columns": [
                {"name": "run_id", "dataType": "string"},
                {"name": "suite", "dataType": "string"},
                {"name": "test_name", "dataType": "string"},
                {"name": "status", "dataType": "string"},
                {"name": "score", "dataType": "double"},
                {"name": "latency_ms", "dataType": "Int64"}
            ]
        }
    ]
    
    # Create new dataset
    return client.create_push_dataset(workspace_id, dataset_name, tables)


def publish_run_result(pbi: PowerBIClient, workspace_id: str, dataset_id: str, result: dict) -> None:
    """
    Publish test run results to Power BI dataset.
    
    Args:
        pbi: PowerBIClient instance
        workspace_id: Power BI workspace (group) ID
        dataset_id: Dataset ID
        result: Test run result dictionary
    """
    try:
        # Build aggregates safely (backwards-compatible with current JSON)
        metrics = result.get("metrics") or {}
        total = int(metrics.get("total") or 0)
        passed = int(metrics.get("pass_count") or 0)
        pass_rate = (100.0 * passed / max(total, 1))
        suites_list = result.get("suites") or []
        started_at = result.get("started_at") or ""
        finished_at = result.get("finished_at") or ""
        provider = result.get("provider") or ""
        model = result.get("model") or ""
        policy_hits = int(metrics.get("policy_violations") or 0)

        # Prepare run summary row
        run_summary_rows = [{
            "run_id": result.get("run_id") or "",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int(result.get("duration_ms") or 0),
            "provider": provider,
            "model": model,
            "suites": ",".join([str(s) for s in suites_list]),
            "total": total,
            "passed": passed,
            "pass_rate": round(pass_rate, 2),
            "policy_violations": policy_hits
        }]

        # Prepare test detail rows (minimal, non-PII fields only)
        test_rows = []
        for test in (result.get("tests") or []):
            test_rows.append({
                "run_id": result.get("run_id") or "",
                "suite": test.get("suite") or "",
                "test_name": test.get("name") or "",
                "status": test.get("status") or "",
                "score": float(test["score"]) if test.get("score") is not None else None,
                "latency_ms": int(test.get("latency_ms") or 0)
            })

        # Push data to Power BI
        pbi.add_rows(workspace_id, dataset_id, "run_summary", run_summary_rows)
        pbi.add_rows(workspace_id, dataset_id, "test_detail", test_rows)
        
        logger.info(f"Successfully published run {result.get('run_id')} to Power BI")
        
    except Exception as e:
        logger.error(f"Failed to publish run result to Power BI: {e}")
        raise
