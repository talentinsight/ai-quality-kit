"""
FastAPI router for dataset validation and management endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Response, Body
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path
from pydantic import BaseModel

from apps.security.auth import require_user_or_admin, Principal
from apps.orchestrator.suites.red_team.attack_loader import validate_attacks_file_content
from apps.orchestrator.suites.red_team.attacks_schemas import AttacksValidationResult
from apps.orchestrator.suites.safety.loader import validate_safety_content
from apps.orchestrator.suites.safety.schemas import SafetyValidationResult
from apps.orchestrator.suites.bias.loader import validate_bias_content
from apps.orchestrator.suites.bias.schemas import BiasValidationResult
from apps.orchestrator.suites.performance.loader import validate_perf_content
from apps.orchestrator.suites.performance.schemas import PerfValidationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])


class AttacksValidationRequest(BaseModel):
    content: str


class SafetyValidationRequest(BaseModel):
    content: str


class BiasValidationRequest(BaseModel):
    content: str


class PerfValidationRequest(BaseModel):
    content: str


@router.post("/red_team/validate", response_model=AttacksValidationResult)
async def validate_red_team_attacks(
    request: AttacksValidationRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Validate Red Team attacks content and return validation results.
    
    Args:
        content: YAML or JSON content as string
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        AttacksValidationResult with validation status and metadata
    """
    try:
        # Validate the attacks content
        validation_result = validate_attacks_file_content(request.content)
        
        # Log validation attempt
        logger.info(f"Red Team attacks validation: valid={validation_result.valid}, "
                   f"format={validation_result.format}, "
                   f"categories={len(validation_result.taxonomy)}, "
                   f"total_attacks={sum(validation_result.counts_by_category.values())}")
        
        if validation_result.errors:
            logger.warning(f"Attacks validation errors: {validation_result.errors}")
        
        if validation_result.warnings:
            logger.info(f"Attacks validation warnings: {validation_result.warnings}")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Attacks validation failed with exception: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Attacks validation failed: {str(e)}"
        )


@router.post("/safety/validate", response_model=SafetyValidationResult)
async def validate_safety_dataset(
    request: SafetyValidationRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Validate Safety dataset content (YAML, JSON, or JSONL format).
    
    Args:
        request: Request containing safety dataset content
        principal: Authenticated user principal
        
    Returns:
        SafetyValidationResult with validation details
    """
    try:
        # Validate the safety dataset content
        validation_result = validate_safety_content(request.content)
        
        # Log validation attempt
        logger.info(f"Safety dataset validation: valid={validation_result.valid}, "
                   f"format={validation_result.format}, "
                   f"categories={len(validation_result.taxonomy)}, "
                   f"total_cases={sum(validation_result.counts_by_category.values())}")
        
        if validation_result.errors:
            logger.warning(f"Safety validation errors: {validation_result.errors}")
        
        if validation_result.warnings:
            logger.info(f"Safety validation warnings: {validation_result.warnings}")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Safety validation failed with exception: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Safety validation failed: {str(e)}"
        )


@router.post("/bias/validate", response_model=BiasValidationResult)
async def validate_bias_dataset(
    request: BiasValidationRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Validate Bias dataset content (YAML, JSON, or JSONL format).
    
    Args:
        request: Request containing bias dataset content
        principal: Authenticated user principal
        
    Returns:
        BiasValidationResult with validation details
    """
    try:
        # Validate the bias dataset content
        validation_result = validate_bias_content(request.content)
        
        # Log validation attempt
        logger.info(f"Bias dataset validation: valid={validation_result.valid}, "
                   f"format={validation_result.format}, "
                   f"categories={len(validation_result.taxonomy)}, "
                   f"total_cases={sum(validation_result.counts_by_category.values())}")
        
        if validation_result.errors:
            logger.warning(f"Bias validation errors: {validation_result.errors}")
        
        if validation_result.warnings:
            logger.info(f"Bias validation warnings: {validation_result.warnings}")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Bias validation failed with exception: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Bias validation failed: {str(e)}"
        )


@router.get("/red_team/template")
async def download_red_team_suite_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Download Red Team suite template file.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        File download response
    """
    try:
        template_path = Path(__file__).parent.parent.parent / "data" / "templates" / "attacks.suite.yaml"
        
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Red Team suite template not found")
        
        return FileResponse(
            path=str(template_path),
            filename="attacks.suite.yaml",
            media_type="application/x-yaml"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Red Team suite template: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve template")


@router.get("/bias/template/yaml")
async def download_bias_yaml_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Download Bias YAML template file.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        File download response
    """
    try:
        template_path = Path(__file__).parent.parent.parent / "data" / "templates" / "bias.yaml"
        
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Bias YAML template not found")
        
        return FileResponse(
            path=str(template_path),
            filename="bias_template.yaml",
            media_type="application/x-yaml"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Bias YAML template: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve template")


@router.get("/bias/template/json")
async def download_bias_json_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Download Bias JSON template file.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        File download response
    """
    try:
        template_path = Path(__file__).parent.parent.parent / "data" / "templates" / "bias.json"
        
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Bias JSON template not found")
        
        return FileResponse(
            path=str(template_path),
            filename="bias_template.json",
            media_type="application/json"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Bias JSON template: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve template")


@router.post("/performance/validate", response_model=PerfValidationResult)
async def validate_performance_dataset(
    request: PerfValidationRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Validate performance dataset content.
    
    Args:
        request: Performance validation request with content
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        PerfValidationResult with validation details
    """
    try:
        logger.info("Validating performance dataset content")
        
        result = validate_perf_content(request.content)
        
        logger.info(f"Performance dataset validation: valid={result.valid}, format={result.format}, "
                   f"categories={len(result.counts_by_category)}, total_scenarios={sum(result.counts_by_category.values())}")
        
        if result.warnings:
            logger.warning(f"Performance validation warnings: {result.warnings}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error validating performance dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/performance/template/yaml")
async def download_perf_yaml_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Download Performance YAML template file.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        FileResponse with YAML template
    """
    try:
        template_path = Path("data/templates/perf.yaml")
        
        if not template_path.exists():
            logger.error(f"Performance YAML template not found at {template_path}")
            raise HTTPException(status_code=404, detail="Performance YAML template not found")
        
        return FileResponse(
            path=str(template_path),
            filename="perf_template.yaml",
            media_type="text/yaml"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Performance YAML template: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve template")


@router.get("/performance/template/json")
async def download_perf_json_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Download Performance JSON template file.
    
    Args:
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        FileResponse with JSON template
    """
    try:
        template_path = Path("data/templates/perf.json")
        
        if not template_path.exists():
            logger.error(f"Performance JSON template not found at {template_path}")
            raise HTTPException(status_code=404, detail="Performance JSON template not found")
        
        return FileResponse(
            path=str(template_path),
            filename="perf_template.json",
            media_type="application/json"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Performance JSON template: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve template")
