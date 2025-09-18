"""Red Team suite integration with attack corpus and deduplication."""

import logging
import hashlib
from typing import Optional, Dict, Any, List, Set, Tuple
from dataclasses import dataclass

from .corpus_loader import AttackCorpusLoader, AttackItem, Provenance
from .execution_engine import RedTeamExecutionEngine, ExecutionResult, EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPlan:
    """Execution plan with deduplication and sampling applied."""
    items_to_execute: List[AttackItem]
    reused_items: List[AttackItem]
    total_planned: int
    family_breakdown: Dict[str, Dict[str, int]]
    mutator_config: Dict[str, Any]
    sampling_config: Dict[str, Any]


class RedTeamSuiteIntegration:
    """Integration layer for Red Team suite with corpus and deduplication."""
    
    def __init__(self, deduplication_service=None):
        self.corpus_loader = AttackCorpusLoader()
        self.execution_engine = RedTeamExecutionEngine()
        self.deduplication_service = deduplication_service
    
    def load_and_merge_corpora(self, user_corpus_data: Optional[Any] = None) -> Tuple[List[AttackItem], List[str]]:
        """Load and merge built-in and user corpora."""
        all_errors = []
        
        # Load user corpus if provided
        user_items = []
        if user_corpus_data:
            user_items, user_errors = self.corpus_loader.load_user_corpus(user_corpus_data)
            all_errors.extend(user_errors)
        
        # Merge corpora
        merged_items = self.corpus_loader.merge_corpora(user_items)
        
        logger.info(f"Loaded corpora: {len(self.corpus_loader.builtin_items)} built-in + {len(user_items)} user = {len(merged_items)} total")
        
        return merged_items, all_errors
    
    def apply_deduplication(self, items: List[AttackItem], model: str, rules_hash: str) -> Tuple[List[AttackItem], List[AttackItem]]:
        """Apply deduplication against Preflight quickset."""
        if not self.deduplication_service:
            return items, []
        
        items_to_execute = []
        reused_items = []
        
        # Check each item against Preflight quickset fingerprints
        for item in items:
            # Check for PI quickset reuse
            is_reused = False
            
            # Check against both PI quickset providers
            for provider_id in ["pi.quickset", "pi.quickset_guard"]:
                # Check ASR-level reuse
                asr_signal = self.deduplication_service.check_signal_reusable(
                    provider_id=provider_id,
                    metric_id="jailbreak",  # Stored with category as metric_id
                    stage="preflight",
                    model=model,
                    rules_hash=rules_hash
                )
                
                if asr_signal:
                    # Check if this item's family matches quickset items
                    quickset_items = asr_signal.details.get("quickset_items", {})
                    for quickset_item_id, quickset_data in quickset_items.items():
                        if quickset_data.get("family") == item.family:
                            # Mark as reused
                            reused_item = AttackItem(
                                id=item.id,
                                family=item.family,
                                technique=item.technique,
                                lang=item.lang,
                                prompt=item.prompt,
                                channel=item.channel,
                                expected_behavior=item.expected_behavior,
                                provenance=item.provenance,
                                notes=f"Reused from Preflight PI quickset ({quickset_item_id})",
                                risk=item.risk,
                                variant_id=item.variant_id,
                                base_id=item.base_id
                            )
                            reused_items.append(reused_item)
                            is_reused = True
                            break
                
                if is_reused:
                    break
            
            if not is_reused:
                items_to_execute.append(item)
        
        logger.info(f"Deduplication: {len(items_to_execute)} to execute, {len(reused_items)} reused from Preflight")
        
        return items_to_execute, reused_items
    
    def create_execution_plan(
        self,
        user_corpus_data: Optional[Any] = None,
        mutator_config: Optional[Dict[str, Any]] = None,
        sampling_config: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4",
        rules_hash: str = "default"
    ) -> Tuple[ExecutionPlan, List[str]]:
        """Create execution plan with all transformations applied."""
        
        # Default configurations
        if mutator_config is None:
            mutator_config = {
                "enabled": False,
                "mutators": [],
                "max_variants_per_item": 2
            }
        
        if sampling_config is None:
            sampling_config = {
                "enabled": False,
                "qa_sample_size": None
            }
        
        # Load and merge corpora
        merged_items, errors = self.load_and_merge_corpora(user_corpus_data)
        if not merged_items:
            return ExecutionPlan([], [], 0, {}, mutator_config, sampling_config), errors
        
        # Apply mutators
        mutated_items = self.corpus_loader.apply_mutators(merged_items, mutator_config)
        
        # Apply sampling
        sampled_items = self.corpus_loader.apply_sampling(mutated_items, sampling_config)
        
        # Apply deduplication
        items_to_execute, reused_items = self.apply_deduplication(sampled_items, model, rules_hash)
        
        # Create family breakdown
        family_breakdown = {}
        all_items = items_to_execute + reused_items
        
        for item in all_items:
            if item.family not in family_breakdown:
                family_breakdown[item.family] = {"planned": 0, "execute": 0, "reused": 0}
            family_breakdown[item.family]["planned"] += 1
            
            if item in items_to_execute:
                family_breakdown[item.family]["execute"] += 1
            else:
                family_breakdown[item.family]["reused"] += 1
        
        plan = ExecutionPlan(
            items_to_execute=items_to_execute,
            reused_items=reused_items,
            total_planned=len(all_items),
            family_breakdown=family_breakdown,
            mutator_config=mutator_config,
            sampling_config=sampling_config
        )
        
        return plan, errors
    
    async def execute_plan(self, plan: ExecutionPlan, llm_client, model: str) -> List[ExecutionResult]:
        """Execute the attack plan."""
        results = []
        
        # Execute items
        for item in plan.items_to_execute:
            try:
                result = await self.execution_engine.execute_attack_item(item, llm_client, model)
                results.append(result)
                
                # Log execution (metrics only, no raw content)
                logger.info(f"Executed {item.id} ({item.family}): {result.evaluation.value} "
                          f"({result.latency_ms:.1f}ms, {result.tokens_in}+{result.tokens_out} tokens)")
                
            except Exception as e:
                logger.error(f"Failed to execute item {item.id}: {e}")
        
        # Add reused items as results
        for item in plan.reused_items:
            # Create a result indicating reuse
            reused_result = ExecutionResult(
                item_id=item.id,
                variant_id=item.variant_id,
                family=item.family,
                technique=item.technique,
                lang=item.lang,
                channel=item.channel.value,
                provenance=item.provenance.value,
                evaluation=EvaluationResult.BLOCKED,  # Assume blocked from Preflight
                latency_ms=0.0,  # No execution time
                tokens_in=0,     # No tokens used
                tokens_out=0,
                confidence=0.9,  # High confidence in reuse
                notes=item.notes,
                reused_from_preflight=True
            )
            results.append(reused_result)
        
        logger.info(f"Execution complete: {len(plan.items_to_execute)} executed, {len(plan.reused_items)} reused")
        
        return results
    
    def generate_execution_summary(self, results: List[ExecutionResult], plan: ExecutionPlan) -> Dict[str, Any]:
        """Generate execution summary with metrics."""
        
        # Overall ASR metrics
        overall_metrics = self.execution_engine.compute_asr_metrics(results)
        
        # Family-specific metrics
        family_metrics = self.execution_engine.compute_family_metrics(results)
        
        # Coverage metrics
        planned_items = plan.items_to_execute + plan.reused_items
        coverage_metrics = self.execution_engine.compute_coverage_metrics(results, planned_items)
        
        # Performance metrics
        executed_results = [r for r in results if not r.reused_from_preflight]
        performance_metrics = {
            "total_latency_ms": sum(r.latency_ms for r in executed_results),
            "avg_latency_ms": sum(r.latency_ms for r in executed_results) / len(executed_results) if executed_results else 0,
            "p95_latency_ms": self._calculate_p95([r.latency_ms for r in executed_results]),
            "total_tokens_in": sum(r.tokens_in for r in executed_results),
            "total_tokens_out": sum(r.tokens_out for r in executed_results),
            "estimated_cost": self._estimate_cost(executed_results)
        }
        
        # Top failing families
        failing_families = []
        for family, metrics in family_metrics.items():
            if metrics["success_count"] > 0:
                failing_families.append({
                    "family": family,
                    "asr": metrics["overall_asr"],
                    "success_count": metrics["success_count"],
                    "total_count": metrics["total_items"]
                })
        
        failing_families.sort(key=lambda x: x["asr"], reverse=True)
        
        return {
            "overall_metrics": overall_metrics,
            "family_metrics": family_metrics,
            "coverage_metrics": coverage_metrics,
            "performance_metrics": performance_metrics,
            "top_failing_families": failing_families[:5],  # Top 5
            "execution_plan": {
                "total_planned": plan.total_planned,
                "executed": len(plan.items_to_execute),
                "reused": len(plan.reused_items),
                "family_breakdown": plan.family_breakdown,
                "mutators_applied": plan.mutator_config.get("mutators", []),
                "sampling_enabled": plan.sampling_config.get("enabled", False)
            },
            "corpus_info": self.corpus_loader.get_corpus_info()
        }
    
    def _calculate_p95(self, values: List[float]) -> float:
        """Calculate 95th percentile."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(0.95 * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def _estimate_cost(self, results: List[ExecutionResult]) -> float:
        """Estimate cost based on token usage."""
        total_input_tokens = sum(r.tokens_in for r in results)
        total_output_tokens = sum(r.tokens_out for r in results)
        
        # Rough cost estimation (GPT-4 pricing)
        input_cost = (total_input_tokens / 1000) * 0.03   # $0.03 per 1K input tokens
        output_cost = (total_output_tokens / 1000) * 0.06  # $0.06 per 1K output tokens
        
        return input_cost + output_cost
    
    def get_reuse_fingerprints(self, items: List[AttackItem]) -> Dict[str, str]:
        """Generate fingerprints for items for future deduplication."""
        fingerprints = {}
        
        for item in items:
            # Create fingerprint based on item content and metadata
            content = f"{item.family}:{item.technique}:{item.lang}:{item.prompt}"
            fingerprint = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
            fingerprints[item.id] = fingerprint
        
        return fingerprints
    
    def is_available(self) -> bool:
        """Check if the Red Team suite integration is available."""
        return self.corpus_loader.is_available()
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get status information for UI/monitoring."""
        corpus_info = self.corpus_loader.get_corpus_info()
        
        return {
            "available": self.is_available(),
            "corpus_info": corpus_info,
            "deduplication_enabled": self.deduplication_service is not None,
            "supported_languages": ["en", "tr"],
            "supported_channels": ["user", "tool_arg", "context"],
            "mutators_available": len(AttackCorpusLoader.MUTATORS),
            "families_supported": len(AttackCorpusLoader.VALID_FAMILIES)
        }
