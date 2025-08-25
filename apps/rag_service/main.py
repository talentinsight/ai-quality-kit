"""FastAPI RAG service main application."""

from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import os
import time

from .rag_pipeline import RAGPipeline
from .config import config, resolve_provider_and_model, ALLOWED_PROVIDERS
from apps.utils.hash_utils import query_hash
from apps.cache.cache_store import get_cached, set_cache, get_cache_ttl, get_context_version
from apps.observability.log_service import start_log, finish_log, log_eval_metrics, audit_start, audit_finish
from apps.observability.live_eval import evaluate_comprehensive
from apps.observability.perf import decide_phase_and_latency, record_latency
from apps.security.auth import get_principal, require_user_or_admin, Principal
from apps.security.rate_limit import rate_limit_middleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Quality Kit - RAG Service",
    description="Retrieval-Augmented Generation service for quality evaluation",
    version="1.0.0"
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Run-ID"],  # Allow frontend to read this header
)

# Request/Response models
class QueryRequest(BaseModel):
    """Request model for /ask endpoint."""
    query: str
    provider: Optional[str] = None
    model: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    context: List[str]
    provider: str
    model: str

# Global RAG pipeline instance
rag_pipeline: Optional[RAGPipeline] = None


@app.on_event("startup")
async def startup_event():
    """Initialize RAG pipeline on startup."""
    global rag_pipeline
    
    try:
        # Validate configuration
        config.validate()
        
        # Initialize RAG pipeline
        rag_pipeline = RAGPipeline(
            model_name=config.model_name,
            top_k=config.rag_top_k
        )
        
        # Build index from passages
        passages_path = "data/golden/passages.jsonl"
        if not os.path.exists(passages_path):
            logger.error(f"Passages file not found: {passages_path}")
            raise FileNotFoundError(f"Passages file not found: {passages_path}")
        
        rag_pipeline.build_index_from_passages(passages_path)
        logger.info("RAG pipeline initialized successfully")
        
        # Start testdata store cleanup task
        from apps.testdata.store import start_store
        await start_store()
        logger.info("Test data store initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Quality Kit RAG Service is running"}


@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Kubernetes-style readiness check."""
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    return {"status": "ready"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "model": config.model_name,
        "provider": config.provider,
        "top_k": config.rag_top_k,
        "allowed_providers": list(ALLOWED_PROVIDERS),
        "index_size": len(rag_pipeline.passages) if rag_pipeline else 0
    }


@app.post("/ask", response_model=QueryResponse)
async def ask(
    request: QueryRequest, 
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> QueryResponse:
    """
    Answer a question using RAG pipeline with caching, logging, and live evaluation.
    
    Args:
        request: Query request containing the question and optional provider/model
        response: FastAPI response object for setting headers
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Response with answer and context passages
    """
    if not rag_pipeline:
        raise HTTPException(
            status_code=500,
            detail="RAG pipeline not initialized"
        )
    
    start_time = time.perf_counter()
    log_id = None
    audit_id = None
    
    try:
        # Validate and resolve provider/model
        try:
            provider, model = resolve_provider_and_model(request.provider, request.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Start audit logging if enabled
        audit_id = audit_start(
            "/ask", 
            "POST", 
            principal.role if principal else None,
            principal.token_hash_prefix if principal else None
        )
        
        # Normalize and hash query
        query_text = request.query
        query_hash_value = query_hash(query_text)
        context_version = get_context_version()
        
        # Check cache first (cache key includes provider/model for consistency)
        cache_key = f"{query_hash_value}_{provider}_{model}"
        cached_response = get_cached(cache_key, context_version)
        
        if cached_response:
            # Cache HIT
            answer = cached_response["answer"]
            context = cached_response["context"]
            source = "cache"
            
            # Log cache hit if enabled
            if log_id is None:
                log_id = start_log(query_text, query_hash_value, context, source)
            
            # Set performance headers
            phase, latency_ms = decide_phase_and_latency(start_time)
            response.headers["X-Source"] = source
            response.headers["X-Perf-Phase"] = phase
            response.headers["X-Latency-MS"] = str(latency_ms)
            
            # Add percentile headers if enabled
            p50, p95 = record_latency("/ask", latency_ms)
            if p50 is not None:
                response.headers["X-P50-MS"] = str(p50)
            if p95 is not None:
                response.headers["X-P95-MS"] = str(p95)
            
            finish_log(log_id, answer, latency_ms)
            
            # Complete audit logging
            if audit_id:
                audit_finish(audit_id, 200, latency_ms, phase == "cold")
            
            return QueryResponse(answer=answer, context=context, provider=provider, model=model)
        
        # Cache MISS - generate live response
        source = "live"
        
        # Start logging if enabled
        log_id = start_log(query_text, query_hash_value, [], source)
        
        # Retrieve context
        contexts = rag_pipeline.retrieve(query_text)
        
        # Generate answer with provider/model override
        answer = rag_pipeline.answer(query_text, contexts, provider, model)
        
        # Cache the response if enabled
        try:
            ttl_seconds = get_cache_ttl()
            set_cache(cache_key, context_version, answer, contexts, ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")
        
        # Live evaluation if enabled
        try:
            eval_metrics = evaluate_comprehensive(query_text, contexts, answer)
            if eval_metrics and log_id:
                log_eval_metrics(log_id, "ragas", eval_metrics)
        except Exception as e:
            logger.warning(f"Live evaluation failed: {e}")
        
        # Set performance headers
        phase, latency_ms = decide_phase_and_latency(start_time)
        response.headers["X-Source"] = source
        response.headers["X-Perf-Phase"] = phase
        response.headers["X-Latency-MS"] = str(latency_ms)
        
        # Add percentile headers if enabled
        p50, p95 = record_latency("/ask", latency_ms)
        if p50 is not None:
            response.headers["X-P50-MS"] = str(p50)
        if p95 is not None:
            response.headers["X-P95-MS"] = str(p95)
        
        # Complete logging
        finish_log(log_id, answer, latency_ms)
        
        # Complete audit logging
        if audit_id:
            audit_finish(audit_id, 200, latency_ms, phase == "cold")
        
        return QueryResponse(answer=answer, context=contexts, provider=provider, model=model)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log error if logging enabled
        if log_id:
            phase, latency_ms = decide_phase_and_latency(start_time)
            finish_log(log_id, "", latency_ms, "error", str(e))
        
        # Complete audit logging with error
        if audit_id:
            phase, latency_ms = decide_phase_and_latency(start_time)
            audit_finish(audit_id, 500, latency_ms, phase == "cold")
        
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


# Include routers
def setup_routers():
    """Setup additional routers based on feature flags."""
    # Always include orchestrator
    from apps.orchestrator.router import router as orchestrator_router
    app.include_router(orchestrator_router)
    
    # Always include test data intake
    from apps.testdata.router import router as testdata_router
    app.include_router(testdata_router)
    
    # Include A2A if enabled
    a2a_enabled = os.getenv("A2A_ENABLED", "true").lower() == "true"
    if a2a_enabled:
        from apps.a2a.api import router as a2a_router
        app.include_router(a2a_router)


# Setup routers on startup
@app.on_event("startup")
async def setup_additional_routers():
    """Setup additional routers after main startup."""
    setup_routers()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
