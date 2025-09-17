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
from apps.cache.cache_store import get_cached, set_cache, get_cache_ttl, get_context_version, get_cache_stats
from apps.observability.log_service import start_log, finish_log, log_eval_metrics, audit_start, audit_finish
from apps.observability.live_eval import evaluate_comprehensive
from apps.observability.perf import decide_phase_and_latency, record_latency
from apps.security.auth import get_principal, require_user_or_admin, Principal
from apps.security.rate_limit import rate_limit_middleware

# Orchestrator functionality will be imported dynamically

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Quality Kit - RAG Service",
    description="Retrieval-Augmented Generation service for quality evaluation",
    version="1.0.0"
)

# Install exception handlers for consistent error responses
from apps.common.http_handlers import install_exception_handlers
install_exception_handlers(app)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Frontend URLs
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
    testdata_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    context: List[str]
    provider: str
    model: str

# Global RAG pipeline instance
rag_pipeline: Optional[RAGPipeline] = None


async def retrieve_with_testdata(query: str, testdata_id: str) -> List[str]:
    """Retrieve contexts using uploaded test data passages."""
    try:
        logger.info(f"🔍 RETRIEVE_WITH_TESTDATA: Starting with testdata_id={testdata_id}")
        
        # Get test data bundle
        from apps.testdata.store import get_store
        store = get_store()
        bundle = store.get_bundle(testdata_id)
        
        logger.info(f"🔍 RETRIEVE_WITH_TESTDATA: Bundle found={bundle is not None}")
        if bundle:
            logger.info(f"🔍 RETRIEVE_WITH_TESTDATA: Bundle has passages={hasattr(bundle, 'passages') and bundle.passages is not None}")
            if hasattr(bundle, 'passages') and bundle.passages:
                logger.info(f"🔍 RETRIEVE_WITH_TESTDATA: Passages count={len(bundle.passages)}")
        
        if not bundle or not bundle.passages:
            logger.warning(f"No passages found in testdata bundle {testdata_id}, falling back to default")
            return rag_pipeline.retrieve(query) if rag_pipeline else []
        
        # Create temporary RAG pipeline with uploaded passages
        from apps.rag_service.rag_pipeline import RAGPipeline
        temp_pipeline = RAGPipeline(
            model_name=config.model_name,
            top_k=config.rag_top_k
        )
        
        # Build index from uploaded passages
        passages_data = []
        for passage in bundle.passages:
            passages_data.append({
                "id": passage.id,
                "text": passage.text
            })
        
        temp_pipeline.build_index_from_data(passages_data)
        logger.info(f"Built temporary index with {len(passages_data)} uploaded passages")
        
        # Retrieve contexts
        contexts = temp_pipeline.retrieve(query)
        return contexts
        
    except Exception as e:
        logger.error(f"Failed to retrieve with testdata {testdata_id}: {e}")
        # Fall back to default pipeline
        return rag_pipeline.retrieve(query) if rag_pipeline else []


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
        
        # Run intake janitor cleanup on startup
        try:
            from apps.orchestrator.intake.storage import janitor_clean_old
            from pathlib import Path
            reports_dir = Path(os.getenv("REPORTS_DIR", "./reports"))
            deleted_count = janitor_clean_old(reports_dir, hours=24)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old test data bundles")
        except Exception as e:
            logger.warning(f"Failed to run intake janitor: {e}")
        
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


