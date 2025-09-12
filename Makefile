.PHONY: test test-ci clean quickcheck quickcheck.running requirements requirements-clean validate-templates

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
