#!/usr/bin/env python3
"""
Template-Schema Drift Validator.

Validates that all shipped templates can be successfully loaded and parsed
by their corresponding suite loaders, preventing template-schema drift.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.common.logging import get_logger, redact
from apps.common.errors import DatasetValidationError

logger = get_logger(__name__)


class TemplateValidator:
    """Validates templates against their corresponding schema loaders."""
    
    def __init__(self):
        self.project_root = project_root
        self.templates_dir = self.project_root / "data" / "templates"
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all_templates(self) -> bool:
        """
        Validate all templates against their schemas.
        
        Returns:
            True if all templates are valid, False otherwise
        """
        logger.info("Starting template validation...")
        
        # Define template-loader mappings
        template_configs = [
            {
                "suite": "red_team",
                "templates": ["attacks.yaml", "attacks.json", "attacks.jsonl"],
                "loader_module": "apps.orchestrator.suites.red_team.single_file_schemas",
                "loader_function": "parse_attacks_content"
            },
            {
                "suite": "safety",
                "templates": ["safety.yaml", "safety.json"],
                "loader_module": "apps.orchestrator.suites.safety.loader",
                "loader_function": "parse_safety_content"
            },
            {
                "suite": "bias",
                "templates": ["bias.yaml", "bias.json"],
                "loader_module": "apps.orchestrator.suites.bias.loader",
                "loader_function": "parse_bias_content"
            },
            {
                "suite": "performance",
                "templates": ["perf.yaml", "perf.json"],
                "loader_module": "apps.orchestrator.suites.performance.loader",
                "loader_function": "parse_perf_content"
            }
        ]
        
        all_valid = True
        
        for config in template_configs:
            suite_valid = self._validate_suite_templates(config)
            if not suite_valid:
                all_valid = False
        
        # Validate RAG templates (different structure)
        rag_valid = self._validate_rag_templates()
        if not rag_valid:
            all_valid = False
        
        # Report results
        self._report_results()
        
        return all_valid
    
    def _validate_suite_templates(self, config: Dict[str, Any]) -> bool:
        """Validate templates for a specific suite."""
        suite = config["suite"]
        templates = config["templates"]
        loader_module = config["loader_module"]
        loader_function = config["loader_function"]
        
        logger.info(f"Validating {suite} templates...")
        
        try:
            # Import the loader function
            module = __import__(loader_module, fromlist=[loader_function])
            loader_func = getattr(module, loader_function)
        except ImportError as e:
            self.errors.append(f"{suite}: Failed to import loader {loader_module}.{loader_function}: {e}")
            return False
        except AttributeError as e:
            self.errors.append(f"{suite}: Loader function {loader_function} not found in {loader_module}: {e}")
            return False
        
        suite_valid = True
        parsed_results = {}
        
        # Validate each template
        for template_name in templates:
            template_path = self.templates_dir / template_name
            
            if not template_path.exists():
                self.warnings.append(f"{suite}: Template {template_name} not found at {template_path}")
                continue
            
            try:
                # Read template content
                content = template_path.read_text(encoding='utf-8')
                
                # Parse using the suite's loader
                result = loader_func(content)
                parsed_results[template_name] = result
                
                logger.info(f"✓ {suite}/{template_name}: Successfully parsed")
                
            except Exception as e:
                self.errors.append(f"{suite}/{template_name}: Parsing failed: {redact(str(e))}")
                suite_valid = False
        
        # Check format parity (YAML/JSON should produce equivalent results)
        if len(parsed_results) >= 2:
            parity_valid = self._check_format_parity(suite, parsed_results)
            if not parity_valid:
                suite_valid = False
        
        return suite_valid
    
    def _validate_rag_templates(self) -> bool:
        """Validate RAG templates (passages and qaset)."""
        logger.info("Validating RAG templates...")
        
        rag_templates = [
            ("passages.template.jsonl", "apps.testdata.models", "validate_jsonl_content"),
            ("qaset.template.jsonl", "apps.testdata.models", "validate_jsonl_content")
        ]
        
        rag_valid = True
        
        for template_name, loader_module, loader_function in rag_templates:
            template_path = self.templates_dir / template_name
            
            if not template_path.exists():
                self.warnings.append(f"RAG: Template {template_name} not found at {template_path}")
                continue
            
            try:
                # Import the loader function
                module = __import__(loader_module, fromlist=[loader_function])
                loader_func = getattr(module, loader_function)
                
                # Read template content
                content = template_path.read_text(encoding='utf-8')
                
                # Determine record type based on template
                if "passages" in template_name:
                    from apps.testdata.models import PassageRecord
                    record_type = PassageRecord
                else:
                    from apps.testdata.models import QARecord
                    record_type = QARecord
                
                # Parse using the loader
                records, errors = loader_func(content, record_type)
                
                if errors:
                    error_messages = [f"Line {e.line_number}: {e.message}" for e in errors]
                    self.errors.append(f"RAG/{template_name}: Validation errors: {error_messages}")
                    rag_valid = False
                else:
                    logger.info(f"✓ RAG/{template_name}: Successfully parsed {len(records)} records")
                
            except Exception as e:
                self.errors.append(f"RAG/{template_name}: Parsing failed: {redact(str(e))}")
                rag_valid = False
        
        return rag_valid
    
    def _check_format_parity(self, suite: str, parsed_results: Dict[str, Any]) -> bool:
        """Check that different formats produce equivalent results."""
        # This is a simplified parity check - in practice, you might want more sophisticated comparison
        formats = list(parsed_results.keys())
        
        if len(formats) < 2:
            return True
        
        # Compare structure of first two formats
        first_format = formats[0]
        second_format = formats[1]
        
        first_result = parsed_results[first_format]
        second_result = parsed_results[second_format]
        
        try:
            # Basic structural comparison
            if hasattr(first_result, 'cases') and hasattr(second_result, 'cases'):
                if len(first_result.cases) != len(second_result.cases):
                    self.warnings.append(f"{suite}: Format parity issue - different number of cases between {first_format} and {second_format}")
                    return False
            elif hasattr(first_result, 'scenarios') and hasattr(second_result, 'scenarios'):
                if len(first_result.scenarios) != len(second_result.scenarios):
                    self.warnings.append(f"{suite}: Format parity issue - different number of scenarios between {first_format} and {second_format}")
                    return False
            elif hasattr(first_result, 'attacks') and hasattr(second_result, 'attacks'):
                if len(first_result.attacks) != len(second_result.attacks):
                    self.warnings.append(f"{suite}: Format parity issue - different number of attacks between {first_format} and {second_format}")
                    return False
            
            logger.info(f"✓ {suite}: Format parity check passed between {first_format} and {second_format}")
            return True
            
        except Exception as e:
            self.warnings.append(f"{suite}: Format parity check failed: {redact(str(e))}")
            return False
    
    def _report_results(self):
        """Report validation results."""
        print("\n" + "="*60)
        print("TEMPLATE VALIDATION RESULTS")
        print("="*60)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All templates validated successfully!")
        elif not self.errors:
            print(f"\n✅ All templates validated successfully (with {len(self.warnings)} warnings)")
        else:
            print(f"\n❌ Validation failed with {len(self.errors)} errors and {len(self.warnings)} warnings")


def main():
    """Main entry point."""
    validator = TemplateValidator()
    
    try:
        success = validator.validate_all_templates()
        
        if success:
            logger.info("Template validation completed successfully")
            sys.exit(0)
        else:
            logger.error("Template validation failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Template validation crashed: {redact(str(e))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
