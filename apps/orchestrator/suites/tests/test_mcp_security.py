"""
Tests for MCP Security Suite.

These tests ensure the MCP security/robustness suite works correctly with
deterministic behavior, proper threshold enforcement, and comprehensive
security testing capabilities.
"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any

from apps.orchestrator.suites.mcp_security import (
    MCPSecuritySuite, MCPTestResult, create_mcp_security_tests
)


class MockMCPClient:
    """Mock MCP client for testing."""
    
    def __init__(self, simulate_errors: bool = False):
        self.simulate_errors = simulate_errors
        self.call_count = 0
        self.schema_version = 1
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mock tool call."""
        self.call_count += 1
        
        if self.simulate_errors and self.call_count % 3 == 0:
            raise Exception("Simulated MCP error")
        
        # Simulate different responses based on tool name
        if tool_name == "list_tools":
            return {
                "tool": tool_name,
                "params": params,
                "result": ["list_tools", "get_info"],
                "status": "success"
            }
        elif tool_name == "out_of_scope_tool":
            raise PermissionError("Access denied: tool not in authorized scope")
        else:
            return {
                "tool": tool_name,
                "params": params,
                "result": "mock_response",
                "status": "success"
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Mock schema retrieval."""
        return {
            "tools": [
                {"name": "list_tools", "description": "List available tools"},
                {"name": "get_info", "description": "Get system information"}
            ],
            "version": f"1.{self.schema_version}.0",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    
    def increment_schema_version(self):
        """Simulate schema drift."""
        self.schema_version += 1


class TestMCPSecuritySuite(unittest.TestCase):
    """Test cases for MCP Security Suite."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MockMCPClient()
        self.options = {
            "mcp": {
                "allow_injection_test": False,
                "latency_test_calls": 5
            }
        }
        self.thresholds = {
            "mcp": {
                "max_p95_ms": 1000,
                "require_schema_stability": True,
                "deny_out_of_scope": True
            }
        }
    
    def test_suite_initialization(self):
        """Test MCP security suite initialization."""
        suite = MCPSecuritySuite(
            mcp_client=self.mock_client,
            options=self.options,
            thresholds=self.thresholds
        )
        
        self.assertEqual(suite.max_p95_ms, 1000)
        self.assertTrue(suite.require_schema_stability)
        self.assertTrue(suite.deny_out_of_scope)
        self.assertFalse(suite.allow_injection_test)
        self.assertEqual(suite.latency_test_calls, 5)
    
    def test_suite_default_thresholds(self):
        """Test suite with default thresholds."""
        suite = MCPSecuritySuite(mcp_client=self.mock_client)
        
        self.assertEqual(suite.max_p95_ms, 2000)  # Default
        self.assertTrue(suite.require_schema_stability)  # Default
        self.assertTrue(suite.deny_out_of_scope)  # Default
        self.assertFalse(suite.allow_injection_test)  # Default
        self.assertEqual(suite.latency_test_calls, 10)  # Default
    
    def test_prompt_injection_guard_blocked(self):
        """Test prompt injection guard when injection should be blocked."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                options={"mcp": {"allow_injection_test": False}},
                thresholds=self.thresholds
            )
            
            # Mock the safe_tool_call to return a controlled refusal
            with patch.object(suite, '_safe_tool_call') as mock_call:
                mock_call.return_value = {
                    "status": "denied",
                    "error": "Cannot process request - policy violation"
                }
                
                await suite._test_prompt_injection_guard()
                
                # Should pass because injection was properly blocked
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t1_injection_guard")
                self.assertEqual(result.status, "pass")
                self.assertIsNone(result.error_message)
        
        asyncio.run(run_test())
    
    def test_prompt_injection_guard_allowed(self):
        """Test prompt injection guard when injection testing is allowed."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                options={"mcp": {"allow_injection_test": True}},
                thresholds=self.thresholds
            )
            
            # Mock the safe_tool_call to return any response
            with patch.object(suite, '_safe_tool_call') as mock_call:
                mock_call.return_value = {
                    "status": "success",
                    "result": "Processing injection pattern for testing"
                }
                
                await suite._test_prompt_injection_guard()
                
                # Should pass because injection testing is explicitly allowed
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t1_injection_guard")
                self.assertEqual(result.status, "pass")
                self.assertTrue(result.details and result.details["allow_injection_test"])
        
        asyncio.run(run_test())
    
    def test_schema_drift_detection_stable(self):
        """Test schema drift detection when schema is stable."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock get_tool_schema to return consistent schema
            with patch.object(suite, '_get_tool_schema') as mock_schema:
                mock_schema.return_value = {
                    "tools": ["tool1", "tool2"],
                    "version": "1.0.0"
                }
                
                await suite._test_tool_schema_drift()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t2_schema_drift")
                self.assertEqual(result.status, "pass")
                self.assertTrue(result.details and result.details["schema_stable"])
        
        asyncio.run(run_test())
    
    def test_schema_drift_detection_unstable(self):
        """Test schema drift detection when schema changes."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock get_tool_schema to return different schemas
            schemas = [
                {"tools": ["tool1", "tool2"], "version": "1.0.0"},
                {"tools": ["tool1", "tool2", "tool3"], "version": "1.1.0"}  # Different
            ]
            
            with patch.object(suite, '_get_tool_schema', side_effect=schemas):
                await suite._test_tool_schema_drift()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t2_schema_drift")
                self.assertEqual(result.status, "fail")
                self.assertFalse(result.details and result.details["schema_stable"])
                self.assertIn("Schema drift detected", result.error_message or "")
        
        asyncio.run(run_test())
    
    def test_auth_scope_leakage_denied(self):
        """Test auth scope leakage when access is properly denied."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock out_of_scope_tool_call to raise permission error
            with patch.object(suite, '_out_of_scope_tool_call') as mock_call:
                mock_call.side_effect = PermissionError("Access denied")
                
                await suite._test_auth_scope_leakage()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t3_auth_scope")
                self.assertEqual(result.status, "pass")
                self.assertTrue(result.details and result.details["exception_indicates_denial"])
        
        asyncio.run(run_test())
    
    def test_auth_scope_leakage_not_denied(self):
        """Test auth scope leakage when access is not properly denied."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock out_of_scope_tool_call to succeed (security issue)
            with patch.object(suite, '_out_of_scope_tool_call') as mock_call:
                mock_call.return_value = {"status": "success", "result": "unauthorized_data"}
                
                with patch.object(suite, '_is_access_denied', return_value=False):
                    await suite._test_auth_scope_leakage()
                    
                    result = suite.test_results[0]
                    self.assertEqual(result.test_id, "mcp_security_t3_auth_scope")
                    self.assertEqual(result.status, "fail")
                    self.assertIn("not properly denied", result.error_message or "")
        
        asyncio.run(run_test())
    
    def test_idempotent_retries_consistent(self):
        """Test idempotent retries when results are consistent."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock safe_tool_call to return consistent results
            consistent_result = {"status": "success", "result": "consistent_response"}
            with patch.object(suite, '_safe_tool_call', return_value=consistent_result):
                await suite._test_idempotent_retries()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t4_idempotent")
                self.assertEqual(result.status, "pass")
                self.assertTrue(result.details and result.details["idempotent"])
                self.assertEqual(result.attempt, 2)  # Indicates retry test
        
        asyncio.run(run_test())
    
    def test_idempotent_retries_inconsistent(self):
        """Test idempotent retries when results are inconsistent."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                thresholds=self.thresholds
            )
            
            # Mock safe_tool_call to return different results
            results = [
                {"status": "success", "result": "response_1"},
                {"status": "error", "result": "response_2"}  # Different status
            ]
            
            with patch.object(suite, '_safe_tool_call', side_effect=results):
                await suite._test_idempotent_retries()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t4_idempotent")
                self.assertEqual(result.status, "fail")
                self.assertFalse(result.details and result.details["idempotent"])
                self.assertIn("inconsistent results", result.error_message or "")
        
        asyncio.run(run_test())
    
    def test_latency_slo_met(self):
        """Test latency SLO when performance meets threshold."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                options={"mcp": {"latency_test_calls": 3}},
                thresholds={"mcp": {"max_p95_ms": 1000}}
            )
            
            # Mock safe_tool_call with fast responses
            with patch.object(suite, '_safe_tool_call') as mock_call:
                # Simulate fast calls (under threshold)
                async def fast_call(*args, **kwargs):
                    await asyncio.sleep(0.01)  # 10ms
                    return {"status": "success"}
                
                mock_call.side_effect = fast_call
                
                await suite._test_latency_slo()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t5_latency_slo")
                self.assertEqual(result.status, "pass")
                self.assertTrue(result.details and result.details["slo_met"])
                self.assertEqual(result.attempt, 3)  # Number of calls made
        
        asyncio.run(run_test())
    
    def test_latency_slo_exceeded(self):
        """Test latency SLO when performance exceeds threshold."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                options={"mcp": {"latency_test_calls": 2}},
                thresholds={"mcp": {"max_p95_ms": 50}}  # Very low threshold
            )
            
            # Mock safe_tool_call with slow responses
            with patch.object(suite, '_safe_tool_call') as mock_call:
                # Simulate slow calls (over threshold)
                async def slow_call(*args, **kwargs):
                    await asyncio.sleep(0.1)  # 100ms
                    return {"status": "success"}
                
                mock_call.side_effect = slow_call
                
                await suite._test_latency_slo()
                
                result = suite.test_results[0]
                self.assertEqual(result.test_id, "mcp_security_t5_latency_slo")
                self.assertEqual(result.status, "fail")
                self.assertFalse(result.details and result.details["slo_met"])
                self.assertIn("exceeds threshold", result.error_message or "")
        
        asyncio.run(run_test())
    
    def test_run_all_tests(self):
        """Test running all MCP security tests."""
        async def run_test():
            suite = MCPSecuritySuite(
                mcp_client=self.mock_client,
                options={"mcp": {"latency_test_calls": 2}},
                thresholds=self.thresholds
            )
            
            # Mock all the individual test methods
            with patch.object(suite, '_test_prompt_injection_guard') as mock_t1, \
                 patch.object(suite, '_test_tool_schema_drift') as mock_t2, \
                 patch.object(suite, '_test_auth_scope_leakage') as mock_t3, \
                 patch.object(suite, '_test_idempotent_retries') as mock_t4, \
                 patch.object(suite, '_test_latency_slo') as mock_t5:
                
                results = await suite.run_all_tests()
                
                # Verify all tests were called
                mock_t1.assert_called_once()
                mock_t2.assert_called_once()
                mock_t3.assert_called_once()
                mock_t4.assert_called_once()
                mock_t5.assert_called_once()
                
                # Results should be the same as test_results
                self.assertEqual(results, suite.test_results)
        
        asyncio.run(run_test())
    
    def test_get_metrics_summary(self):
        """Test metrics summary generation."""
        suite = MCPSecuritySuite(mcp_client=self.mock_client)
        
        # Add some mock test results
        suite.test_results = [
            MCPTestResult(
                test_id="mcp_security_t1_injection_guard",
                test_name="Prompt Injection Guard",
                status="pass",
                latency_ms=100
            ),
            MCPTestResult(
                test_id="mcp_security_t5_latency_slo",
                test_name="Latency/SLO",
                status="pass",
                latency_ms=200,
                details={"p95_latency_ms": 150, "slo_met": True}
            ),
            MCPTestResult(
                test_id="mcp_security_t2_schema_drift",
                test_name="Schema Drift",
                status="fail",
                latency_ms=50,
                details={"schema_stable": False}
            )
        ]
        
        metrics = suite.get_metrics_summary()
        
        self.assertEqual(metrics["total_tests"], 3)
        self.assertEqual(metrics["passed"], 2)
        self.assertAlmostEqual(metrics["pass_rate"], 2/3)
        self.assertEqual(metrics["p95_latency_ms"], 150)
        self.assertFalse(metrics["schema_stable"])
        self.assertTrue(metrics["out_of_scope_denied"])  # Default
    
    def test_helper_methods(self):
        """Test helper methods."""
        suite = MCPSecuritySuite(mcp_client=self.mock_client)
        
        # Test _is_controlled_refusal
        refusal_result = {"status": "denied", "error": "Cannot process - policy violation"}
        self.assertTrue(suite._is_controlled_refusal(refusal_result))
        
        normal_result = {"status": "success", "result": "normal response"}
        self.assertFalse(suite._is_controlled_refusal(normal_result))
        
        # Test _is_access_denied
        denied_result = {"status": "denied"}
        self.assertTrue(suite._is_access_denied(denied_result))
        
        allowed_result = {"status": "success"}
        self.assertFalse(suite._is_access_denied(allowed_result))
        
        # Test _results_are_idempotent
        result1 = {"status": "success", "data": "test"}
        result2 = {"status": "success", "data": "different"}  # Same status
        self.assertTrue(suite._results_are_idempotent(result1, result2))
        
        result3 = {"status": "error", "data": "test"}  # Different status
        self.assertFalse(suite._results_are_idempotent(result1, result3))
        
        # Test _hash_schema
        schema1 = {"tools": ["a", "b"], "version": "1.0", "timestamp": "2024-01-01"}
        schema2 = {"tools": ["a", "b"], "version": "1.0", "timestamp": "2024-01-02"}  # Different timestamp
        
        # Should be same hash (timestamp ignored)
        self.assertEqual(suite._hash_schema(schema1), suite._hash_schema(schema2))
        
        schema3 = {"tools": ["a", "b", "c"], "version": "1.0", "timestamp": "2024-01-01"}  # Different tools
        self.assertNotEqual(suite._hash_schema(schema1), suite._hash_schema(schema3))


