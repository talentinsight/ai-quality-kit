"""RAG Pipeline implementation with FAISS indexing."""

import json
import numpy as np
from typing import List, Dict, Any, Optional
import faiss
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from llm.provider import get_chat
from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline with FAISS indexing."""
    
    def __init__(self, model_name: str, top_k: int = 4):
        """
        Initialize RAG pipeline.
        
        Args:
            model_name: Name of the LLM model to use
            top_k: Number of top passages to retrieve
        """
        self.model_name = model_name
        self.top_k = top_k
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                # Try newer API first
                self.embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small"  # Cost-effective embedding model
                )
            except Exception:
                try:
                    # Fallback for older API versions
                    self.embeddings = OpenAIEmbeddings(
                        openai_api_key=api_key,  # type: ignore # Use the older parameter name for compatibility
                        model="text-embedding-3-small"
                    )
                except Exception:
                    # Final fallback
                    self.embeddings = None
        else:
            # Fallback for when no API key is available
            self.embeddings = None
        self.chat = get_chat()
        self.index: Optional[faiss.IndexFlatIP] = None
        self.passages: List[Dict[str, Any]] = []
        self.passage_texts: List[str] = []
        
    def build_index_from_passages(self, path: str) -> None:
        """
        Build FAISS index from passages file.
        
        Args:
            path: Path to JSONL file containing passages
        """
        # Load passages
        self.passages = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    passage = json.loads(line)
                    self.passages.append(passage)
        
        if not self.passages:
            raise ValueError(f"No passages found in {path}")
        
        # Extract texts
        self.passage_texts = [passage['text'] for passage in self.passages]
        
        # Generate embeddings
        if self.embeddings is None:
            raise ValueError("OpenAI API key not configured - cannot generate embeddings")
        embeddings_list = self.embeddings.embed_documents(self.passage_texts)
        embeddings_array = np.array(embeddings_list, dtype=np.float32)
        
        # Create FAISS index (Inner Product for cosine similarity)
        dimension = embeddings_array.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings_array)  # type: ignore
        self.index.add(embeddings_array)  # type: ignore
        
        print(f"Built FAISS index with {len(self.passages)} passages")
    
    def retrieve(self, query: str) -> List[str]:
        """
        Retrieve top-k relevant passages for a query.
        
        Args:
            query: User query string
            
        Returns:
            List of retrieved passage texts
        """
        if self.index is None:
            raise RuntimeError("Index not built. Call build_index_from_passages() first.")
        
        # Generate query embedding
        if self.embeddings is None:
            raise ValueError("OpenAI API key not configured - cannot generate embeddings")
        query_embedding = self.embeddings.embed_query(query)
        query_vector = np.array([query_embedding], dtype=np.float32)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(query_vector)  # type: ignore
        
        # Search
        scores, indices = self.index.search(query_vector, self.top_k)  # type: ignore
        
        # Return relevant passages
        retrieved_texts = []
        for idx in indices[0]:
            if idx < len(self.passage_texts):
                retrieved_texts.append(self.passage_texts[idx])
        
        return retrieved_texts
    
    def answer(self, query: str, context: List[str], provider: Optional[str] = None, model: Optional[str] = None) -> str:
        """
        Generate answer using LLM with retrieved context.
        
        Args:
            query: User query
            context: List of retrieved passage texts
            provider: Optional provider override
            model: Optional model override
            
        Returns:
            Generated answer
        """
        # Format context
        context_text = "\n\n".join([f"Passage {i+1}: {text}" for i, text in enumerate(context)])
        
        # Create user message with context
        user_message = f"""Question: {query}

Context:
{context_text}

Please answer the question based only on the provided context."""
        
        # Get chat function with provider/model override
        if provider or model:
            from llm.provider import get_chat_for
            chat_fn = get_chat_for(provider, model)
        else:
            chat_fn = self.chat
        
        # Call LLM
        messages = [CONTEXT_ONLY_ANSWERING_PROMPT, user_message]
        response = chat_fn(messages)
        
        return response.strip()
    
    def query(self, query: str) -> Dict[str, Any]:
        """
        End-to-end query processing: retrieve + answer.
        
        Args:
            query: User query
            
        Returns:
            Dictionary with answer and context
        """
        context = self.retrieve(query)
        answer = self.answer(query, context)
        
        return {
            "answer": answer,
            "context": context
        }
