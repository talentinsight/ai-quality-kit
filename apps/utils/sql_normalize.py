"""SQL normalization and comparison utilities for structured evaluation."""

import re
from typing import List, Dict, Any


def canonicalize_sql(sql: str) -> str:
    """
    Canonicalize SQL query for comparison.
    
    Args:
        sql: Raw SQL query string
        
    Returns:
        Canonicalized SQL string
    """
    if not sql:
        return ""
    
    # Step 1: Remove comments
    # Remove line comments (-- ...)
    sql = re.sub(r'--.*?(?=\n|$)', '', sql)
    # Remove block comments (/* ... */)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    
    # Step 2: Strip trailing semicolon
    sql = sql.rstrip(';').strip()
    
    # Step 3: Normalize whitespace
    # Convert CRLF/CR to LF, then replace newlines with spaces
    sql = sql.replace('\r\n', '\n').replace('\r', '\n')
    sql = re.sub(r'\s+', ' ', sql)
    
    # Step 4: Uppercase SQL keywords
    sql_keywords = [
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
        'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL', 'DISTINCT',
        'AND', 'OR', 'NOT', 'IN', 'BETWEEN', 'LIKE', 'AS', 'CASE', 'WHEN', 'THEN',
        'ELSE', 'END', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TABLE'
    ]
    
    # Sort by length (longest first) to avoid partial matches
    sql_keywords.sort(key=len, reverse=True)
    
    for keyword in sql_keywords:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        sql = re.sub(pattern, keyword, sql, flags=re.IGNORECASE)
    
    # Step 5: Put single spaces around commas and equals
    sql = re.sub(r'\s*,\s*', ', ', sql)
    sql = re.sub(r'\s*=\s*', ' = ', sql)
    
    # Step 6: Parenthesis simplification (safe)
    sql = sql.strip()
    if sql.startswith('(') and sql.endswith(')'):
        # Check if the parentheses are balanced and the outer pair can be removed
        inner = sql[1:-1]
        if _is_balanced_parentheses(inner):
            sql = inner.strip()
    
    # Step 7: Final trim
    return sql.strip()


def split_where_and_predicates(sql: str) -> List[str]:
    """
    Split WHERE clause predicates connected by AND.
    
    Args:
        sql: Canonicalized SQL query
        
    Returns:
        List of normalized predicates if WHERE contains only AND, empty list otherwise
    """
    # Find WHERE clause
    where_match = re.search(r'\bWHERE\b\s+(.*?)(?:\s+(?:GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|UNION|$))', sql, re.IGNORECASE)
    if not where_match:
        return []
    
    where_clause = where_match.group(1).strip()
    
    # Check if contains OR (if so, return empty list)
    if re.search(r'\bOR\b', where_clause, re.IGNORECASE):
        return []
    
    # Split on AND and normalize each predicate
    predicates = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
    normalized_predicates = []
    
    for pred in predicates:
        pred = pred.strip()
        if pred:
            # Normalize spaces around operators
            pred = re.sub(r'\s*=\s*', ' = ', pred)
            pred = re.sub(r'\s*<\s*', ' < ', pred)
            pred = re.sub(r'\s*>\s*', ' > ', pred)
            pred = re.sub(r'\s*<=\s*', ' <= ', pred)
            pred = re.sub(r'\s*>=\s*', ' >= ', pred)
            pred = re.sub(r'\s*!=\s*', ' != ', pred)
            pred = re.sub(r'\s*<>\s*', ' <> ', pred)
            normalized_predicates.append(pred.strip())
    
    # Sort predicates for consistent comparison
    return sorted(normalized_predicates)


def compare_sql(gold: str, pred: str) -> Dict[str, Any]:
    """
    Compare two SQL queries for semantic equality.
    
    Args:
        gold: Gold standard SQL query
        pred: Predicted SQL query
        
    Returns:
        Dictionary with comparison results
    """
    gold_c = canonicalize_sql(gold)
    pred_c = canonicalize_sql(pred)
    
    canonical_equal = (gold_c == pred_c)
    
    wa_gold = split_where_and_predicates(gold_c)
    wa_pred = split_where_and_predicates(pred_c)
    where_and_set_equal = bool(wa_gold and wa_pred and wa_gold == wa_pred)
    
    # Create normalized diff preview
    gold_preview = gold_c[:120] + ("..." if len(gold_c) > 120 else "")
    pred_preview = pred_c[:120] + ("..." if len(pred_c) > 120 else "")
    normalized_sql_diff_preview = f"GOLD: {gold_preview} || PRED: {pred_preview}"
    
    return {
        "canonical_equal": canonical_equal,
        "where_and_set_equal": where_and_set_equal,
        "normalized_sql_diff_preview": normalized_sql_diff_preview
    }


def _is_balanced_parentheses(s: str) -> bool:
    """Check if parentheses are balanced in the string."""
    count = 0
    for char in s:
        if char == '(':
            count += 1
        elif char == ')':
            count -= 1
            if count < 0:
                return False
    return count == 0
