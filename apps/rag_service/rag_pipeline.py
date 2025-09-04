"""RAG Pipeline implementation with scikit-learn for vector search."""

import json
import numpy as np
from typing import List, Dict, Any, Optional
# import faiss  # Removed - compatibility issues with Python 3.13
# from sentence_transformers import SentenceTransformer, util  # Removed - PyTorch dependency
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from llm.provider import get_chat
from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline with scikit-learn TF-IDF indexing."""
    
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
        # self.index: Optional[faiss.IndexFlatIP] = None  # Removed FAISS index
        self.passages: List[Dict[str, Any]] = []
        self.passage_texts: List[str] = []
        self.passage_embeddings: Optional[np.ndarray] = None
        
        # Initialize TF-IDF vectorizer for local text similarity (fallback)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=10000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = None
        
    def build_index_from_passages(self, path: str) -> None:
        """
        Build vector index from passages file using scikit-learn TF-IDF.
        
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
        if self.embeddings is not None:
            # Use OpenAI embeddings if available
            try:
                embeddings_list = self.embeddings.embed_documents(self.passage_texts)
                self.passage_embeddings = np.array(embeddings_list, dtype=np.float32)
                print("Using OpenAI embeddings")
            except Exception as e:
                print(f"OpenAI embeddings failed: {e}, falling back to TF-IDF")
                self.passage_embeddings = None
        
        if self.passage_embeddings is None:
            # Fallback to TF-IDF vectorization
            try:
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.passage_texts)
                print("Using TF-IDF vectorization")
            except Exception as e:
                raise ValueError(f"Failed to create TF-IDF vectors: {e}")
        
        if self.passage_embeddings is None and self.tfidf_matrix is None:
            raise ValueError("No indexing method available - cannot build index")
        
        # Normalize OpenAI embeddings for cosine similarity
        if self.passage_embeddings is not None:
            self.passage_embeddings = self.passage_embeddings / np.linalg.norm(
                self.passage_embeddings, axis=1, keepdims=True
            )
        
        print(f"Built vector index with {len(self.passages)} passages using scikit-learn")
    
    def retrieve(self, query: str) -> List[str]:
        """
        Retrieve top-k relevant passages for a query.
        
        Args:
            query: User query string
            
        Returns:
            List of top-k relevant passage texts
        """
        if self.passage_embeddings is None and self.tfidf_matrix is None:
            raise ValueError("Index not built - call build_index_from_passages first")
        
        # Generate query embedding/vector
        if self.embeddings is not None and self.passage_embeddings is not None:
            try:
                query_embedding = self.embeddings.embed_query(query)
                query_embedding = np.array(query_embedding, dtype=np.float32)
                
                # Normalize query embedding
                query_embedding = query_embedding / np.linalg.norm(query_embedding)
                
                # Calculate cosine similarities
                similarities = np.dot(self.passage_embeddings, query_embedding)
                
            except Exception:
                # Fallback to TF-IDF
                if self.tfidf_matrix is not None:
                    query_vector = self.tfidf_vectorizer.transform([query])
                    similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
                else:
                    raise ValueError("No embedding method available")
        else:
            # Use TF-IDF similarity
            if self.tfidf_matrix is not None:
                query_vector = self.tfidf_vectorizer.transform([query])
                similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            else:
                raise ValueError("No indexing method available")
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:self.top_k]
        
        # Ensure indices are within bounds
        valid_indices = [i for i in top_indices if 0 <= i < len(self.passage_texts)]
        
        # Return top-k passages
        return [self.passage_texts[i] for i in valid_indices]
    
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
