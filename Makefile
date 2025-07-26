.PHONY: minimal
minimal: venv

venv: requirements.txt setup.py tox.ini
	python3 -m tox -e venv

.PHONY: test
test:
	python3 -m tox -e tests

.PHONY: pre-commit
pre-commit:
	python3 -m tox -e pre-commit

.PHONY: clean
clean:
	find -name '*.pyc' -delete
	find -name '__pycache__' -delete
	rm -rf .tox
	rm -rf venv

.PHONY: install-hooks
install-hooks:
	python3 -m tox -e install-hooks
