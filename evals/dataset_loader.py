"""Dataset loading utilities for evaluations."""

import json
from typing import List, Dict, Any
from pathlib import Path


def load_qa(path: str) -> List[Dict[str, Any]]:
    """
    Load QA dataset from JSONL file.
    
    Args:
        path: Path to JSONL file containing QA pairs
        
    Returns:
        List of dictionaries with 'query' and 'answer' keys
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is empty or malformed
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"QA dataset file not found: {path}")
    
    qa_pairs = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    qa_item = json.loads(line)
                    
                    # Validate required fields
                    if 'query' not in qa_item:
                        raise ValueError(f"Missing 'query' field in line {line_num}")
                    if 'answer' not in qa_item:
                        raise ValueError(f"Missing 'answer' field in line {line_num}")
                    
                    qa_pairs.append(qa_item)
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in line {line_num}: {e}")
    
    except Exception as e:
        raise ValueError(f"Error reading QA dataset: {e}")
    
    if not qa_pairs:
        raise ValueError(f"No valid QA pairs found in {path}")
    
    return qa_pairs


def load_passages(path: str) -> List[Dict[str, Any]]:
    """
    Load passages dataset from JSONL file.
    
    Args:
        path: Path to JSONL file containing passages
        
    Returns:
        List of dictionaries with passage data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is empty or malformed
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Passages file not found: {path}")
    
    passages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    passage = json.loads(line)
                    
                    # Validate required fields
                    if 'id' not in passage:
                        raise ValueError(f"Missing 'id' field in line {line_num}")
                    if 'text' not in passage:
                        raise ValueError(f"Missing 'text' field in line {line_num}")
                    
                    passages.append(passage)
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in line {line_num}: {e}")
    
    except Exception as e:
        raise ValueError(f"Error reading passages: {e}")
    
    if not passages:
        raise ValueError(f"No valid passages found in {path}")
    
    return passages
