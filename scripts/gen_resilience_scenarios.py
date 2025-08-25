#!/usr/bin/env python3
"""Generate deterministic resilience scenario catalog for comprehensive testing."""

import os
import json
import random
import itertools
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


# Fixed seed for deterministic generation
DETERMINISTIC_SEED = 42

# Scenario parameters matrix
FAILURE_MODES = ["timeout", "upstream_5xx", "upstream_429", "circuit_open", "burst", "idle_stream"]
TARGET_TIMEOUTS = [15000, 20000, 30000]  # milliseconds
CONCURRENCY_LEVELS = [5, 10]
CIRCUIT_FAILS = [3, 5]
CIRCUIT_RESET_S = [15, 30]
PAYLOAD_SIZES = ["S", "M", "L"]

# Minimum target scenarios
MIN_SCENARIOS = 48


class ResilienceScenarioGenerator:
    """Generator for deterministic resilience test scenarios."""
    
    def __init__(self, base_date: Optional[str] = None):
        self.base_date = base_date or datetime.now().strftime("%Y%m%d")
        self.output_dir = Path(f"data/resilience_catalog/{self.base_date}")
        self.output_file = self.output_dir / "resilience.jsonl"
        
        # Set deterministic seed
        random.seed(DETERMINISTIC_SEED)
    
    def check_existing_catalog(self) -> bool:
        """Check if catalog already exists with sufficient scenarios."""
        if not self.output_file.exists():
            return False
        
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for line in f if line.strip())
            
            if line_count >= MIN_SCENARIOS:
                print(f"Existing catalog in {self.output_dir} already has {line_count} scenarios (≥{MIN_SCENARIOS})")
                return True
                
        except Exception as e:
            print(f"Warning: Could not read existing catalog: {e}")
        
        return False
    
    def generate_base_scenarios(self) -> List[Dict[str, Any]]:
        """Generate base scenario matrix covering all parameter combinations."""
        scenarios = []
        seq_id = 1
        
        # Generate all combinations of core parameters
        combinations = list(itertools.product(
            FAILURE_MODES,
            TARGET_TIMEOUTS,
            CONCURRENCY_LEVELS,
            CIRCUIT_FAILS,
            CIRCUIT_RESET_S,
            PAYLOAD_SIZES
        ))
        
        # Shuffle for deterministic but varied ordering
        random.shuffle(combinations)
        
        for failure_mode, timeout_ms, concurrency, circuit_fails, circuit_reset, payload_size in combinations:
            scenario = {
                "scenario_id": f"RZ-{self.base_date}-{seq_id:03d}",
                "failure_mode": failure_mode,
                "target_timeout_ms": timeout_ms,
                "retries": 0,  # Default 0 for resilience testing
                "concurrency": concurrency,
                "queue_depth": concurrency * 5,  # Queue depth typically 5x concurrency
                "circuit": {
                    "fails": circuit_fails,
                    "reset_s": circuit_reset
                },
                "fail_rate": self._get_fail_rate(failure_mode),
                "payload_size": payload_size,
                "notes": self._get_scenario_notes(failure_mode, timeout_ms, concurrency, payload_size)
            }
            
            scenarios.append(scenario)
            seq_id += 1
            
            # Break early if we have enough scenarios
            if len(scenarios) >= MIN_SCENARIOS:
                break
        
        return scenarios
    
    def _get_fail_rate(self, failure_mode: str) -> float:
        """Get appropriate failure rate for mock provider based on failure mode."""
        fail_rates = {
            "timeout": 0.3,       # 30% timeout rate
            "upstream_5xx": 0.2,  # 20% 5xx rate  
            "upstream_429": 0.15, # 15% rate limit rate
            "circuit_open": 0.4,  # 40% to trigger circuit breaker
            "burst": 0.1,         # 10% failure during load spike
            "idle_stream": 0.05   # 5% failure for idle streams
        }
        return fail_rates.get(failure_mode, 0.1)
    
    def _get_scenario_notes(self, failure_mode: str, timeout_ms: int, concurrency: int, payload_size: str) -> str:
        """Generate descriptive notes for the scenario."""
        mode_descriptions = {
            "timeout": "Request timeout simulation",
            "upstream_5xx": "Upstream server error simulation", 
            "upstream_429": "Rate limiting simulation",
            "circuit_open": "Circuit breaker activation test",
            "burst": "Load spike resilience test",
            "idle_stream": "TTFB and idle connection test"
        }
        
        base_desc = mode_descriptions.get(failure_mode, "Resilience test")
        return f"{base_desc} - {timeout_ms}ms timeout, {concurrency}x concurrent, {payload_size} payload"
    
    def generate_additional_scenarios(self, base_scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate additional specialized scenarios to ensure comprehensive coverage."""
        additional = []
        seq_id = len(base_scenarios) + 1
        
        # Add high-stress scenarios
        stress_scenarios = [
            {
                "failure_mode": "burst",
                "target_timeout_ms": 10000,  # Aggressive timeout
                "concurrency": 20,           # High concurrency
                "queue_depth": 100,
                "circuit": {"fails": 2, "reset_s": 60},  # Sensitive circuit
                "fail_rate": 0.2,
                "payload_size": "L",
                "notes": "High-stress burst test with aggressive timeouts"
            },
            {
                "failure_mode": "idle_stream", 
                "target_timeout_ms": 45000,  # Long timeout for idle
                "concurrency": 2,            # Low concurrency
                "queue_depth": 5,
                "circuit": {"fails": 10, "reset_s": 10},  # Tolerant circuit
                "fail_rate": 0.02,
                "payload_size": "S",
                "notes": "Long-lived idle connection resilience test"
            },
            {
                "failure_mode": "circuit_open",
                "target_timeout_ms": 5000,   # Very aggressive
                "concurrency": 15,
                "queue_depth": 75,
                "circuit": {"fails": 1, "reset_s": 120},  # Very sensitive
                "fail_rate": 0.8,
                "payload_size": "M", 
                "notes": "Rapid circuit breaker activation test"
            }
        ]
        
        for scenario_template in stress_scenarios:
            if len(base_scenarios) + len(additional) >= MIN_SCENARIOS:
                break
                
            scenario = {
                "scenario_id": f"RZ-{self.base_date}-{seq_id:03d}",
                "retries": 0,  # Always 0 for resilience
                **scenario_template
            }
            additional.append(scenario)
            seq_id += 1
        
        return additional
    
    def generate_catalog(self) -> List[Dict[str, Any]]:
        """Generate complete scenario catalog."""
        if self.check_existing_catalog():
            return []  # Already exists, idempotent
        
        print(f"Generating resilience scenario catalog for {self.base_date}...")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate base scenarios from parameter matrix
        scenarios = self.generate_base_scenarios()
        
        # Add additional specialized scenarios if needed
        if len(scenarios) < MIN_SCENARIOS:
            additional = self.generate_additional_scenarios(scenarios)
            scenarios.extend(additional)
        
        # Ensure we have enough scenarios
        scenarios = scenarios[:MIN_SCENARIOS] if len(scenarios) > MIN_SCENARIOS else scenarios
        
        # Write to JSONL file
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for scenario in scenarios:
                f.write(json.dumps(scenario) + '\n')
        
        print(f"Generated {len(scenarios)} resilience scenarios")
        self.print_summary(scenarios)
        
        return scenarios
    
    def print_summary(self, scenarios: List[Dict[str, Any]]):
        """Print generation summary with counts per failure mode."""
        print("\n" + "="*60)
        print("RESILIENCE SCENARIO CATALOG SUMMARY")
        print("="*60)
        print(f"Date: {self.base_date}")
        print(f"Output: {self.output_file}")
        print(f"Total scenarios: {len(scenarios)}")
        print()
        
        # Count by failure mode
        by_failure_mode = {}
        for scenario in scenarios:
            mode = scenario["failure_mode"]
            by_failure_mode[mode] = by_failure_mode.get(mode, 0) + 1
        
        print("Scenarios by failure mode:")
        for mode in FAILURE_MODES:
            count = by_failure_mode.get(mode, 0)
            print(f"  {mode:15} | {count:3d} scenarios")
        
        print()
        
        # Additional stats
        timeouts = set(s["target_timeout_ms"] for s in scenarios)
        concurrencies = set(s["concurrency"] for s in scenarios)
        payload_sizes = set(s["payload_size"] for s in scenarios)
        
        print(f"Timeout variants: {sorted(timeouts)}")
        print(f"Concurrency levels: {sorted(concurrencies)}")
        print(f"Payload sizes: {sorted(payload_sizes)}")
        print()
        
        if len(scenarios) >= MIN_SCENARIOS:
            print("✅ Scenario catalog meets minimum requirements!")
        else:
            print(f"⚠️  Need {MIN_SCENARIOS - len(scenarios)} more scenarios")


def main():
    """Main entry point."""
    import sys
    
    # Optional date argument
    base_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    generator = ResilienceScenarioGenerator(base_date)
    generator.generate_catalog()


if __name__ == "__main__":
    main()
