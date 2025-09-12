"""RAG-specific test data loaders and manifest handling."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from .models import PassageRecord, QARecord, ValidationError

logger = logging.getLogger(__name__)


class RAGManifest(BaseModel):
    """RAG test data manifest with optional paths."""
    passages: Optional[str] = None
    qaset: Optional[str] = None
    attacks: Optional[str] = None
    schema: Optional[str] = None


def load_passages(path: str) -> List[Dict[str, Any]]:
    """
    Load passages from JSONL file.
    
    Args:
        path: Path to passages.jsonl file
        
    Returns:
        List of passage dictionaries with id, text, and optional metadata
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    passages = []
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"Passages file not found: {path}")
    
    try:
        with open(path_obj, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    passage_data = json.loads(line)
                    
                    # Validate required fields
                    if 'id' not in passage_data:
                        raise ValueError(f"Missing 'id' field at line {line_num}")
                    if 'text' not in passage_data:
                        raise ValueError(f"Missing 'text' field at line {line_num}")
                    
                    # Ensure text is not empty
                    if not passage_data['text'].strip():
                        raise ValueError(f"Empty 'text' field at line {line_num}")
                    
                    passages.append({
                        'id': str(passage_data['id']),
                        'text': passage_data['text'],
                        'meta': passage_data.get('meta', {})
                    })
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")
                    
    except Exception as e:
        logger.error(f"Error loading passages from {path}: {e}")
        raise
    
    logger.info(f"Loaded {len(passages)} passages from {path}")
    return passages


def load_qaset(path: str) -> List[Dict[str, Any]]:
    """
    Load QA set from JSONL file.
    
    Args:
        path: Path to qaset.jsonl file
        
    Returns:
        List of QA dictionaries with qid, question, expected_answer, and optional contexts
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    qaset = []
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"QA set file not found: {path}")
    
    try:
        with open(path_obj, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    qa_data = json.loads(line)
                    
                    # Validate required fields
                    required_fields = ['qid', 'question', 'expected_answer']
                    for field in required_fields:
                        if field not in qa_data:
                            raise ValueError(f"Missing '{field}' field at line {line_num}")
                        if not qa_data[field].strip():
                            raise ValueError(f"Empty '{field}' field at line {line_num}")
                    
                    qaset.append({
                        'qid': str(qa_data['qid']),
                        'question': qa_data['question'],
                        'expected_answer': qa_data['expected_answer'],
                        'contexts': qa_data.get('contexts', []),
                        # Embedding Robustness fields (optional, backward compatible)
                        'required': qa_data.get('required'),
                        'robustness': qa_data.get('robustness'),
                        # Prompt Robustness fields (optional, backward compatible)
                        'task_type': qa_data.get('task_type', 'rag_qa'),
                        'prompt_robustness': qa_data.get('prompt_robustness')
                    })
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")
                    
    except Exception as e:
        logger.error(f"Error loading QA set from {path}: {e}")
        raise
    
    logger.info(f"Loaded {len(qaset)} QA pairs from {path}")
    return qaset


def resolve_manifest_from_bundle(testdata_id: str, bundle_dir: Path) -> RAGManifest:
    """
    Resolve RAG manifest from testdata bundle directory.
    
    Args:
        testdata_id: Test data bundle ID
        bundle_dir: Path to bundle directory
        
    Returns:
        RAGManifest with resolved file paths
    """
    manifest = RAGManifest()
    
    # Check for standard RAG files
    passages_file = bundle_dir / "passages.jsonl"
    if passages_file.exists():
        manifest.passages = str(passages_file)
    
    qaset_file = bundle_dir / "qaset.jsonl"
    if qaset_file.exists():
        manifest.qaset = str(qaset_file)
    
    attacks_file = bundle_dir / "attacks.txt"
    if not attacks_file.exists():
        attacks_file = bundle_dir / "attacks.yaml"
    if attacks_file.exists():
        manifest.attacks = str(attacks_file)
    
    schema_file = bundle_dir / "schema.json"
    if schema_file.exists():
        manifest.schema = str(schema_file)
    
    logger.info(f"Resolved RAG manifest for {testdata_id}: passages={bool(manifest.passages)}, qaset={bool(manifest.qaset)}, attacks={bool(manifest.attacks)}, schema={bool(manifest.schema)}")
    return manifest
