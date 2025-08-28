"""Tests for structure evaluation reporting sheets."""

import unittest
from unittest.mock import MagicMock
from apps.reporting.structure_sheet import (
    write_structure_sheet,
    write_structure_prompts_sheet,
    write_structure_diffs_sheet,
    compute_summary_rollups
)


class MockWorkbook:
    """Mock workbook for testing."""
    
    def __init__(self):
        self.sheets = {}
    
    def create_sheet(self, name):
        sheet = MockWorksheet(name)
        self.sheets[name] = sheet
        return sheet


class MockWorksheet:
    """Mock worksheet for testing."""
    
    def __init__(self, name):
        self.name = name
        self.cells = {}
    
    def cell(self, row, column, value=None):
        if value is not None:
            self.cells[(row, column)] = value
        return MockCell(self.cells.get((row, column), ""))


class MockCell:
    """Mock cell for testing."""
    
    def __init__(self, value):
        self.value = value


class TestStructureSheet(unittest.TestCase):
    """Test structure sheet functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.wb = MockWorkbook()
    
    def test_write_structure_sheet_basic(self):
        """Test basic structure sheet writing."""
        rows = [
            {
                "run_id": "test_run_001",
                "item_id": "item_001",
                "task_type": "long_multiplication",
                "mode": "simple",
                "paraphrase_idx": 0,
                "prompt_source": "built_in",
                "prompt_hash": "abc123",
                "input_preview_masked": "Calculate 123 × 456",
                "gold_preview_masked": "56088",
                "raw_output_preview_masked": "The answer is 56088",
                "parsed_result": 56088,
                "exact_match": True,
                "similarity_score": 1.0,
                "contract_ok": True,
                "latency_ms": 1500,
                "prompt_tokens": 25,
                "completion_tokens": 10,
                "skip_reason": ""
            },
            {
                "run_id": "test_run_001",
                "item_id": "item_002",
                "task_type": "extraction",
                "mode": "cot",
                "paraphrase_idx": 1,
                "prompt_source": "built_in",
                "prompt_hash": "def456",
                "input_preview_masked": "Receipt with user@[EMAIL] and [PHONE]",
                "gold_preview_masked": "Merchant: Test Store",
                "raw_output_preview_masked": "The merchant is Test Store, total $45.67",
                "parsed_result": {"merchant": "Test Store", "total": 45.67},
                "exact_match": False,
                "similarity_score": 0.8,
                "contract_ok": None,
                "latency_ms": 2000,
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "skip_reason": ""
            }
        ]
        
        write_structure_sheet(self.wb, rows)
        
        # Check that sheet was created
        self.assertIn("Structure", self.wb.sheets)
        sheet = self.wb.sheets["Structure"]
        
        # Check headers
        self.assertEqual(sheet.cells[(1, 1)], "run_id")
        self.assertEqual(sheet.cells[(1, 2)], "item_id")
        self.assertEqual(sheet.cells[(1, 3)], "task_type")
        
        # Check first data row
        self.assertEqual(sheet.cells[(2, 1)], "test_run_001")
        self.assertEqual(sheet.cells[(2, 2)], "item_001")
        self.assertEqual(sheet.cells[(2, 3)], "long_multiplication")
        self.assertEqual(sheet.cells[(2, 13)], True)  # exact_match
        self.assertEqual(sheet.cells[(2, 14)], 1.0)   # similarity_score
    
    def test_write_structure_sheet_pii_masking(self):
        """Test that PII masking is applied to preview fields."""
        rows = [
            {
                "run_id": "test_run_001",
                "item_id": "item_001",
                "input_preview_masked": "Contact user@example.com or call 555-123-4567",
                "gold_preview_masked": "Expected result",
                "raw_output_preview_masked": "Response with credit card 4532-1234-5678-9012",
                # ... other required fields with defaults
                "task_type": "test", "mode": "simple", "paraphrase_idx": 0,
                "prompt_source": "built_in", "prompt_hash": "test",
                "parsed_result": None, "exact_match": False, "similarity_score": 0.0,
                "contract_ok": None, "latency_ms": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "skip_reason": ""
            }
        ]
        
        write_structure_sheet(self.wb, rows)
        sheet = self.wb.sheets["Structure"]
        
        # Check that PII was masked in preview fields
        input_preview = sheet.cells[(2, 8)]  # input_preview_masked column
        self.assertIn("[EMAIL]", input_preview)
        self.assertIn("[PHONE]", input_preview)
        self.assertNotIn("user@example.com", input_preview)
        
        output_preview = sheet.cells[(2, 10)]  # raw_output_preview_masked column
        self.assertIn("[CREDIT_CARD]", output_preview)
        self.assertNotIn("4532-1234-5678-9012", output_preview)
    
    def test_write_structure_prompts_sheet_deduplication(self):
        """Test prompt sheet deduplication."""
        prompt_rows = [
            {
                "item_id": "item_001",
                "mode": "simple",
                "prompt_source": "built_in",
                "prompt_hash": "abc123",
                "prompt_masked_full": "Calculate the result",
                "style_contract_version": "",
                "provider_profile": "",
                "gates_passed": ""
            },
            {
                "item_id": "item_001",
                "mode": "simple", 
                "prompt_source": "built_in",
                "prompt_hash": "abc123",  # Same hash - should be deduplicated
                "prompt_masked_full": "Calculate the result",
                "style_contract_version": "",
                "provider_profile": "",
                "gates_passed": ""
            },
            {
                "item_id": "item_001",
                "mode": "cot",
                "prompt_source": "built_in",
                "prompt_hash": "def456",  # Different hash - should be kept
                "prompt_masked_full": "Think step by step and calculate",
                "style_contract_version": "",
                "provider_profile": "",
                "gates_passed": ""
            }
        ]
        
        write_structure_prompts_sheet(self.wb, prompt_rows)
        
        # Check that sheet was created
        self.assertIn("Structure_Prompts", self.wb.sheets)
        sheet = self.wb.sheets["Structure_Prompts"]
        
        # Should have header + 2 unique rows (deduplicated)
        self.assertEqual(sheet.cells[(1, 1)], "item_id")
        self.assertEqual(sheet.cells[(2, 1)], "item_001")  # First unique row
        self.assertEqual(sheet.cells[(3, 1)], "item_001")  # Second unique row
        self.assertNotIn((4, 1), sheet.cells)  # No third row due to deduplication
    
    def test_write_structure_diffs_sheet_task_specific(self):
        """Test diffs sheet with task-specific columns."""
        diff_rows = [
            {
                "item_id": "item_001",
                "mode": "simple",
                "paraphrase_idx": 0,
                "task_type": "long_multiplication",
                "diff_preview": "Parsed: 56088, Gold: 56088, Diff: 0",
                "abs_diff": 0,
                "relative_error": 0.0
            },
            {
                "item_id": "item_002",
                "mode": "cot",
                "paraphrase_idx": 0,
                "task_type": "extraction",
                "diff_preview": "Accuracy: 0.67, Missing: 1, Mismatched: 0",
                "fieldwise_accuracy": 0.67,
                "missing_fields": "date",
                "mismatched_fields": ""
            },
            {
                "item_id": "item_003",
                "mode": "scaffold",
                "paraphrase_idx": 0,
                "task_type": "json_to_sql",
                "diff_preview": "Canonical: True, WHERE-AND: True",
                "canonical_equal": True,
                "where_and_set_equal": True,
                "normalized_sql_diff_preview": "GOLD: SELECT * FROM users || PRED: SELECT * FROM users"
            }
        ]
        
        write_structure_diffs_sheet(self.wb, diff_rows)
        
        # Check that sheet was created
        self.assertIn("Structure_Diffs", self.wb.sheets)
        sheet = self.wb.sheets["Structure_Diffs"]
        
        # Check base columns
        self.assertEqual(sheet.cells[(1, 1)], "item_id")
        self.assertEqual(sheet.cells[(1, 2)], "mode")
        self.assertEqual(sheet.cells[(1, 3)], "paraphrase_idx")
        self.assertEqual(sheet.cells[(1, 4)], "diff_preview")
        
        # Check that task-specific columns are present
        # (The exact column order depends on the sorted task-specific columns)
        header_values = [sheet.cells.get((1, i), "") for i in range(1, 15)]
        self.assertIn("abs_diff", header_values)
        self.assertIn("fieldwise_accuracy", header_values)
        self.assertIn("canonical_equal", header_values)
    
    def test_compute_summary_rollups_basic(self):
        """Test summary rollups computation."""
        structure_rows = [
            {
                "item_id": "item_001",
                "mode": "simple",
                "exact_match": True,
                "contract_ok": True
            },
            {
                "item_id": "item_001", 
                "mode": "scaffold",
                "exact_match": True,
                "contract_ok": True
            },
            {
                "item_id": "item_002",
                "mode": "simple",
                "exact_match": False,
                "contract_ok": False
            },
            {
                "item_id": "item_002",
                "mode": "scaffold", 
                "exact_match": True,
                "contract_ok": None
            }
        ]
        
        rollups = compute_summary_rollups(structure_rows)
        
        # Check capacity lift (scaffold - simple)
        # Simple: 1/2 = 0.5, Scaffold: 2/2 = 1.0, Lift: 1.0 - 0.5 = 0.5
        self.assertEqual(rollups["capacity_lift_avg"], 0.5)
        
        # Check stability (using accuracy as proxy)
        self.assertIn("simple", rollups["stability_avg_by_mode"])
        self.assertIn("scaffold", rollups["stability_avg_by_mode"])
        
        # Check contract adherence (2 True out of 3 non-None = 66.7%)
        self.assertAlmostEqual(rollups["contract_adherence_pct"], 66.7, places=1)
    
    def test_compute_summary_rollups_empty(self):
        """Test summary rollups with empty data."""
        rollups = compute_summary_rollups([])
        
        self.assertEqual(rollups["capacity_lift_avg"], 0.0)
        self.assertEqual(rollups["stability_avg_by_mode"], {})
        self.assertEqual(rollups["contract_adherence_pct"], 0.0)
        self.assertIsNone(rollups["faithfulness_avg"])


if __name__ == '__main__':
    unittest.main()
