"""FastAPI RAG service main application."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
import os
import time

from .rag_pipeline import RAGPipeline
from .config import config
from apps.utils.hash_utils import query_hash
from apps.cache.cache_store import get_cached, set_cache, get_cache_ttl, get_context_version
from apps.observability.log_service import start_log, finish_log, log_eval_metrics
from apps.observability.live_eval import evaluate_comprehensive

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Quality Kit - RAG Service",
    description="Retrieval-Augmented Generation service for quality evaluation",
    version="1.0.0"
)

# Request/Response models
class QueryRequest(BaseModel):
    """Request model for /ask endpoint."""
    query: str

class QueryResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    context: List[str]

# Global RAG pipeline instance
rag_pipeline: RAGPipeline = None


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
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Quality Kit RAG Service is running"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "model": config.model_name,
        "provider": config.provider,
        "top_k": config.rag_top_k,
        "index_size": len(rag_pipeline.passages) if rag_pipeline else 0
    }


@app.post("/ask", response_model=QueryResponse)
async def ask(request: QueryRequest) -> QueryResponse:
    """
    Answer a question using RAG pipeline with caching, logging, and live evaluation.
    
    Args:
        request: Query request containing the question
        
    Returns:
        Response with answer and context passages
    """
    if not rag_pipeline:
        raise HTTPException(
            status_code=500,
            detail="RAG pipeline not initialized"
        )
    
    start_time = time.time()
    log_id = None
    
    try:
        # Normalize and hash query
        query_text = request.query
        query_hash_value = query_hash(query_text)
        context_version = get_context_version()
        
        # Check cache first
        cached_response = get_cached(query_hash_value, context_version)
        
        if cached_response:
            # Cache HIT
            answer = cached_response["answer"]
            context = cached_response["context"]
            source = "cache"
            
            # Log cache hit if enabled
            if log_id is None:
                log_id = start_log(query_text, query_hash_value, context, source)
            
            latency_ms = int((time.time() - start_time) * 1000)
            finish_log(log_id, answer, latency_ms)
            
            return QueryResponse(answer=answer, context=context)
        
        # Cache MISS - generate live response
        source = "live"
        
        # Start logging if enabled
        log_id = start_log(query_text, query_hash_value, [], source)
        
        # Retrieve context
        contexts = rag_pipeline.retrieve(query_text)
        
        # Generate answer
        generation_start = time.time()
        result = rag_pipeline.query(query_text)
        generation_time = time.time() - generation_start
        
        answer = result["answer"]
        context = result["context"]
        
        # Cache the response if enabled
        try:
            ttl_seconds = get_cache_ttl()
            set_cache(query_hash_value, context_version, answer, context, ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")
        
        # Live evaluation if enabled
        try:
            eval_metrics = evaluate_comprehensive(query_text, contexts, answer)
            if eval_metrics and log_id:
                log_eval_metrics(log_id, "ragas", eval_metrics)
        except Exception as e:
            logger.warning(f"Live evaluation failed: {e}")
        
        # Complete logging
        latency_ms = int((time.time() - start_time) * 1000)
        finish_log(log_id, answer, latency_ms)
        
        return QueryResponse(answer=answer, context=context)
        
    except Exception as e:
        # Log error if logging enabled
        if log_id:
            latency_ms = int((time.time() - start_time) * 1000)
            finish_log(log_id, "", latency_ms, "error", str(e))
        
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
