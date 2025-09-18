"""Metamorphic and counterfactual consistency checking for test quality."""

import re
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
import logging

from .schema_v2 import TestCaseV2
from .oracles import EvaluationResult

logger = logging.getLogger(__name__)


class MetamorphicGroup:
    """A group of test cases that should show consistent behavior."""
    
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.cases: List[TestCaseV2] = []
        self.results: Dict[str, EvaluationResult] = {}
        self.consistency_violations: List[str] = []
    
    def add_case(self, case: TestCaseV2):
        """Add a test case to this metamorphic group."""
        self.cases.append(case)
    
    def add_result(self, case_id: str, result: EvaluationResult):
        """Add evaluation result for a case in this group."""
        self.results[case_id] = result
    
    def check_consistency(self) -> bool:
        """Check if all cases in the group show consistent outcomes."""
        if len(self.results) < 2:
            return True  # Not enough results to check consistency
        
        # Check pass/fail consistency
        outcomes = [result.passed for result in self.results.values()]
        first_outcome = outcomes[0]
        
        violations = []
        
        for case, outcome in zip(self.cases, outcomes):
            if outcome != first_outcome:
                violations.append(
                    f"Case {case.test_id} outcome {outcome} differs from group consensus {first_outcome}"
                )
        
        self.consistency_violations = violations
        return len(violations) == 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of this metamorphic group."""
        return {
            "group_id": self.group_id,
            "case_count": len(self.cases),
            "evaluated_count": len(self.results),
            "is_consistent": len(self.consistency_violations) == 0,
            "violations": self.consistency_violations
        }


class CounterfactualPair:
    """A pair of test cases that should behave consistently except for specific substitutions."""
    
    def __init__(self, case_a: TestCaseV2, case_b: TestCaseV2, substitution: Dict[str, str]):
        self.case_a = case_a
        self.case_b = case_b
        self.substitution = substitution  # e.g., {"female": "male"}
        self.result_a: Optional[EvaluationResult] = None
        self.result_b: Optional[EvaluationResult] = None
    
    def add_results(self, result_a: EvaluationResult, result_b: EvaluationResult):
        """Add evaluation results for both cases."""
        self.result_a = result_a
        self.result_b = result_b
    
    def check_parity(self, tolerance: float = 0.1) -> bool:
        """Check if the pair shows acceptable parity."""
        if not self.result_a or not self.result_b:
            return True  # Can't check without both results
        
        # For pass/fail, they should match
        if self.result_a.passed != self.result_b.passed:
            return False
        
        # For scored results, check score difference
        if self.result_a.score is not None and self.result_b.score is not None:
            score_diff = abs(self.result_a.score - self.result_b.score)
            if score_diff > tolerance:
                return False
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of this counterfactual pair."""
        has_parity = self.check_parity()
        
        summary = {
            "case_a_id": self.case_a.test_id,
            "case_b_id": self.case_b.test_id,
            "substitution": self.substitution,
            "has_parity": has_parity
        }
        
        if self.result_a and self.result_b:
            summary.update({
                "outcome_a": self.result_a.passed,
                "outcome_b": self.result_b.passed,
                "score_a": self.result_a.score,
                "score_b": self.result_b.score
            })
        
        return summary


class MetamorphicGenerator:
    """Generator for creating metamorphic test variants."""
    
    PUNCTUATION_VARIANTS = [
        (".", "!"),
        ("?", "."),
        ("", "."),
        (".", "")
    ]
    
    POLITENESS_PREFIXES = [
        "Please ",
        "Could you please ",
        "Would you kindly ",
        ""
    ]
    
    ORDER_INVERSIONS = [
        # Simple inversions for compound questions
        (r"(.+?) and (.+?)(\?|\.)", r"\2 and \1\3"),
        (r"(.+?) or (.+?)(\?|\.)", r"\2 or \1\3")
    ]
    
    @staticmethod
    def generate_punctuation_variant(original_query: str) -> str:
        """Generate a variant with different punctuation."""
        import random
        old_punct, new_punct = random.choice(MetamorphicGenerator.PUNCTUATION_VARIANTS)
        
        if old_punct and original_query.endswith(old_punct):
            return original_query[:-len(old_punct)] + new_punct
        elif not old_punct and not original_query.endswith(('.', '!', '?')):
            return original_query + new_punct
        
        return original_query
    
    @staticmethod
    def generate_politeness_variant(original_query: str) -> str:
        """Generate a variant with different politeness level."""
        import random
        
        # Remove existing politeness prefix if present
        query = original_query
        for prefix in MetamorphicGenerator.POLITENESS_PREFIXES:
            if prefix and query.lower().startswith(prefix.lower()):
                query = query[len(prefix):]
                break
        
        # Add new politeness prefix
        new_prefix = random.choice(MetamorphicGenerator.POLITENESS_PREFIXES)
        return new_prefix + query
    
    @staticmethod
    def generate_order_variant(original_query: str) -> str:
        """Generate a variant with inverted order (where applicable)."""
        for pattern, replacement in MetamorphicGenerator.ORDER_INVERSIONS:
            if re.search(pattern, original_query):
                return re.sub(pattern, replacement, original_query)
        
        return original_query
    
    @classmethod
    def create_metamorphic_variants(cls, base_case: TestCaseV2, group_id: str) -> List[TestCaseV2]:
        """Create metamorphic variants of a base test case."""
        variants = []
        
        # Punctuation variant
        punct_query = cls.generate_punctuation_variant(base_case.query)
        if punct_query != base_case.query:
            punct_case = TestCaseV2(
                test_id=f"{base_case.test_id}_punct",
                query=punct_query,
                expected_answer=base_case.expected_answer,
                context=base_case.context,
                oracle_type=base_case.oracle_type,
                acceptance=base_case.acceptance,
                severity=base_case.severity,
                deterministic_seed=base_case.deterministic_seed,
                metamorphic_group=group_id,
                tags=(base_case.tags or []) + ["metamorphic", "punctuation"],
                unstable=None,
                metamorphic_break=None
            )
            variants.append(punct_case)
        
        # Politeness variant
        polite_query = cls.generate_politeness_variant(base_case.query)
        if polite_query != base_case.query:
            polite_case = TestCaseV2(
                test_id=f"{base_case.test_id}_polite",
                query=polite_query,
                expected_answer=base_case.expected_answer,
                context=base_case.context,
                oracle_type=base_case.oracle_type,
                acceptance=base_case.acceptance,
                severity=base_case.severity,
                deterministic_seed=base_case.deterministic_seed,
                metamorphic_group=group_id,
                tags=(base_case.tags or []) + ["metamorphic", "politeness"],
                unstable=None,
                metamorphic_break=None
            )
            variants.append(polite_case)
        
        return variants


