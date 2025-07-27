.PHONY: minimal
minimal: venv

venv: requirements.txt requirements-dev.txt setup.py
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	./venv/bin/pip install -r requirements-dev.txt
	./venv/bin/pip install -e .

.PHONY: test
test: venv
	./venv/bin/python -m pytest tests/ -v --tb=short

.PHONY: test-coverage
test-coverage: venv
	./venv/bin/python -m pytest --cov=api --cov=main --cov=core --cov=schemas tests/ --cov-report=term-missing --cov-report=html -v

.PHONY: test-full
test-full: venv
	./venv/bin/python -m pytest --cov=api --cov=main --cov=core --cov=schemas tests/ --cov-report=term-missing --cov-report=html --cov-report=xml -v --tb=long
	@echo ""
	@echo "📊 Coverage reports generated:"
	@echo "  - Terminal: Displayed above"
	@echo "  - HTML: htmlcov/index.html"
	@echo "  - XML: coverage.xml"

.PHONY: pre-commit
pre-commit: venv
	./venv/bin/pre-commit run --all-files

.PHONY: clean
clean:
	find -name '*.pyc' -delete
	find -name '__pycache__' -delete
	rm -rf .tox
	rm -rf venv
	rm -rf *.egg-info

.PHONY: install-hooks
install-hooks: venv
	./venv/bin/pre-commit install -f --install-hooks
