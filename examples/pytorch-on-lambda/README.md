# PyTorch with Lambda SnapStart

This project demonstrates how to use PyTorch 2.6 CPU version in AWS Lambda with Lambda SnapStart to reduce cold start times. Since Lambda SnapStart doesn't support EFS and 10GB /tmp directory, we package PyTorch libraries and upload them to S3, then download and load them into memory during function initialization, and finally use SnapStart to save the state to avoid cold starts.

## Architecture

The solution works as follows:

1. Package PyTorch 2.6 CPU version libraries and upload to an S3 bucket
2. Lambda function downloads PyTorch libraries from S3 during initialization
3. Load libraries into memory using lambda-snaploader, not writing to the filesystem
4. Lambda SnapStart creates a snapshot of the function, including PyTorch libraries in memory
5. When the function is restored, PyTorch libraries are already in memory, no need to download and load again

## Prerequisites

- AWS CLI configured
- Python 3.12
- SAM CLI

## Deployment Steps

### Option 1: Full Automated Deployment

Run the deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 2: Step-by-Step Deployment using Make

```bash
# Build and deploy the SAM application
make deploy

# Package and upload PyTorch libraries
make package

# Test the function
make test
```

### Option 3: Manual Deployment

```bash
# Build the SAM application
sam build

# Deploy the SAM application
sam deploy --guided

# Get the S3 bucket name
export BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='PyTorchLibrariesBucketName'].OutputValue" --output text)

# Package and upload PyTorch libraries
python package_pytorch.py --bucket $BUCKET_NAME

# Get the API endpoint
export API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name pytorch-with-lambda-snapshot --query "Stacks[0].Outputs[?OutputKey=='HelloWorldApi'].OutputValue" --output text)

# Test the function
curl -X POST $API_ENDPOINT -d '{"input": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}'
```

## How It Works

1. **Bootstrap Script**:
   - A bootstrap script is included in the Lambda layer
   - The script sets the LD_PRELOAD environment variable before the Python runtime starts
   - This allows the preload library to intercept library loading calls

2. **Lambda Layer Building**:
   - The lambda-snaploader library is pre-built as a wheel file
   - SAM uses the Makefile in the `layer/` directory to install the wheel
   - The layer is included in the Lambda function deployment

3. **Initialization Phase**:
   - Lambda function downloads PyTorch libraries from S3
   - lambda-snaploader loads libraries into memory using memfd_create
   - A simple PyTorch model is created for testing

4. **SnapStart**:
   - Lambda SnapStart creates a snapshot of the function, including PyTorch libraries in memory
   - When the function is restored, PyTorch libraries and model are already in memory

5. **Inference**:
   - Function receives input data
   - Uses the in-memory PyTorch model for inference
   - Returns inference results, including PyTorch version and device information

## Project Structure

- `layer/`: Contains the Makefile and pre-built wheel for the lambda-snaploader layer
- `hello_world/`: Contains the Lambda function code
- `template.yaml`: SAM template defining the AWS resources
- `deploy.sh`: Script for deploying the application
- `package_pytorch.py`: Script for packaging and uploading PyTorch libraries to S3

## Notes

- This approach works for large libraries like PyTorch that exceed Lambda layer's 250MB limit
- In-memory libraries consume Lambda function memory, ensure sufficient memory allocation
- Initialization may take longer, but SnapStart saves the initialized state for faster subsequent invocations
- This project uses PyTorch 2.6 CPU version to reduce library size and improve compatibility
- The bootstrap script sets LD_PRELOAD before the Python runtime starts, which is necessary for the preload library to work correctly

## Cleanup

```bash
sam delete
```