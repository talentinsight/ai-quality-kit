"""FastAPI router for orchestrator endpoints."""

import os
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request, Response, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional

from .run_tests import OrchestratorRequest, OrchestratorResult, OrchestratorPlan, TestRunner
from apps.security.auth import require_user_or_admin, Principal, _get_client_ip
from apps.audit import audit_orchestrator_run_started, audit_orchestrator_run_finished, audit_request_accepted
from pydantic import BaseModel

class OrchestratorStartResponse(BaseModel):
    """Immediate response when test starts."""
    run_id: str
    status: str
    message: str

async def run_tests_background(runner: TestRunner, actor: str):
    """Background task to run tests."""
    try:
        # Run the actual tests
        result = await runner.run_all_tests()
        
        # Audit completion
        audit_orchestrator_run_finished(
            run_id=runner.run_id,
            suites=list(runner.request.suites),
            provider=runner.request.provider,
            model=runner.request.model,
            actor=actor,
            duration_ms=(time.time() - _running_tests[runner.run_id]["start_time"]) * 1000,
            success=True,
            testdata_id=runner.request.testdata_id
        )
        
        print(f"✅ BACKGROUND: Test {runner.run_id} completed successfully")
        
    except Exception as e:
        print(f"❌ BACKGROUND: Test {runner.run_id} failed: {e}")
        audit_orchestrator_run_finished(
            run_id=runner.run_id,
            suites=list(runner.request.suites),
            provider=runner.request.provider,
            model=runner.request.model,
            actor=actor,
            duration_ms=(time.time() - _running_tests[runner.run_id]["start_time"]) * 1000,
            success=False,
            testdata_id=runner.request.testdata_id,
            error=str(e)
        )
    finally:
        # Clean up
        if runner.run_id in _running_tests:
            del _running_tests[runner.run_id]

# Create router
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

def get_reports_dir() -> Path:
    """Get reports directory path from environment."""
    reports_dir = Path(os.getenv("REPORTS_DIR", "./reports"))
    reports_dir.mkdir(exist_ok=True)
    return reports_dir


