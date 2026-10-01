.PHONY: install run test compile check

install:
	python3 -m pip install -e .

run:
	python3 -m app.main

test:
	pytest -q

compile:
	python3 -m compileall -q app tests

check: compile test