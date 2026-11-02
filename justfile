# Phase 1 Maritime Tail Risk Engine Task Runner

default:
    @just --list

setup:
    python -m pip install -r requirements.txt

test:
    python -m pytest tests -v

verify:
    python verify_repo.py --target .

audit:
    python generate_tear_sheet.py
