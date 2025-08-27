"""Storage and validation utilities for test data intake."""

import json
import os
import shutil
import time
import uuid
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple


# Allowed file names for security
ALLOWED_FILES = {
    "passages.jsonl",
    "qaset.jsonl", 
    "attacks.txt",
    "attacks.yaml",
    "attacks.yml"
}

# Maximum total upload size (50 MB)
MAX_TOTAL_SIZE = 50 * 1024 * 1024


def create_bundle_dir(reports_dir: Path) -> Tuple[str, Path]:
    """
    Create a new bundle directory for test data intake.
    
    Args:
        reports_dir: Base reports directory
        
    Returns:
        Tuple of (testdata_id, directory_path)
    """
    testdata_id = str(uuid.uuid4())
    intake_root = reports_dir / "intake"
    intake_root.mkdir(exist_ok=True)
    
    bundle_dir = intake_root / testdata_id
    bundle_dir.mkdir(exist_ok=True)
    
    # Create metadata file
    metadata = {
        "testdata_id": testdata_id,
        "created_at": time.time(),
        "files": {}
    }
    
    with open(bundle_dir / ".metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return testdata_id, bundle_dir


def list_bundle(dir_path: Path) -> List[Dict[str, Any]]:
    """
    List files in a bundle directory.
    
    Args:
        dir_path: Bundle directory path
        
    Returns:
        List of file info dictionaries
    """
    if not dir_path.exists():
        return []
    
    files = []
    for file_path in dir_path.iterdir():
        if file_path.name.startswith('.'):
            continue  # Skip metadata and hidden files
            
        if file_path.is_file() and file_path.name in ALLOWED_FILES:
            files.append({
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "path": str(file_path)
            })
    
    return files


def validate_file(path: Path, kind: str) -> None:
    """
    Validate a file based on its type.
    
    Args:
        path: File path to validate
        kind: File kind (passages, qaset, attacks)
        
    Raises:
        ValueError: If file is invalid
    """
    if not path.exists():
        raise ValueError(f"File does not exist: {path}")
    
    content = path.read_text(encoding='utf-8')
    
    if kind == "passages":
        _validate_passages(content)
    elif kind == "qaset":
        _validate_qaset(content)
    elif kind == "attacks":
        _validate_attacks(content, path.suffix)
    else:
        raise ValueError(f"Unknown file kind: {kind}")


def _validate_passages(content: str) -> None:
    """Validate passages.jsonl content."""
    lines = content.strip().split('\n')
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        raise ValueError("Passages file is empty")
    
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
            
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"Line {i}: Expected JSON object")
            
            # Check for required text field (accept both 'text' and 'chunk')
            if 'text' not in obj and 'chunk' not in obj:
                raise ValueError(f"Line {i}: Missing 'text' or 'chunk' field")
                
            text_content = obj.get('text') or obj.get('chunk')
            if not isinstance(text_content, str):
                raise ValueError(f"Line {i}: 'text'/'chunk' must be string")
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Line {i}: Invalid JSON - {e}")


def _validate_qaset(content: str) -> None:
    """Validate qaset.jsonl content."""
    lines = content.strip().split('\n')
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        raise ValueError("QA set file is empty")
    
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
            
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"Line {i}: Expected JSON object")
            
            # Check required fields
            if 'question' not in obj:
                raise ValueError(f"Line {i}: Missing 'question' field")
            if 'answer' not in obj:
                raise ValueError(f"Line {i}: Missing 'answer' field")
                
            if not isinstance(obj['question'], str):
                raise ValueError(f"Line {i}: 'question' must be string")
            if not isinstance(obj['answer'], str):
                raise ValueError(f"Line {i}: 'answer' must be string")
                
            # Optional contexts field
            if 'contexts' in obj and not isinstance(obj['contexts'], list):
                raise ValueError(f"Line {i}: 'contexts' must be list")
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Line {i}: Invalid JSON - {e}")


def _validate_attacks(content: str, suffix: str) -> None:
    """Validate attacks file content."""
    if not content.strip():
        raise ValueError("Attacks file is empty")
    
    if suffix in ['.yaml', '.yml']:
        try:
            data = yaml.safe_load(content)
            if isinstance(data, list):
                # YAML sequence of strings
                for i, item in enumerate(data):
                    if not isinstance(item, str):
                        raise ValueError(f"Item {i+1}: Expected string attack")
            elif isinstance(data, dict) and 'attacks' in data:
                # YAML with attacks key
                attacks = data['attacks']
                if not isinstance(attacks, list):
                    raise ValueError("'attacks' field must be a list")
                for i, item in enumerate(attacks):
                    if not isinstance(item, str):
                        raise ValueError(f"Attack {i+1}: Expected string")
            else:
                raise ValueError("Expected list of attacks or dict with 'attacks' key")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")
    else:
        # Plain text - newline separated
        lines = content.strip().split('\n')
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            raise ValueError("No attacks found in file")
        
        for i, line in enumerate(lines, 1):
            if line.strip() and len(line.strip()) < 3:
                raise ValueError(f"Line {i}: Attack too short (minimum 3 characters)")


def delete_bundle(dir_path: Path) -> None:
    """
    Delete a bundle directory and all its contents.
    
    Args:
        dir_path: Bundle directory to delete
    """
    if dir_path.exists() and dir_path.is_dir():
        shutil.rmtree(dir_path)


def janitor_clean_old(root: Path, hours: int = 24) -> int:
    """
    Clean up old bundle directories.
    
    Args:
        root: Root directory to clean (reports_dir)
        hours: Age threshold in hours
        
    Returns:
        Number of directories deleted
    """
    intake_dir = root / "intake"
    if not intake_dir.exists():
        return 0
    
    cutoff_time = time.time() - (hours * 3600)
    deleted_count = 0
    
    for bundle_dir in intake_dir.iterdir():
        if not bundle_dir.is_dir():
            continue
            
        # Check metadata for creation time
        metadata_file = bundle_dir / ".metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                created_at = metadata.get("created_at", 0)
                
                if created_at < cutoff_time:
                    delete_bundle(bundle_dir)
                    deleted_count += 1
            except (json.JSONDecodeError, OSError):
                # If metadata is corrupted, delete if directory is old
                dir_mtime = bundle_dir.stat().st_mtime
                if dir_mtime < cutoff_time:
                    delete_bundle(bundle_dir)
                    deleted_count += 1
        else:
            # No metadata, use directory modification time
            dir_mtime = bundle_dir.stat().st_mtime
            if dir_mtime < cutoff_time:
                delete_bundle(bundle_dir)
                deleted_count += 1
    
    return deleted_count


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for security.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
        
    Raises:
        ValueError: If filename is not allowed
    """
    # Remove path components
    filename = os.path.basename(filename)
    
    # Check against allowed list
    if filename not in ALLOWED_FILES:
        raise ValueError(f"Filename not allowed: {filename}. Allowed: {', '.join(ALLOWED_FILES)}")
    
    return filename


def check_total_size(files: List[Path]) -> None:
    """
    Check total size of files against limit.
    
    Args:
        files: List of file paths
        
    Raises:
        ValueError: If total size exceeds limit
    """
    total_size = sum(f.stat().st_size for f in files if f.exists())
    
    if total_size > MAX_TOTAL_SIZE:
        raise ValueError(f"Total upload size {total_size} bytes exceeds limit of {MAX_TOTAL_SIZE} bytes")
