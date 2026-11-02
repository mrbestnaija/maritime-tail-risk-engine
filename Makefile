.PHONY: setup test verify audit

setup:
	python -m pip install -r requirements.txt

test:
	python -m pytest tests -v

verify:
	python verify_repo.py --target .

audit:
	python generate_tear_sheet.py
