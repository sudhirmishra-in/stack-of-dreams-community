# SAM "makefile" build, driven by scripts/sam_build.sh (which exports NAVIGATOR_ROOT).
# Installs Linux/arm64 wheels without Docker, then copies the shared package and fixtures.
build-ApiFunction build-IngestFunction:
	uv pip install --quiet --target "$(ARTIFACTS_DIR)" \
	  --python-platform aarch64-manylinux2014 --python-version 3.12 --only-binary :all: \
	  -r "$(NAVIGATOR_ROOT)/requirements-lambda.txt"
	cp -r "$(NAVIGATOR_ROOT)/src/navigator" "$(ARTIFACTS_DIR)/navigator"
	cp -r "$(NAVIGATOR_ROOT)/fixtures" "$(ARTIFACTS_DIR)/fixtures"
	find "$(ARTIFACTS_DIR)" -name '__pycache__' -type d -prune -exec rm -rf {} +
