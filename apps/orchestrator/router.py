"""FastAPI router for orchestrator endpoints."""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import Optional

from .run_tests import OrchestratorRequest, OrchestratorResult, TestRunner
from apps.security.auth import require_user_or_admin, Principal

# Create router
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

def get_reports_dir() -> Path:
    """Get reports directory path from environment."""
    reports_dir = Path(os.getenv("REPORTS_DIR", "./reports"))
    reports_dir.mkdir(exist_ok=True)
    return reports_dir


@router.post("/run_tests", response_model=OrchestratorResult)
async def run_tests(
    request: OrchestratorRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> OrchestratorResult:
    """
    Run multiple test suites and generate reports.
    
    Args:
        request: Orchestrator request with test configuration
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Orchestrator result with run ID and artifact paths
    """
    try:
        # Create and run test runner
        runner = TestRunner(request)
        result = await runner.run_all_tests()
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run tests: {str(e)}"
        )


@router.get("/report/{run_id}.json")
async def get_json_report(
    run_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> FileResponse:
    """
    Download JSON report for a test run.
    
    Args:
        run_id: Test run identifier
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        JSON file download
    """
    json_path = get_reports_dir() / f"{run_id}.json"
    
    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"JSON report not found for run_id: {run_id}"
        )
    
    return FileResponse(
        path=str(json_path),
        filename=f"{run_id}.json",
        media_type="application/json"
    )


@router.get("/report/{run_id}.xlsx")
async def get_xlsx_report(
    run_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> FileResponse:
    """
    Download Excel report for a test run.
    
    Args:
        run_id: Test run identifier
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Excel file download
    """
    xlsx_path = get_reports_dir() / f"{run_id}.xlsx"
    
    if not xlsx_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Excel report not found for run_id: {run_id}"
        )
    
    return FileResponse(
        path=str(xlsx_path),
        filename=f"{run_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/reports")
async def list_reports(
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> dict:
    """
    List available reports.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        List of available report files
    """
    try:
        reports_dir = get_reports_dir()
        json_files = list(reports_dir.glob("*.json"))
        xlsx_files = list(reports_dir.glob("*.xlsx"))
        
        reports = []
        
        # Group by run_id
        run_ids = set()
        for file_path in json_files + xlsx_files:
            run_id = file_path.stem
            run_ids.add(run_id)
        
        for run_id in sorted(run_ids):
            json_exists = (reports_dir / f"{run_id}.json").exists()
            xlsx_exists = (reports_dir / f"{run_id}.xlsx").exists()
            
            reports.append({
                "run_id": run_id,
                "json_available": json_exists,
                "xlsx_available": xlsx_exists,
                "json_url": f"/orchestrator/report/{run_id}.json" if json_exists else None,
                "xlsx_url": f"/orchestrator/report/{run_id}.xlsx" if xlsx_exists else None
            })
        
        return {
            "reports": reports,
            "total_count": len(reports)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list reports: {str(e)}"
        )
