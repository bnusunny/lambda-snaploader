#!/bin/bash
set -e

echo "Building and deploying SAM application..."
sam build
sam deploy --guided

echo "Getting S3 bucket name..."
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='PyTorchLibrariesBucketName'].OutputValue" --output text)
echo "S3 bucket name: $BUCKET_NAME"

echo "Packaging and uploading PyTorch libraries..."
python package_pytorch.py --bucket $BUCKET_NAME

echo "Getting API endpoint..."
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='HelloWorldApi'].OutputValue" --output text)
echo "API endpoint: $API_ENDPOINT"

echo "Deployment complete!"
echo "To test the function, run:"
echo "curl -X POST $API_ENDPOINT -d '{\"input\": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}'"