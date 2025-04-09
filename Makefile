PYTHON_VERSION = 3.12.7
PYTHON_RELEASE = 20241002

# Helper variables
venv ?= $(TMP_DIR)/venv-$(PYTHON_ID)
py = $(venv)/bin/python3

include Makefile.sidekick

# Virtual env setup
$(venv)/.created: | .d.python
	$(PYTHON) -m venv $(venv)
	$(py) -m pip install -U uv
	touch $@

$(py): $(venv)/.created
	touch $@

$(venv)/.deps: requirements.txt | $(py)
	$(py) -m pip install -r $<
	touch $@


deps: $(venv)/.deps
	echo "deps"
.PHONY: deps	

test: $(venv)/.deps
	$(py) -m unittest