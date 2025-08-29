"""Enhanced synthetic provider for deterministic testing."""

import json
import re
import random
from typing import Dict, Any, Optional
from datetime import datetime


class SyntheticProvider:
    """Deterministic synthetic provider that generates realistic responses."""
    
    def __init__(self, base_url: str, token: Optional[str], provider: str, model: str, success_rate: float = 0.95, seed: int = 42):
        self.base_url = base_url
        self.token = token
        self.provider = provider
        self.model = model
        self.success_rate = success_rate
        self.call_count = 0
        self.seed = seed
        
        # Create deterministic random instance
        self.random = random.Random(seed)
    
    def complete(self, prompt: str, temperature: float = 0, top_p: float = 1, max_tokens: int = 1000) -> Dict[str, Any]:
        """Generate synthetic completion based on prompt analysis."""
        self.call_count += 1
        
        # Simulate some latency
        import time
        time.sleep(0.01)  # Much faster than real API
        
        prompt_lower = prompt.lower()
        
        # Determine if this should be a success or failure
        is_success = self.random.random() < self.success_rate
        
        # Receipt extraction
        if self._is_receipt_task(prompt_lower):
            return self._handle_receipt_extraction(prompt, is_success)
        
        # Mathematical operations
        elif self._is_math_task(prompt_lower):
            return self._handle_math_operation(prompt, is_success)
        
        # SQL generation
        elif self._is_sql_task(prompt_lower):
            return self._handle_sql_generation(prompt, is_success)
        
        # RAG/QA tasks
        elif self._is_qa_task(prompt_lower):
            return self._handle_qa_task(prompt, is_success)
        
        # Default response
        else:
            return self._handle_default_task(prompt, is_success)
    
    def _is_receipt_task(self, prompt_lower: str) -> bool:
        """Check if this is a receipt extraction task."""
        receipt_indicators = ["extract", "receipt", "merchant", "total", "purchase", "walmart", "target", "costco"]
        return any(indicator in prompt_lower for indicator in receipt_indicators)
    
    def _is_math_task(self, prompt_lower: str) -> bool:
        """Check if this is a mathematical operation."""
        math_indicators = ["calculate", "×", "*", "multiply", "product", "times", "compute"]
        has_math = any(indicator in prompt_lower for indicator in math_indicators)
        numbers = re.findall(r'\d+', prompt_lower)
        has_large_numbers = len(numbers) >= 2 and any(len(num) >= 6 for num in numbers)
        return has_math or has_large_numbers
    
    def _is_sql_task(self, prompt_lower: str) -> bool:
        """Check if this is a SQL generation task."""
        sql_indicators = ["select", "from", "where", "join", "sql", "query", "database"]
        return any(indicator in prompt_lower for indicator in sql_indicators)
    
    def _is_qa_task(self, prompt_lower: str) -> bool:
        """Check if this is a QA/RAG task."""
        qa_indicators = ["question", "answer", "context", "passage", "explain", "what", "how", "why"]
        return any(indicator in prompt_lower for indicator in qa_indicators)
    
    def _handle_receipt_extraction(self, prompt: str, is_success: bool) -> Dict[str, Any]:
        """Handle receipt extraction with realistic merchant detection."""
        if not is_success:
            return {
                "text": json.dumps({
                    "merchant": "Unknown Store",
                    "total": 0.0,
                    "date": "1900-01-01"
                }),
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 30
            }
        
        # Extract receipt text from prompt (handle both direct receipt and prompted format)
        receipt_text = prompt
        
        # If prompt contains instruction + receipt, extract just the receipt part
        if "receipt:" in prompt.lower():
            # Split on "receipt:" and take the part after
            parts = prompt.lower().split("receipt:")
            if len(parts) > 1:
                receipt_text = prompt[prompt.lower().find("receipt:") + 8:].strip()
        elif "from this receipt" in prompt.lower():
            # Handle "Extract ... from this receipt:\n<receipt_text>"
            lines = prompt.split('\n')
            receipt_start = -1
            for i, line in enumerate(lines):
                if "from this receipt" in line.lower() and i + 1 < len(lines):
                    receipt_start = i + 1
                    break
            if receipt_start >= 0:
                receipt_text = '\n'.join(lines[receipt_start:])
        
        # Extract actual data from receipt text
        merchant = "Unknown Store"
        total = 0.0
        date = "2024-01-01"
        
        # Smart merchant detection with better patterns
        merchant_patterns = [
            (r'walmart', "WALMART SUPERCENTER"),
            (r'target store', "TARGET STORE #1234"),
            (r'target', "TARGET STORE #1234"),
            (r'costco wholesale', "COSTCO WHOLESALE"),
            (r'costco', "COSTCO WHOLESALE"),
            (r'best buy', "Best Buy"),
            (r'home depot', "THE HOME DEPOT"),
            (r'cvs', "CVS PHARMACY"),
            (r'walgreens', "WALGREENS"),
            (r'starbucks', "STARBUCKS"),
            (r'mcdonalds', "MCDONALD'S"),
        ]
        
        receipt_lower = receipt_text.lower()
        for pattern, name in merchant_patterns:
            if pattern in receipt_lower:
                merchant = name
                break
        else:
            # Try to extract merchant from first line of receipt
            lines = receipt_text.split('\n')
            if lines:
                first_line = lines[0].strip()
                if len(first_line) > 3 and not any(char.isdigit() for char in first_line[:5]):
                    merchant = first_line
        
        # Extract total amount with better patterns (order matters - most specific first)
        total_patterns = [
            r'amount due[:\s]*\$?(\d+\.?\d*)',     # Most specific first
            r'final total[:\s]*\$?(\d+\.?\d*)',
            r'grand total[:\s]*\$?(\d+\.?\d*)',
            r'purchase amount[:\s]*\$?(\d+\.?\d*)',
            r'(?<!sub)total[:\s]*\$?(\d+\.?\d*)',  # Negative lookbehind to avoid "subtotal"
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, receipt_text.lower())
            if match:
                try:
                    total = float(match.group(1))
                    break
                except:
                    continue
        
        # Fallback: extract all amounts and use the largest reasonable one
        if total == 0.0:
            amounts = re.findall(r'\$?(\d+\.?\d*)', receipt_text)
            if amounts:
                try:
                    # Convert to floats and find reasonable total (not tax, not small amounts)
                    float_amounts = [float(a) for a in amounts if float(a) > 10.0]
                    if float_amounts:
                        total = max(float_amounts)  # Largest amount is usually total
                except:
                    total = 99.99
        
        # Extract date with multiple patterns
        date_patterns = [
            r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',  # MM/DD/YYYY or MM-DD-YYYY
            r'(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',  # YYYY/MM/DD or YYYY-MM-DD
            r'(\d{1,2}/\d{1,2}/\d{2})',          # MM/DD/YY
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, receipt_text)
            if date_match:
                found_date = date_match.group(1)
                # Convert to standard format if needed
                if len(found_date.split('/')[-1]) == 2:  # YY format
                    parts = found_date.split('/')
                    if len(parts) == 3:
                        date = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                    else:
                        date = found_date
                else:
                    date = found_date
                break
        
        return {
            "text": json.dumps({
                "merchant": merchant,
                "total": total,
                "date": date
            }),
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 30
        }
    
    def _handle_math_operation(self, prompt: str, is_success: bool) -> Dict[str, Any]:
        """Handle mathematical operations with controlled error rate."""
        numbers = re.findall(r'\d+', prompt)
        if len(numbers) >= 2:
            try:
                a = int(numbers[0])
                b = int(numbers[1])
                correct_result = a * b
                
                if is_success:
                    result = correct_result
                    print(f"🧮 SYNTHETIC CORRECT: {a} × {b} = {result}")
                else:
                    # Generate realistic errors
                    error_types = [
                        lambda x: x + self.random.randint(1, 1000),
                        lambda x: x - self.random.randint(1, 1000),
                        lambda x: int(x * 0.99),
                        lambda x: int(x * 1.01)
                    ]
                    error_func = self.random.choice(error_types)
                    result = error_func(correct_result)
                    print(f"🤖 SYNTHETIC ERROR: {a} × {b} = {result} (should be {correct_result})")
                
                return {
                    "text": json.dumps({"result": result}),
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": 20
                }
            except:
                pass
        
        return {
            "text": "42",
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 5
        }
    
    def _handle_sql_generation(self, prompt: str, is_success: bool) -> Dict[str, Any]:
        """Generate realistic SQL queries."""
        if not is_success:
            return {
                "text": "INVALID SQL SYNTAX ERROR",
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 10
            }
        
        # Generate basic SQL based on prompt
        if "users" in prompt.lower():
            sql = "SELECT * FROM users WHERE active = 1;"
        elif "orders" in prompt.lower():
            sql = "SELECT order_id, total FROM orders WHERE date >= '2024-01-01';"
        else:
            sql = "SELECT COUNT(*) FROM table_name;"
        
        return {
            "text": sql,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(sql.split())
        }
    
    def _handle_qa_task(self, prompt: str, is_success: bool) -> Dict[str, Any]:
        """Handle QA tasks with contextual answers."""
        if not is_success:
            return {
                "text": "I don't know the answer to this question.",
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 10
            }
        
        # Generate contextual answer
        if "capital" in prompt.lower():
            answer = "The capital city is typically the political center of a country or region."
        elif "python" in prompt.lower():
            answer = "Python is a high-level programming language known for its simplicity and readability."
        elif "ai" in prompt.lower() or "artificial intelligence" in prompt.lower():
            answer = "Artificial Intelligence refers to computer systems that can perform tasks typically requiring human intelligence."
        else:
            answer = "Based on the provided context, this appears to be a factual question that requires specific domain knowledge."
        
        return {
            "text": answer,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(answer.split())
        }
    
    def _handle_default_task(self, prompt: str, is_success: bool) -> Dict[str, Any]:
        """Default handler for unrecognized tasks."""
        if not is_success:
            return {
                "text": "Error: Unable to process this request.",
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 8
            }
        
        return {
            "text": "This is a synthetic response generated for testing purposes.",
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 12
        }


def create_synthetic_provider(success_rate: float = 0.95, seed: int = 42) -> SyntheticProvider:
    """Factory function to create a synthetic provider with specified success rate and seed."""
    return SyntheticProvider(
        base_url="synthetic://localhost",
        token="synthetic_token",
        provider="synthetic",
        model="synthetic-v1",
        success_rate=success_rate,
        seed=seed
    )
