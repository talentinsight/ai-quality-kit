"""Red Team Reports v2 integration with PII masking and detailed metrics."""

import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from .execution_engine import ExecutionResult, EvaluationResult
from .suite_integration import ExecutionPlan

logger = logging.getLogger(__name__)


class PIIMasker:
    """PII masking utility for safe report generation."""
    
    @staticmethod
    def mask_prompt(prompt: str, max_length: int = 120) -> str:
        """Mask sensitive content in prompts for reports."""
        if not prompt:
            return "[empty]"
        
        # Truncate to max length
        truncated = prompt[:max_length]
        if len(prompt) > max_length:
            truncated += "..."
        
        # Mask potential sensitive patterns
        masked = PIIMasker._apply_masking_patterns(truncated)
        
        return masked
    
    @staticmethod
    def _apply_masking_patterns(text: str) -> str:
        """Apply masking patterns to text."""
        # Mask email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Mask phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        
        # Mask credit card numbers
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', text)
        
        # Mask SSN-like patterns
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        
        # Mask API keys and tokens (common patterns)
        text = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[TOKEN]', text)
        
        # Mask base64-like strings longer than 20 chars
        text = re.sub(r'\b[A-Za-z0-9+/]{20,}={0,2}\b', '[BASE64]', text)
        
        return text
    
    @staticmethod
    def redact_response(response: str, max_length: int = 200) -> str:
        """Redact LLM response for safe logging."""
        if not response:
            return "[no response]"
        
        # Truncate and mask
        truncated = response[:max_length]
        if len(response) > max_length:
            truncated += "..."
        
        masked = PIIMasker._apply_masking_patterns(truncated)
        
        return masked


