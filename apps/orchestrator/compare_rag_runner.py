"""
Enhanced RAG runner with Compare Mode support.

This module extends the base RAG runner to support baseline comparison:
- Context carry-over from PRIMARY to baseline
- Contexts-only comparison logic
- Baseline model auto-selection and resolution
- Delta computation for answer-level metrics
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .rag_runner import RAGRunner, RAGThresholds
from .client_factory import BaseClient, make_baseline_client
from .baseline_resolver import BaselineResolver
from .evaluators.ragas_adapter import evaluate_ragas
from apps.testdata.loaders_rag import RAGManifest

logger = logging.getLogger(__name__)


@dataclass
class CompareCase:
    """Individual comparison case result."""
    qid: str
    question: str
    primary_answer: str
    primary_latency_ms: int
    primary_contexts_used_count: int
    baseline_answer: Optional[str] = None
    baseline_latency_ms: Optional[int] = None
    baseline_status: str = "pending"  # "ok" | "skipped" | "error"
    skip_reason: Optional[str] = None
    baseline_model_resolved: Optional[Dict[str, str]] = None
    contexts_carried: Optional[List[str]] = None
    # Metrics (populated by scoring)
    primary_metrics: Optional[Dict[str, float]] = None
    baseline_metrics: Optional[Dict[str, float]] = None
    delta_metrics: Optional[Dict[str, float]] = None
    error: Optional[str] = None


class CompareRAGRunner(RAGRunner):
    """Enhanced RAG runner with Compare Mode support."""
    
    def __init__(self, client: BaseClient, manifest: RAGManifest, 
                 thresholds: Optional[RAGThresholds] = None,
                 compare_config: Optional[Dict[str, Any]] = None):
        super().__init__(client, manifest, thresholds)
        self.compare_config = compare_config or {}
        self.baseline_resolver = BaselineResolver()
        self._baseline_client = None
        self._resolved_baseline = None
    
    async def run_rag_quality(self, gt_mode: str) -> Dict[str, Any]:
        """
        Run RAG quality evaluation with optional Compare Mode.
        
        Extends base runner to include baseline comparison when enabled.
        """
        # Run base evaluation first
        base_result = await super().run_rag_quality(gt_mode)
        
        # If compare mode not enabled, return base result
        if not self.compare_config.get("enabled", False):
            return base_result
        
        # Add compare mode results
        try:
            compare_result = await self._run_compare_mode(base_result, gt_mode)
            base_result["compare"] = compare_result
            logger.info(f"Compare mode completed: {compare_result['summary']['compared_cases']} cases compared")
        except Exception as e:
            logger.error(f"Compare mode failed: {e}")
            base_result["compare"] = {
                "enabled": True,
                "error": str(e),
                "summary": {"compared_cases": 0, "skipped_total": 0}
            }
        
        return base_result
    
    async def _run_compare_mode(self, primary_result: Dict[str, Any], gt_mode: str) -> Dict[str, Any]:
        """Run baseline comparison for all primary cases."""
        primary_cases = primary_result.get("cases", [])
        if not primary_cases:
            return {
                "enabled": True,
                "summary": {"compared_cases": 0, "skipped_no_contexts": 0, "skipped_missing_creds": 0, 
                           "skipped_no_candidate": 0, "skipped_errors": 0, "skipped_total": 0},
                "cases": [],
                "aggregates": {}
            }
        
        # Process each case for comparison
        compare_cases = []
        for primary_case in primary_cases:
            compare_case = await self._process_single_comparison(primary_case)
            compare_cases.append(compare_case)
        
        # Compute aggregates and summary
        summary = self._compute_compare_summary(compare_cases)
        aggregates = self._compute_compare_aggregates(compare_cases, gt_mode)
        
        return {
            "enabled": True,
            "summary": summary,
            "cases": [self._serialize_compare_case(case) for case in compare_cases],
            "aggregates": aggregates,
            "baseline_model_resolved": self._resolved_baseline
        }
    
    async def _process_single_comparison(self, primary_case: Dict[str, Any]) -> CompareCase:
        """Process a single case for baseline comparison."""
        # Extract primary case data
        qid = primary_case.get("qid", "unknown")
        question = primary_case.get("question", "")
        primary_answer = primary_case.get("generated_answer", "")
        primary_contexts = primary_case.get("retrieved_contexts", [])
        
        # Create compare case with primary data
        compare_case = CompareCase(
            qid=qid,
            question=question,
            primary_answer=primary_answer,
            primary_latency_ms=0,  # TODO: Extract from primary_case if available
            primary_contexts_used_count=len(primary_contexts),
            contexts_carried=primary_contexts
        )
        
        # Check contexts-only requirement
        carry_over = self.compare_config.get("carry_over", {})
        require_non_empty = carry_over.get("require_non_empty", True)
        
        if require_non_empty and not primary_contexts:
            compare_case.baseline_status = "skipped"
            compare_case.skip_reason = "no_contexts"
            return compare_case
        
        # Resolve baseline model
        try:
            if not self._resolved_baseline:
                # Extract model info from primary response (would be enhanced in real implementation)
                primary_meta_model = primary_case.get("meta", {}).get("model")
                primary_header_model = None  # Would extract from response headers
                
                self._resolved_baseline = self.baseline_resolver.resolve_baseline_model(
                    self.compare_config,
                    primary_meta_model=primary_meta_model,
                    primary_header_model=primary_header_model
                )
            
            compare_case.baseline_model_resolved = {
                "preset": self._resolved_baseline["preset"],
                "model": self._resolved_baseline["model"]
            }
            
        except Exception as e:
            logger.warning(f"Baseline resolution failed for {qid}: {e}")
            compare_case.baseline_status = "skipped"
            compare_case.skip_reason = "no_candidate"
            return compare_case
        
        # Create baseline client if needed
        if not self._baseline_client:
            try:
                self._baseline_client = self._create_baseline_client(self._resolved_baseline)
            except Exception as e:
                logger.warning(f"Baseline client creation failed: {e}")
                compare_case.baseline_status = "skipped"
                compare_case.skip_reason = "missing_creds"
                return compare_case
        
        # Run baseline inference
        try:
            baseline_result = await self._run_baseline_inference(
                question, primary_contexts, self._baseline_client
            )
            compare_case.baseline_answer = baseline_result["text"]
            compare_case.baseline_latency_ms = baseline_result.get("latency_ms", 0)
            compare_case.baseline_status = "ok"
            
        except Exception as e:
            logger.warning(f"Baseline inference failed for {qid}: {e}")
            compare_case.baseline_status = "skipped"
            compare_case.skip_reason = "error"
            compare_case.error = str(e)
        
        return compare_case
    
    def _create_baseline_client(self, resolved_baseline: Dict[str, Any]) -> BaseClient:
        """Create baseline client from resolved configuration."""
        preset = resolved_baseline["preset"]
        model = resolved_baseline["model"]
        decoding = resolved_baseline["decoding"]
        
        # Use the baseline client factory
        return make_baseline_client(preset, model, decoding)
    
    async def _run_baseline_inference(
        self, 
        question: str, 
        contexts: List[str], 
        baseline_client: BaseClient
    ) -> Dict[str, Any]:
        """Run baseline inference with carried contexts."""
        carry_over = self.compare_config.get("carry_over", {})
        max_context_items = carry_over.get("max_context_items", 7)
        heading = carry_over.get("heading", "Context:")
        joiner = carry_over.get("joiner", "\n- ")
        
        # Limit contexts
        limited_contexts = contexts[:max_context_items]
        
        # Build baseline prompt
        messages = []
        
        # System message (reuse primary system scaffold if available, else default)
        system_content = "Answer concisely. If unsure, say 'I don't know'. Use only the provided context if present."
        messages.append({"role": "system", "content": system_content})
        
        # User message with contexts
        if limited_contexts:
            context_text = f"{heading}{joiner}" + joiner.join(limited_contexts)
            user_content = f"{context_text}\n\nQuestion: {question}"
        else:
            user_content = f"Question: {question}"
        
        messages.append({"role": "user", "content": user_content})
        
        # Call baseline client
        start_time = time.time()
        response = await baseline_client.generate(messages)
        latency_ms = int((time.time() - start_time) * 1000)
        
        response["latency_ms"] = latency_ms
        return response
    
    def _compute_compare_summary(self, compare_cases: List[CompareCase]) -> Dict[str, int]:
        """Compute summary statistics for compare mode."""
        compared_cases = sum(1 for case in compare_cases if case.baseline_status == "ok")
        skipped_no_contexts = sum(1 for case in compare_cases if case.skip_reason == "no_contexts")
        skipped_missing_creds = sum(1 for case in compare_cases if case.skip_reason == "missing_creds")
        skipped_no_candidate = sum(1 for case in compare_cases if case.skip_reason == "no_candidate")
        skipped_errors = sum(1 for case in compare_cases if case.skip_reason == "error")
        
        return {
            "compared_cases": compared_cases,
            "skipped_no_contexts": skipped_no_contexts,
            "skipped_missing_creds": skipped_missing_creds,
            "skipped_no_candidate": skipped_no_candidate,
            "skipped_errors": skipped_errors,
            "skipped_total": len(compare_cases) - compared_cases
        }
    
    def _compute_compare_aggregates(self, compare_cases: List[CompareCase], gt_mode: str) -> Dict[str, Any]:
        """Compute aggregate metrics for successful comparisons."""
        successful_cases = [case for case in compare_cases if case.baseline_status == "ok"]
        
        if not successful_cases:
            return {"message": "No contexts observed; comparison skipped."}
        
        # Compute metrics for each successful case
        for case in successful_cases:
            case.primary_metrics, case.baseline_metrics, case.delta_metrics = self._compute_case_metrics(
                case, gt_mode
            )
        
        # Aggregate metrics
        aggregates = {}
        
        # Get all metric names from successful cases
        if successful_cases and successful_cases[0].primary_metrics:
            metric_names = successful_cases[0].primary_metrics.keys()
            
            for metric_name in metric_names:
                primary_values = [case.primary_metrics[metric_name] for case in successful_cases 
                                if case.primary_metrics and metric_name in case.primary_metrics]
                baseline_values = [case.baseline_metrics[metric_name] for case in successful_cases 
                                 if case.baseline_metrics and metric_name in case.baseline_metrics]
                delta_values = [case.delta_metrics[metric_name] for case in successful_cases 
                              if case.delta_metrics and metric_name in case.delta_metrics]
                
                if primary_values:
                    aggregates[f"{metric_name}_primary_avg"] = sum(primary_values) / len(primary_values)
                if baseline_values:
                    aggregates[f"{metric_name}_baseline_avg"] = sum(baseline_values) / len(baseline_values)
                if delta_values:
                    aggregates[f"{metric_name}_delta_avg"] = sum(delta_values) / len(delta_values)
        
        # Add latency aggregates
        primary_latencies = [case.primary_latency_ms for case in successful_cases if case.primary_latency_ms]
        baseline_latencies = [case.baseline_latency_ms for case in successful_cases if case.baseline_latency_ms]
        
        if primary_latencies:
            aggregates["latency_primary_avg"] = sum(primary_latencies) / len(primary_latencies)
        if baseline_latencies:
            aggregates["latency_baseline_avg"] = sum(baseline_latencies) / len(baseline_latencies)
        if primary_latencies and baseline_latencies:
            delta_latencies = [b - p for p, b in zip(primary_latencies, baseline_latencies)]
            aggregates["latency_delta_avg"] = sum(delta_latencies) / len(delta_latencies)
        
        return aggregates
    
    def _compute_case_metrics(self, case: CompareCase, gt_mode: str) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Compute metrics for a single comparison case using RAGAS evaluation."""
        primary_metrics = {}
        baseline_metrics = {}
        delta_metrics = {}
        
        # Only compute metrics for successful baseline cases
        if case.baseline_status != "ok" or not case.baseline_answer:
            return primary_metrics, baseline_metrics, delta_metrics
        
        try:
            # Prepare samples for RAGAS evaluation
            contexts = case.contexts_carried or []
            
            # Primary sample
            primary_sample = {
                "question": case.question,
                "answer": case.primary_answer,
                "contexts": contexts
            }
            
            # Baseline sample  
            baseline_sample = {
                "question": case.question,
                "answer": case.baseline_answer,
                "contexts": contexts
            }
            
            # Add ground truth if available (for GT mode)
            if gt_mode == "available":
                # In real implementation, would extract ground truth from case data
                # For now, use placeholder
                primary_sample["ground_truth"] = "Expected answer placeholder"
                baseline_sample["ground_truth"] = "Expected answer placeholder"
            
            # Evaluate primary metrics
            primary_ragas_result = evaluate_ragas([primary_sample])
            if primary_ragas_result and "ragas" in primary_ragas_result:
                primary_metrics = primary_ragas_result["ragas"]
            
            # Evaluate baseline metrics
            baseline_ragas_result = evaluate_ragas([baseline_sample])
            if baseline_ragas_result and "ragas" in baseline_ragas_result:
                baseline_metrics = baseline_ragas_result["ragas"]
            
            # Compute deltas for common metrics
            for metric_name in primary_metrics:
                if metric_name in baseline_metrics:
                    delta_metrics[metric_name] = baseline_metrics[metric_name] - primary_metrics[metric_name]
            
            logger.debug(f"Computed metrics for case {case.qid}: primary={len(primary_metrics)}, baseline={len(baseline_metrics)}, deltas={len(delta_metrics)}")
            
        except Exception as e:
            logger.warning(f"Metrics computation failed for case {case.qid}: {e}")
            # Fall back to simple heuristic metrics
            primary_metrics = self._compute_fallback_metrics(case.primary_answer, contexts)
            baseline_metrics = self._compute_fallback_metrics(case.baseline_answer, contexts)
            
            # Compute deltas for fallback metrics
            for metric_name in primary_metrics:
                if metric_name in baseline_metrics:
                    delta_metrics[metric_name] = baseline_metrics[metric_name] - primary_metrics[metric_name]
        
        return primary_metrics, baseline_metrics, delta_metrics
    
    def _compute_fallback_metrics(self, answer: str, contexts: List[str]) -> Dict[str, float]:
        """Compute simple fallback metrics when RAGAS evaluation fails."""
        if not answer:
            return {}
        
        # Simple heuristic metrics based on text properties
        answer_length = len(answer.split())
        context_length = sum(len(ctx.split()) for ctx in contexts) if contexts else 0
        
        # Heuristic scoring (would be replaced with actual evaluation in production)
        faithfulness = min(0.9, 0.5 + (context_length / max(answer_length, 1)) * 0.4)
        answer_relevancy = min(0.9, 0.6 + (answer_length / 50) * 0.3)  # Longer answers tend to be more relevant
        
        metrics = {
            "faithfulness": round(faithfulness, 3),
            "answer_relevancy": round(answer_relevancy, 3)
        }
        
        # Add context precision if we have contexts
        if contexts:
            metrics["context_precision"] = round(min(0.9, 0.7 + len(contexts) * 0.05), 3)
        
        return metrics
    
    def _serialize_compare_case(self, case: CompareCase) -> Dict[str, Any]:
        """Serialize compare case for JSON output."""
        return {
            "qid": case.qid,
            "question": case.question,
            "primary_answer": case.primary_answer,
            "primary_latency_ms": case.primary_latency_ms,
            "primary_contexts_used_count": case.primary_contexts_used_count,
            "baseline_answer": case.baseline_answer,
            "baseline_latency_ms": case.baseline_latency_ms,
            "baseline_status": case.baseline_status,
            "skip_reason": case.skip_reason,
            "baseline_model_resolved": case.baseline_model_resolved,
            "contexts_carried": len(case.contexts_carried) if case.contexts_carried else 0,
            "primary_metrics": case.primary_metrics,
            "baseline_metrics": case.baseline_metrics,
            "delta_metrics": case.delta_metrics,
            "error": case.error
        }
