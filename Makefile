.PHONY: test test-ci clean

test:
	pytest -q --cov=apps --cov=llm --cov-report=term-missing --cov-report=html --ignore=evals --ignore=guardrails --ignore=safety

test-ci:
	pytest -q --cov=apps --cov=llm --cov-report=term-missing --cov-report=html --cov-fail-under=80 --ignore=evals --ignore=guardrails --ignore=safety

clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
