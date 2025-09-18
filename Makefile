.PHONY: test test-ci test-coverage clean quickcheck quickcheck.running requirements requirements-clean validate-templates go-no-go mcp-go-no-go

test:
	pytest -q --cov=apps --cov=llm --cov-report=term-missing --cov-report=html --ignore=evals --ignore=guardrails --ignore=safety

test-ci:
	pytest -q --cov=apps --cov=llm --cov-report=term-missing --cov-report=html --cov-fail-under=80 --ignore=evals --ignore=guardrails --ignore=safety

clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

quickcheck:
	QUICKCHECK_START_SERVER=true python3 scripts/quickcheck.py

quickcheck.running:
	QUICKCHECK_START_SERVER=false python3 scripts/quickcheck.py

# Requirements management
requirements:
	@echo "🔄 Updating requirements.txt with smart organizer..."
	@source .venv/bin/activate && python scripts/update_requirements.py

requirements-clean:
	@echo "🧹 Cleaning up requirements backup files..."
	@rm -f requirements.txt.backup.*
	@echo "✅ Backup files cleaned up"

requirements-freeze:
	@echo "📦 Creating requirements.txt from pip freeze..."
	@source .venv/bin/activate && pip freeze > requirements.txt
	@echo "✅ requirements.txt updated with all packages"

validate-templates:
	@echo "🔍 Validating templates against schemas..."
	@source .venv/bin/activate && python scripts/validate_templates.py
	@echo "✅ Template validation completed"

# Coverage testing with enforcement gate
test-coverage:
	@echo "🧪 Running tests with coverage enforcement..."
	@if [ "$(COVERAGE_ENFORCE)" = "1" ]; then \
		echo "⚠️  Coverage enforcement enabled (80% minimum)"; \
		source .venv/bin/activate && pytest --cov=apps/server/guardrails --cov=apps/orchestrator --cov=apps/reporters --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=80 tests/; \
	else \
		echo "ℹ️  Coverage enforcement disabled (set COVERAGE_ENFORCE=1 to enable)"; \
		source .venv/bin/activate && pytest --cov=apps/server/guardrails --cov=apps/orchestrator --cov=apps/reporters --cov-report=term-missing --cov-report=html:htmlcov tests/; \
	fi
	@echo "✅ Coverage report generated in htmlcov/"

# Go/No-Go validation harness
go-no-go:
	@echo "🚀 Running Go/No-Go validation harness..."
	@echo "📋 This will test the complete AI Quality Kit flow end-to-end"
	@source .venv/bin/activate && python scripts/go_no_go_validation_simple.py --verbose --output-dir go_no_go_results
	@echo "📊 Results and artifacts saved to go_no_go_results/"
	@echo "✅ Go/No-Go validation completed"

# MCP Go/No-Go validation harness
mcp-go-no-go:
	@echo "🚀 Running MCP Go/No-Go validation harness..."
	@echo "📋 This will test the MCP production harness end-to-end"
	@source .venv/bin/activate && PYTHONPATH=/Users/sam/Documents/GitHub/ai-quality-kit .venv/bin/python scripts/mcp_go_no_go.py --verbose
	@echo "📊 Results and artifacts saved to artifacts/ and docs/"
	@echo "✅ MCP Go/No-Go validation completed"
