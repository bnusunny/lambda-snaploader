.PHONY: all clean deploy package test

# Default target
all: deploy

# Clean up build artifacts
clean:
	@echo "Cleaning up..."
	@rm -rf .aws-sam
	@echo "Clean complete"

# Build and deploy the SAM application
deploy:
	@echo "Building and deploying SAM application..."
	sam build
	sam deploy --guided

# Package and upload PyTorch libraries
package:
	@echo "Getting S3 bucket name..."
	$(eval BUCKET_NAME := $(shell aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='PyTorchLibrariesBucketName'].OutputValue" --output text))
	@echo "S3 bucket name: $(BUCKET_NAME)"
	@echo "Packaging and uploading PyTorch libraries..."
	python package_pytorch.py --bucket $(BUCKET_NAME)

# Test the deployed function
test:
	@echo "Getting API endpoint..."
	$(eval API_ENDPOINT := $(shell aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='HelloWorldApi'].OutputValue" --output text))
	@echo "API endpoint: $(API_ENDPOINT)"
	@echo "Testing the function..."
	curl -X POST $(API_ENDPOINT) -d '{"input": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}'

# Full deployment process
full-deploy: deploy package test