class RedTeamReportsIntegration:
    """Integration for Red Team Reports v2 with comprehensive metrics."""
    
    def __init__(self):
        self.pii_masker = PIIMasker()
    
    def generate_adversarial_details_sheet(self, results: List[ExecutionResult]) -> List[Dict[str, Any]]:
        """Generate Adversarial_Details sheet data."""
        sheet_data = []
        
        for result in results:
            # Mask prompt for safe display (only first 120 chars)
            masked_prompt = self.pii_masker.mask_prompt(
                # We don't have the original prompt in ExecutionResult, so use placeholder
                f"[{result.family}] {result.technique} attack",
                max_length=120
            )
            
            row = {
                "item_id": result.item_id,
                "variant_id": result.variant_id or "",
                "family": result.family,
                "technique": result.technique,
                "language": result.lang,
                "channel": result.channel,
                "provenance": result.provenance,
                "prompt_preview": masked_prompt,  # Masked/redacted
                "evaluation": result.evaluation.value,
                "success": result.evaluation == EvaluationResult.SUCCESS,
                "blocked": result.evaluation == EvaluationResult.BLOCKED,
                "ambiguous": result.evaluation == EvaluationResult.AMBIGUOUS,
                "confidence": result.confidence,
                "latency_ms": result.latency_ms,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "reused_from_preflight": result.reused_from_preflight,
                "notes": result.notes or "",
                "risk_level": self._categorize_risk(result)
            }
            
            sheet_data.append(row)
        
        # Sort by family, then by success (failures first)
        sheet_data.sort(key=lambda x: (x["family"], not x["success"], x["item_id"]))
        
        return sheet_data
    
    def generate_coverage_sheet(self, plan: ExecutionPlan, results: List[ExecutionResult]) -> List[Dict[str, Any]]:
        """Generate Coverage sheet data."""
        sheet_data = []
        
        # Get execution stats by family/technique/language/channel
        stats = {}
        
        # Count planned items
        all_items = plan.items_to_execute + plan.reused_items
        for item in all_items:
            key = (item.family, item.technique, item.lang, item.channel.value)
            if key not in stats:
                stats[key] = {
                    "family": item.family,
                    "technique": item.technique,
                    "language": item.lang,
                    "channel": item.channel.value,
                    "planned": 0,
                    "executed": 0,
                    "reused": 0,
                    "success": 0,
                    "blocked": 0,
                    "ambiguous": 0
                }
            stats[key]["planned"] += 1
            
            if item in plan.reused_items:
                stats[key]["reused"] += 1
        
        # Count execution results
        for result in results:
            key = (result.family, result.technique, result.lang, result.channel)
            if key in stats:
                if result.reused_from_preflight:
                    # Already counted in reused above
                    pass
                else:
                    stats[key]["executed"] += 1
                
                # Count evaluation results
                if result.evaluation == EvaluationResult.SUCCESS:
                    stats[key]["success"] += 1
                elif result.evaluation == EvaluationResult.BLOCKED:
                    stats[key]["blocked"] += 1
                else:
                    stats[key]["ambiguous"] += 1
        
        # Convert to sheet format
        for key, data in stats.items():
            total_tested = data["executed"] + data["reused"]
            execution_rate = data["executed"] / data["planned"] if data["planned"] > 0 else 0.0
            success_rate = data["success"] / total_tested if total_tested > 0 else 0.0
            
            row = {
                "family": data["family"],
                "technique": data["technique"],
                "language": data["language"],
                "channel": data["channel"],
                "planned_count": data["planned"],
                "executed_count": data["executed"],
                "reused_count": data["reused"],
                "total_tested": total_tested,
                "execution_rate": execution_rate,
                "success_count": data["success"],
                "blocked_count": data["blocked"],
                "ambiguous_count": data["ambiguous"],
                "success_rate": success_rate,
                "coverage_status": "Complete" if execution_rate >= 0.8 else "Partial" if execution_rate > 0 else "Reused Only"
            }
            
            sheet_data.append(row)
        
        # Sort by family, then by success rate (highest first)
        sheet_data.sort(key=lambda x: (x["family"], -x["success_rate"], x["technique"]))
        
        return sheet_data
    
    def generate_summary_sheet(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Summary sheet data."""
        overall = summary["overall_metrics"]
        performance = summary["performance_metrics"]
        coverage = summary["coverage_metrics"]
        plan = summary["execution_plan"]
        corpus = summary["corpus_info"]
        
        return {
            # Overall ASR metrics
            "overall_asr": overall["overall_asr"],
            "overall_asr_percent": overall["success_rate_percent"],
            "total_items_tested": overall["total_items"],
            "success_count": overall["success_count"],
            "blocked_count": overall["blocked_count"],
            "ambiguous_count": overall["ambiguous_count"],
            
            # Coverage metrics
            "total_planned": coverage["total_planned"],
            "total_executed": coverage["total_executed"],
            "total_reused": coverage["total_reused"],
            "execution_rate": coverage["execution_rate"],
            
            # Performance metrics
            "total_latency_ms": performance["total_latency_ms"],
            "avg_latency_ms": performance["avg_latency_ms"],
            "p95_latency_ms": performance["p95_latency_ms"],
            "total_tokens": performance["total_tokens_in"] + performance["total_tokens_out"],
            "estimated_cost": performance["estimated_cost"],
            
            # Top failing families
            "worst_families": [
                {
                    "family": f["family"],
                    "asr_percent": f["asr"] * 100,
                    "success_count": f["success_count"],
                    "total_count": f["total_count"]
                }
                for f in summary["top_failing_families"]
            ],
            
            # Execution plan details
            "mutators_applied": plan["mutators_applied"],
            "sampling_enabled": plan["sampling_enabled"],
            "reused_from_preflight_count": plan["reused"],
            
            # Corpus information
            "builtin_corpus_version": corpus["builtin_version"],
            "builtin_corpus_hash": corpus["builtin_hash"],
            "builtin_corpus_count": corpus["builtin_count"],
            "families_supported": len(corpus["families"]),
            "mutators_available": len(corpus["mutators"]),
            
            # Run manifest
            "run_manifest": {
                "corpus_version": corpus["builtin_version"],
                "corpus_hash": corpus["builtin_hash"],
                "taxonomy_version": corpus.get("taxonomy_version", "1.0"),
                "mutators_applied": plan["mutators_applied"],
                "sampling_config": {
                    "enabled": plan["sampling_enabled"],
                    "qa_sample_size": plan.get("qa_sample_size")
                },
                "deduplication_enabled": True,  # Always enabled in this implementation
                "families_tested": list(set(f["family"] for f in summary["family_metrics"].keys()))
            }
        }
    
    def generate_json_report(self, results: List[ExecutionResult], plan: ExecutionPlan, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate JSON report with all Red Team data."""
        return {
            "red_team": {
                "summary": self.generate_summary_sheet(summary),
                "adversarial_details": self.generate_adversarial_details_sheet(results),
                "coverage": self.generate_coverage_sheet(plan, results),
                "family_metrics": summary["family_metrics"],
                "performance_metrics": summary["performance_metrics"],
                "execution_plan": summary["execution_plan"],
                "corpus_info": summary["corpus_info"]
            }
        }
    
    def _categorize_risk(self, result: ExecutionResult) -> str:
        """Categorize risk level based on result."""
        if result.evaluation == EvaluationResult.SUCCESS:
            if result.confidence >= 0.8:
                return "High"
            elif result.confidence >= 0.6:
                return "Medium"
            else:
                return "Low"
        elif result.evaluation == EvaluationResult.AMBIGUOUS:
            return "Medium"
        else:
            return "Low"
    
    def validate_privacy_compliance(self, report_data: Dict[str, Any]) -> List[str]:
        """Validate that report data complies with privacy requirements."""
        violations = []
        
        # Check adversarial details for raw prompts
        if "red_team" in report_data and "adversarial_details" in report_data["red_team"]:
            for item in report_data["red_team"]["adversarial_details"]:
                prompt_preview = item.get("prompt_preview", "")
                
                # Check if prompt preview is properly masked/truncated
                if len(prompt_preview) > 150:  # Should be truncated
                    violations.append(f"Prompt preview too long for item {item.get('item_id')}")
                
                # Check for potential PII patterns that weren't masked
                if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', prompt_preview):
                    violations.append(f"Unmasked email in item {item.get('item_id')}")
                
                if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', prompt_preview):
                    violations.append(f"Unmasked phone number in item {item.get('item_id')}")
        
        # Check that no raw LLM responses are included
        def check_for_raw_responses(data, path=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in ["response", "output", "llm_response", "raw_response"]:
                        violations.append(f"Raw response found at {path}.{key}")
                    else:
                        check_for_raw_responses(value, f"{path}.{key}")
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_for_raw_responses(item, f"{path}[{i}]")
        
        check_for_raw_responses(report_data)
        
        return violations
    
    def generate_privacy_safe_logs(self, results: List[ExecutionResult]) -> List[Dict[str, Any]]:
        """Generate privacy-safe log entries."""
        log_entries = []
        
        for result in results:
            # Only include metrics and IDs, no raw content
            entry = {
                "timestamp": "2024-01-15T12:00:00Z",  # Would be actual timestamp
                "item_id": result.item_id,
                "family": result.family,
                "technique": result.technique,
                "evaluation": result.evaluation.value,
                "latency_ms": result.latency_ms,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "confidence": result.confidence,
                "reused": result.reused_from_preflight,
                "channel": result.channel,
                "lang": result.lang
            }
            
            log_entries.append(entry)
        
        return log_entries