@app.get("/cache/stats")
async def cache_stats(principal: Optional[Principal] = Depends(require_user_or_admin())):
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return {
            "cache_type": "in_memory",
            "snowflake_available": False,  # We disabled it
            **stats
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")


@app.get("/config")
async def get_config():
    """Get application configuration for frontend."""
    from apps.settings import settings
    return settings.get_powerbi_config_dict()


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
        
        # Use custom passages if testdata_id provided AND not using mock provider
        logger.info(f"🔍 ASK ENDPOINT: testdata_id={request.testdata_id}, provider={provider}")
        if request.testdata_id and provider != "mock":
            logger.info(f"🔍 ASK ENDPOINT: Using uploaded data for provider={provider}")
            contexts = await retrieve_with_testdata(query_text, request.testdata_id)
        else:
            # Use default pipeline for mock provider or when no testdata_id
            logger.info(f"🔍 ASK ENDPOINT: Using default data (provider={provider}, testdata_id={request.testdata_id})")
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
    
    # Mount static files for orchestrator (HTML reports)
    try:
        from fastapi.staticfiles import StaticFiles
        from pathlib import Path
        static_dir = Path("apps/orchestrator/static")
        if static_dir.exists():
            app.mount("/orchestrator/static", StaticFiles(directory=str(static_dir)), name="orchestrator_static")
    except Exception as e:
        logger.warning(f"Failed to mount orchestrator static files: {e}")
    
    # Include guardrails router and new testdata intake first (Phase 3.1)
    try:
        from apps.api.routes.guardrails import router as guardrails_router
        app.include_router(guardrails_router)
        logger.info("Guardrails router included successfully")
        
        # Include testdata intake router (Phase 3.1) - FIRST to take precedence
        from apps.api.routes.testdata_intake import router as testdata_intake_router
        app.include_router(testdata_intake_router)
        logger.info("Testdata intake router included successfully")
    except Exception as e:
        logger.warning(f"Failed to include guardrails router: {e}")
    
    # Include legacy test data intake (with different prefix to avoid conflicts)
    from apps.testdata.router import router as legacy_testdata_router
    # Change prefix to avoid conflict with new testdata intake
    legacy_testdata_router.prefix = "/legacy-testdata"
    app.include_router(legacy_testdata_router)
    
    # Include datasets router for validation endpoints
    from apps.datasets.router import router as datasets_router
    app.include_router(datasets_router)
    
    # Include orchestrator test data intake
    from apps.orchestrator.router_testdata import router as orchestrator_testdata_router
    app.include_router(orchestrator_testdata_router)
    
    # Include A2A if enabled
    a2a_enabled = os.getenv("A2A_ENABLED", "true").lower() == "true"
    if a2a_enabled:
        from apps.a2a.api import router as a2a_router
        app.include_router(a2a_router)


# MCP Tools Discovery Models
class MCPToolsRequest(BaseModel):
    """Request model for MCP tools discovery."""
    endpoint: str
    auth: Optional[Dict[str, Any]] = None

class MCPToolsResponse(BaseModel):
    """Response model for MCP tools discovery."""
    tools: List[Dict[str, Any]]
    error: Optional[str] = None

@app.post("/mcp/tools", response_model=MCPToolsResponse)
async def discover_mcp_tools(
    request: MCPToolsRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> MCPToolsResponse:
    """Discover available tools from an MCP server."""
    try:
        # Import MCP client
        from apps.orchestrator.mcp_client import MCPClient
        
        # Create MCP client
        mcp_client = MCPClient(
            endpoint=request.endpoint,
            auth=request.auth,
            timeouts={"connect_ms": 5000, "call_ms": 10000}
        )
        
        # Connect and list tools
        await mcp_client.connect()
        tools = await mcp_client.list_tools()
        await mcp_client.close()
        
        # Convert to dict format
        tools_data = []
        for tool in tools:
            tools_data.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "outputSchema": tool.output_schema
            })
        
        return MCPToolsResponse(tools=tools_data)
        
    except Exception as e:
        logger.error(f"MCP tools discovery failed: {e}")
        return MCPToolsResponse(tools=[], error=str(e))

# Setup routers on startup
@app.on_event("startup")
async def setup_additional_routers():
    """Setup additional routers after main startup."""
    setup_routers()
    
    # Add real orchestrator endpoint
    @app.post("/orchestrator/run_tests")
    async def run_tests_endpoint(request: dict):
        """Real orchestrator endpoint with Universal RAG Evaluation."""
        try:
            import subprocess
            import json
            import tempfile
            import os
            
            # Write request to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(request, f)
                temp_file = f.name
            
            try:
                # Run orchestrator as subprocess
                orchestrator_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestrator')
                cmd = [
                    sys.executable, '-c',
                    f'''
import sys
import os
import json
sys.path.insert(0, "{orchestrator_dir}")
os.chdir("{orchestrator_dir}")

# Fix relative imports
import importlib.util
spec = importlib.util.spec_from_file_location("run_tests", "{orchestrator_dir}/run_tests.py")
run_tests_module = importlib.util.module_from_spec(spec)
sys.modules["run_tests"] = run_tests_module
spec.loader.exec_module(run_tests_module)

# Load request
with open("{temp_file}", "r") as f:
    request_data = json.load(f)

# Run tests
runner = run_tests_module.TestRunner()
result = runner.run_tests(request_data)
print(json.dumps(result))
                    '''
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # Parse JSON output
                    output_lines = result.stdout.strip().split('\\n')
                    json_line = output_lines[-1]  # Last line should be JSON
                    return json.loads(json_line)
                else:
                    logger.error(f"Orchestrator subprocess failed: {result.stderr}")
                    raise Exception(f"Subprocess failed: {result.stderr}")
                    
            finally:
                # Cleanup temp file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("🎯 Real orchestrator endpoint with Universal RAG added successfully")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
