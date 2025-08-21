"""FastAPI RAG service main application."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
import os

from .rag_pipeline import RAGPipeline
from .config import config

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
    Answer a question using RAG pipeline.
    
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
    
    try:
        # Process query
        result = rag_pipeline.query(request.query)
        
        return QueryResponse(
            answer=result["answer"],
            context=result["context"]
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
