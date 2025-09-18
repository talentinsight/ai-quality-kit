"""
Guardrails Composite Suite.

A composite suite that routes to existing suites based on guardrails configuration
and aggregates results under a unified "Guardrails" summary.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GuardrailsSubtest:
    """Represents a guardrails subtest that maps to underlying suite tests."""
    name: str
    suite: str
    enabled: bool
    config: Dict[str, Any]
    tags: List[str]
    skip_reason: Optional[str] = None


class GuardrailsSuite:
    """
    Guardrails composite suite that routes to existing suites.
    
    This suite inspects the guardrails configuration and enqueues underlying tests
    by calling existing loaders with appropriate tags and parameters.
    """
    
    def __init__(self, request, test_runner):
        self.request = request
        self.test_runner = test_runner
        self.guardrails_config = request.guardrails if request.guardrails else None
        self.subtests: List[GuardrailsSubtest] = []
        self.skipped_tests: Set[str] = set()  # Track tests to skip in original suites
        
    def load_tests(self) -> List[Dict[str, Any]]:
        """Load guardrails tests by routing to existing suites."""
        if not self.guardrails_config:
            logger.info("No guardrails configuration provided, skipping guardrails suite")
            return []
        
        logger.info("Loading guardrails composite suite")
        
        # Generate subtests based on configuration
        self._generate_subtests()
        
        # Load tests from underlying suites
        all_tests = []
        for subtest in self.subtests:
            if subtest.enabled and not subtest.skip_reason:
                tests = self._load_subtest(subtest)
                all_tests.extend(tests)
            elif subtest.skip_reason:
                # Add skipped test entry
                all_tests.append({
                    "test_id": f"guardrails_{subtest.name}",
                    "test_type": "guardrails",
                    "subtest": subtest.name,
                    "suite": subtest.suite,
                    "status": "SKIPPED",
                    "reason": subtest.skip_reason,
                    "guardrails": True
                })
        
        logger.info(f"Loaded {len(all_tests)} guardrails tests")
        return all_tests
    
    def _generate_subtests(self):
        """Generate subtest configurations based on guardrails options."""
        config = self.guardrails_config
        
        # PII/PHI Leak Detection
        self.subtests.append(GuardrailsSubtest(
            name="pii_leak",
            suite="safety",
            enabled=config.pii.enable,
            config={
                "detectors": config.pii.detectors,
                "custom_regex": config.pii.custom_regex,
                "mask_policy": config.pii.mask_policy,
                "use_guardrails_pii": True  # Flag to use new PII scan module
            },
            tags=["input_scan", "output_scan", "pii"]
        ))
        
        # Jailbreak & Obfuscation
        self.subtests.append(GuardrailsSubtest(
            name="jailbreak",
            suite="red_team",
            enabled=config.jailbreak.enable,
            config={
                "variants": config.jailbreak.variants,
                "templates_path": "data/red_team/attacks_guardrails.yaml",  # Use guardrails templates
                "use_guardrails_templates": True  # Flag to use new guardrails templates
            },
            tags=config.jailbreak.variants + ["guardrails", "jailbreak"]
        ))
        
        # JSON/Schema Guard
        self.subtests.append(GuardrailsSubtest(
            name="schema_guard",
            suite="rag_structure_eval",
            enabled=config.schema_guard.enable,
            config={
                "fail_on_violation": config.schema_guard.fail_on_violation,
                "json_schema_file": config.schema_guard.json_schema_file
            },
            tags=["json_schema_valid"]
        ))
        
        # Citation Required - check if RAG is available
        citation_skip_reason = None
        if config.citation.enable:
            rag_suites = {"rag_quality", "rag_reliability_robustness", "rag_structure_eval"}
            if not any(suite in self.request.suites for suite in rag_suites):
                citation_skip_reason = "RAG suites not selected - citation validation requires RAG"
        
        self.subtests.append(GuardrailsSubtest(
            name="citation_required",
            suite="rag_quality",
            enabled=config.citation.enable,
            config={
                "min_sources": config.citation.min_sources,
                "source_allowlist": config.citation.source_allowlist
            },
            tags=["citation_min_sources"],
            skip_reason=citation_skip_reason
        ))
        
        # Resilience
        self.subtests.append(GuardrailsSubtest(
            name="resilience",
            suite="resilience",
            enabled=config.resilience.enable,
            config={
                "long_input_tokens": config.resilience.long_input_tokens,
                "repeat_tokens": config.resilience.repeat_tokens,
                "unicode_classes": config.resilience.unicode_classes
            },
            tags=["long_input", "unicode_adversarial", "gibberish_noise"]
        ))
        
        # Tool/MCP Governance
        self.subtests.append(GuardrailsSubtest(
            name="mcp_governance",
            suite="mcp_security",
            enabled=config.mcp.enable,
            config={
                "allowed_tools": config.mcp.allowed_tools,
                "max_call_depth": config.mcp.max_call_depth,
                "max_calls": config.mcp.max_calls
            },
            tags=["allowed_tools_only", "max_depth", "max_calls"]
        ))
        
        # Rate/Cost Limits
        self.subtests.append(GuardrailsSubtest(
            name="rate_cost_limits",
            suite="performance",
            enabled=config.rate_cost.enable,
            config={
                "max_rps": config.rate_cost.max_rps,
                "max_tokens_per_request": config.rate_cost.max_tokens_per_request,
                "budget_usd_per_run": config.rate_cost.budget_usd_per_run
            },
            tags=["rate_limit_obeyed", "token_budget_respected"]
        ))
        
        # Bias/Fairness
        bias_suite = "bias_smoke" if config.bias.mode == "smoke" else "bias"
        self.subtests.append(GuardrailsSubtest(
            name="bias_fairness",
            suite=bias_suite,
            enabled=config.bias.enable,
            config={
                "mode": config.bias.mode,
                "categories": config.bias.categories
            },
            tags=config.bias.categories
        ))
    
    def _load_subtest(self, subtest: GuardrailsSubtest) -> List[Dict[str, Any]]:
        """Load tests for a specific guardrails subtest."""
        logger.debug(f"Loading subtest {subtest.name} from suite {subtest.suite}")
        
        # Get the appropriate loader method from test runner
        loader_method = getattr(self.test_runner, f"_load_{subtest.suite}_tests", None)
        if not loader_method:
            logger.warning(f"No loader found for suite {subtest.suite}")
            return []
        
        # Load tests from the underlying suite
        try:
            # Temporarily modify request options to include subtest config
            original_options = self.request.options or {}
            modified_options = original_options.copy()
            
            # Merge subtest config into existing suite options
            existing_suite_opts = modified_options.get(subtest.suite, {})
            existing_suite_opts.update(subtest.config)
            modified_options[subtest.suite] = existing_suite_opts
            
            # Temporarily set options
            self.request.options = modified_options
            
            # Load tests
            tests = loader_method()
            
            # Restore original options
            self.request.options = original_options
            
            # Tag tests as guardrails and filter by tags if needed
            filtered_tests = []
            for test in tests:
                # Check if test matches subtest tags
                if self._test_matches_tags(test, subtest.tags):
                    test["guardrails"] = True
                    test["guardrails_subtest"] = subtest.name
                    test["guardrails_suite"] = subtest.suite
                    filtered_tests.append(test)
                    
                    # Track for deduplication if mode is "dedupe"
                    if self.guardrails_config.mode == "dedupe":
                        test_key = f"{subtest.suite}:{test.get('test_id', '')}"
                        self.skipped_tests.add(test_key)
            
            logger.debug(f"Loaded {len(filtered_tests)} tests for subtest {subtest.name}")
            return filtered_tests
            
        except Exception as e:
            logger.error(f"Failed to load subtest {subtest.name}: {e}")
            return []
    
    def _test_matches_tags(self, test: Dict[str, Any], tags: List[str]) -> bool:
        """Check if a test matches the required tags."""
        if not tags:
            return True
        
        # Check various fields that might contain tags
        test_tags = []
        
        # Check test type, category, subtype
        test_tags.extend([
            test.get("test_type", ""),
            test.get("category", ""),
            test.get("subtype", ""),
            test.get("attack_type", ""),
            test.get("variant", "")
        ])
        
        # Check if any required tag matches
        for tag in tags:
            if any(tag.lower() in str(test_tag).lower() for test_tag in test_tags if test_tag):
                return True
        
        # If no specific tags match, include the test (broad matching)
        return True
    
    def should_skip_test(self, suite: str, test_id: str) -> Optional[str]:
        """Check if a test should be skipped due to guardrails deduplication."""
        if self.guardrails_config and self.guardrails_config.mode == "dedupe":
            test_key = f"{suite}:{test_id}"
            if test_key in self.skipped_tests:
                return "covered-by-guardrails"
        return None


def load_guardrails_tests(request, test_runner) -> List[Dict[str, Any]]:
    """Load guardrails tests using the composite suite."""
    suite = GuardrailsSuite(request, test_runner)
    return suite.load_tests()
