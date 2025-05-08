.PHONY: build-LambdaSnaploaderLayer

# Get the directory where the Makefile is located
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

build-LambdaSnaploaderLayer:
	@echo "Building lambda-snaploader layer..."
	@echo "Makefile directory: $(MAKEFILE_DIR)"
	@echo "Artifacts directory: $(ARTIFACTS_DIR)"
	@mkdir -p "$(ARTIFACTS_DIR)/python"
	
	# Install the lambda-snaploader wheel
	@pip install wheels/lambda_snaploader-*.whl -t "$(ARTIFACTS_DIR)/python/"
	
	# Copy the bootstrap script
	@mkdir -p "$(ARTIFACTS_DIR)/bin"
	@cp -f "$(MAKEFILE_DIR)/bootstrap" "$(ARTIFACTS_DIR)/bin/"
	@chmod +x "$(ARTIFACTS_DIR)/bin/bootstrap"
	
	@echo "Lambda layer build complete"