class TestMCPSecurityIntegration(unittest.TestCase):
    """Integration tests for MCP Security Suite."""
    
    def test_create_mcp_security_tests(self):
        """Test creation of MCP security test cases for orchestrator."""
        options = {"mcp": {"allow_injection_test": True}}
        thresholds = {"mcp": {"max_p95_ms": 1500}}
        
        test_cases = create_mcp_security_tests(options=options, thresholds=thresholds)
        
        # Should create 5 test cases
        self.assertEqual(len(test_cases), 5)
        
        # Check test IDs
        expected_ids = [
            "mcp_security_t1_injection_guard",
            "mcp_security_t2_schema_drift",
            "mcp_security_t3_auth_scope",
            "mcp_security_t4_idempotent",
            "mcp_security_t5_latency_slo"
        ]
        
        actual_ids = [test["test_id"] for test in test_cases]
        self.assertEqual(actual_ids, expected_ids)
        
        # Check test structure
        for test_case in test_cases:
            self.assertIn("test_id", test_case)
            self.assertIn("query", test_case)
            self.assertEqual(test_case["test_type"], "mcp_security")
            self.assertIn("category", test_case)
            self.assertIn("mcp_test_config", test_case)
            
            # Check config structure
            config = test_case["mcp_test_config"]
            self.assertIn("test_name", config)
            self.assertIn("description", config)
            self.assertEqual(config["options"], options)
            self.assertEqual(config["thresholds"], thresholds)
    
    def test_create_mcp_security_tests_defaults(self):
        """Test creation with default options and thresholds."""
        test_cases = create_mcp_security_tests()
        
        self.assertEqual(len(test_cases), 5)
        
        # Check that None options/thresholds are handled
        for test_case in test_cases:
            config = test_case["mcp_test_config"]
            self.assertIsNone(config["options"])
            self.assertIsNone(config["thresholds"])


if __name__ == '__main__':
    unittest.main()