class CounterfactualGenerator:
    """Generator for creating counterfactual test pairs."""
    
    DEMOGRAPHIC_SUBSTITUTIONS = [
        {"female": "male", "she": "he", "her": "his", "woman": "man"},
        {"young": "elderly", "youth": "senior", "teenager": "adult"},
        {"urban": "rural", "city": "countryside", "metropolitan": "small town"}
    ]
    
    @staticmethod
    def create_counterfactual_pair(
        base_case: TestCaseV2, 
        substitutions: Dict[str, str]
    ) -> Optional[CounterfactualPair]:
        """Create a counterfactual pair by applying substitutions."""
        
        # Apply substitutions to the query
        modified_query = base_case.query
        applied_subs = {}
        
        for original, replacement in substitutions.items():
            if original.lower() in modified_query.lower():
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(original) + r'\b'
                if re.search(pattern, modified_query, re.IGNORECASE):
                    modified_query = re.sub(pattern, replacement, modified_query, flags=re.IGNORECASE)
                    applied_subs[original] = replacement
        
        if not applied_subs:
            return None  # No substitutions were applicable
        
        # Create the counterfactual case
        counterfactual_case = TestCaseV2(
            test_id=f"{base_case.test_id}_cf",
            query=modified_query,
            expected_answer=base_case.expected_answer,  # Keep same expected answer
            context=base_case.context,
            oracle_type=base_case.oracle_type,
            acceptance=base_case.acceptance,
            severity=base_case.severity,
            deterministic_seed=base_case.deterministic_seed,
            metamorphic_group=f"cf_{base_case.test_id}",
            tags=(base_case.tags or []) + ["counterfactual", "bias_check"],
            unstable=None,
            metamorphic_break=None
        )
        
        return CounterfactualPair(base_case, counterfactual_case, applied_subs)


class MetamorphicChecker:
    """Main checker for metamorphic and counterfactual consistency."""
    
    def __init__(self):
        self.metamorphic_groups: Dict[str, MetamorphicGroup] = {}
        self.counterfactual_pairs: List[CounterfactualPair] = []
        self.violations: List[Dict[str, Any]] = []
    
    def register_case(self, case: TestCaseV2):
        """Register a test case for metamorphic checking."""
        if case.metamorphic_group:
            if case.metamorphic_group not in self.metamorphic_groups:
                self.metamorphic_groups[case.metamorphic_group] = MetamorphicGroup(case.metamorphic_group)
            
            self.metamorphic_groups[case.metamorphic_group].add_case(case)
    
    def add_result(self, case_id: str, case: TestCaseV2, result: EvaluationResult):
        """Add an evaluation result for consistency checking."""
        if case.metamorphic_group and case.metamorphic_group in self.metamorphic_groups:
            self.metamorphic_groups[case.metamorphic_group].add_result(case_id, result)
    
    def check_all_consistency(self) -> Dict[str, Any]:
        """Check consistency across all metamorphic groups."""
        total_groups = len(self.metamorphic_groups)
        consistent_groups = 0
        total_violations = 0
        
        for group in self.metamorphic_groups.values():
            is_consistent = group.check_consistency()
            if is_consistent:
                consistent_groups += 1
            else:
                total_violations += len(group.consistency_violations)
                
                # Record violations
                for violation in group.consistency_violations:
                    self.violations.append({
                        "type": "metamorphic_inconsistency",
                        "group_id": group.group_id,
                        "description": violation
                    })
        
        return {
            "total_groups": total_groups,
            "consistent_groups": consistent_groups,
            "total_violations": total_violations,
            "consistency_rate": consistent_groups / total_groups if total_groups > 0 else 1.0
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get complete summary of metamorphic checking."""
        consistency_summary = self.check_all_consistency()
        
        return {
            "metamorphic_groups": len(self.metamorphic_groups),
            "counterfactual_pairs": len(self.counterfactual_pairs),
            "metamorphic_breaks": consistency_summary["total_violations"],
            "consistency_rate": consistency_summary["consistency_rate"],
            "violations": self.violations
        }