@router.post("/run_tests")
async def run_tests(
    http_request: Request,
    request: OrchestratorRequest,
    dry_run: bool = False,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Run multiple test suites and generate reports, or create a test plan.
    
    Args:
        http_request: FastAPI request object for audit logging
        request: Orchestrator request with test configuration
        dry_run: If True, return a test plan instead of executing tests
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Orchestrator result with run ID and artifact paths, or test plan if dry_run=True
    """
    start_time = time.time()
    actor = principal.token_hash_prefix if principal else "anonymous"
    client_ip = _get_client_ip(http_request)
    
    # Audit request acceptance
    audit_request_accepted(
        route="/orchestrator/run_tests",
        actor=actor,
        ip=client_ip
    )
    
    try:
        # Create test runner
        runner = TestRunner(request)
        
        # Handle dry run (planning)
        if dry_run:
            plan = runner.create_test_plan()
            return plan
        
        # Register running test
        _running_tests[runner.run_id] = {
            "cancelled": False,
            "start_time": start_time,
            "runner": runner
        }
        
        print(f"🆔 BACKEND: Starting test {runner.run_id}")
        
        # Audit run start
        audit_orchestrator_run_started(
            run_id=runner.run_id,
            suites=list(request.suites),
            provider=request.provider,
            model=request.model,
            actor=actor,
            testdata_id=request.testdata_id
        )
        
        # Run tests synchronously with cancel support
        try:
            result = await runner.run_all_tests()
            
            # Audit successful completion
            duration_ms = (time.time() - start_time) * 1000
            audit_orchestrator_run_finished(
                run_id=runner.run_id,
                suites=list(request.suites),
                provider=request.provider,
                model=request.model,
                actor=actor,
                duration_ms=duration_ms,
                success=True,
                testdata_id=request.testdata_id
            )
            
            return result
            
        except Exception as inner_e:
            error_msg = str(inner_e)
            
            # Check if this was a cancellation (graceful)
            if "CANCELLED:" in error_msg:
                print(f"✅ Graceful cancellation detected: {error_msg}")
                
                # Generate cancelled result instead of error
                result = runner._generate_cancelled_result()
                
                # Audit as successful cancellation
                duration_ms = (time.time() - start_time) * 1000
                audit_orchestrator_run_finished(
                    run_id=runner.run_id,
                    suites=list(request.suites),
                    provider=request.provider,
                    model=request.model,
                    actor=actor,
                    duration_ms=duration_ms,
                    success=True,  # Cancellation is success!
                    testdata_id=request.testdata_id
                )
                
                return result
            else:
                # Real error - audit as failure
                duration_ms = (time.time() - start_time) * 1000
                audit_orchestrator_run_finished(
                    run_id=runner.run_id,
                    suites=list(request.suites),
                    provider=request.provider,
                    model=request.model,
                    actor=actor,
                    duration_ms=duration_ms,
                    success=False,
                    testdata_id=request.testdata_id,
                    error=error_msg
                )
                raise inner_e
        finally:
            # Clean up
            _running_tests.pop(runner.run_id, None)
            
    except Exception as e:
        # Remove from running tests on outer error  
        if 'runner' in locals():
            _running_tests.pop(getattr(runner, 'run_id', None), None)
            
        # Audit failed completion
        duration_ms = (time.time() - start_time) * 1000
        audit_orchestrator_run_finished(
            run_id=getattr(runner, 'run_id', 'unknown') if 'runner' in locals() else 'unknown',
            suites=list(request.suites),
            provider=request.provider,
            model=request.model,
            actor=actor,
            duration_ms=duration_ms,
            success=False,
            testdata_id=request.testdata_id,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run tests: {str(e)}"
        )


@router.post("/start", response_model=OrchestratorStartResponse)
async def start_tests(
    http_request: Request,
    request: OrchestratorRequest,
    background: BackgroundTasks,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> OrchestratorStartResponse:
    """
    Start test execution in background and return immediately.
    
    Args:
        http_request: FastAPI request object for audit logging
        request: Orchestrator request with test configuration
        background: FastAPI background tasks
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Immediate response with run_id and status
    """
    start_time = time.time()
    actor = principal.token_hash_prefix if principal else "anonymous"
    client_ip = _get_client_ip(http_request)

    runner = TestRunner(request)
    _running_tests[runner.run_id] = {"cancelled": False, "start_time": time.time()}

    audit_request_accepted(
        route="/orchestrator/start",
        actor=actor,
        ip=client_ip
    )
    audit_orchestrator_run_started(run_id=runner.run_id, suites=list(request.suites), provider=request.provider, model=request.model, actor=actor)

    async def _bg():
        try:
            result = await runner.run_all_tests()
            _running_tests.pop(runner.run_id, None)
            audit_orchestrator_run_finished(run_id=runner.run_id, suites=list(request.suites), provider=request.provider, model=request.model, actor=actor, duration_ms=(time.time()-start_time)*1000, success=True, testdata_id=request.testdata_id)
        except Exception as e:
            _running_tests.pop(runner.run_id, None)
            audit_orchestrator_run_finished(run_id=runner.run_id, suites=list(request.suites), provider=request.provider, model=request.model, actor=actor, duration_ms=(time.time()-start_time)*1000, success=False, testdata_id=request.testdata_id, error=str(e))

    background.add_task(_bg)
    return OrchestratorStartResponse(run_id=runner.run_id, status="started", message="Run started in background")


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


@router.get("/report/{run_id}.html")
async def get_html_report(
    run_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> FileResponse:
    """
    Download HTML report for a test run.
    
    Args:
        run_id: Test run identifier
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        HTML file response
    """
    html_path = get_reports_dir() / f"{run_id}.html"
    
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"HTML report not found for run_id: {run_id}"
        )
    
    return FileResponse(
        path=str(html_path),
        filename=f"{run_id}.html",
        media_type="text/html"
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


# Global registry to track running tests
_running_tests = {}

@router.get("/running-tests")
async def list_running_tests(
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> dict:
    """Debug endpoint to list running tests."""
    return {
        "running_tests": list(_running_tests.keys()),
        "count": len(_running_tests),
        "details": {k: {"cancelled": v["cancelled"], "start_time": v["start_time"]} for k, v in _running_tests.items()}
    }

@router.post("/cancel/{run_id}")
async def cancel_test_run(
    run_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> dict:
    """Cancel a running test execution."""
    if run_id not in _running_tests:
        raise HTTPException(
            status_code=404,
            detail=f"Test run {run_id} not found or already completed. Running tests: {list(_running_tests.keys())}"
        )
    
    # Mark for cancellation
    _running_tests[run_id]["cancelled"] = True
    print(f"🔥 CANCEL ENDPOINT: Marked {run_id} for cancellation")
    
    return {
        "message": f"Test run {run_id} marked for cancellation",
        "run_id": run_id,
        "status": "cancelling"
    }
