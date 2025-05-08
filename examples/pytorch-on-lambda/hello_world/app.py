import json
import os
import sys
import time
import logging
import boto3
from typing import Dict, Any
from lambda_snaploader import load_libraries_from_s3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variables
pytorch_module = None
model = None

# Log initialization information
logger.info(f"Python version: {sys.version}")
logger.info(f"System paths: {sys.path}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Environment variables: LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH', 'Not set')}")
logger.info(f"Environment variables: LD_PRELOAD={os.environ.get('LD_PRELOAD', 'Not set')}")

def load_pytorch():
    """
    Load PyTorch library from S3 using lambda-snaploader
    """
    global pytorch_module, model
    
    # If PyTorch is already loaded, return immediately
    if pytorch_module is not None:
        logger.info("PyTorch is already loaded, skipping initialization")
        return True
    
    start_time = time.time()
    logger.info("Starting PyTorch library initialization")
    
    # Get environment variables
    bucket_name = os.environ.get('PYTORCH_BUCKET')
    key = os.environ.get('PYTORCH_KEY')
    
    if not bucket_name or not key:
        logger.error(f"Environment variables not set: PYTORCH_BUCKET={bucket_name}, PYTORCH_KEY={key}")
        raise ValueError("Required environment variables not set: PYTORCH_BUCKET or PYTORCH_KEY")
    
    logger.info(f"Loading from S3: s3://{bucket_name}/{key}")
    
    try:
        # Setup library from S3 using lambda-snaploader
        target_dir = '/tmp/libs_so'
        setup_result = load_libraries_from_s3(
            bucket=bucket_name,
            key=key,
            target_dir=target_dir
        )
        
        if not setup_result:
            logger.error("Failed to setup PyTorch library from S3")
            return False
        
        logger.info("Library setup complete, importing PyTorch")
        
        # Import PyTorch
        import_start = time.time()
        import torch
        pytorch_module = torch
        import_time = time.time() - import_start
        logger.info(f"PyTorch import complete, took {import_time:.2f} seconds")
        
        # Create a simple model for testing
        model_start = time.time()
        model = torch.nn.Sequential(
            torch.nn.Linear(10, 5),
            torch.nn.ReLU(),
            torch.nn.Linear(5, 1)
        )
        model_time = time.time() - model_start
        logger.info(f"Model creation complete, took {model_time:.2f} seconds")
        
        logger.info(f"PyTorch library loaded successfully, version: {torch.__version__}")
        logger.info(f"Total initialization time: {time.time() - start_time:.2f} seconds")
        
        return True
    except Exception as e:
        logger.error(f"Failed to load PyTorch library: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_inference(input_data):
    """
    Run inference using PyTorch model
    """
    global pytorch_module, model
    
    logger.info(f"Running inference, input data: {input_data[:5]}...")
    
    if pytorch_module is None or model is None:
        logger.warning("PyTorch or model not loaded, attempting to reload")
        if not load_pytorch():
            return {"error": "Failed to load PyTorch"}
    
    try:
        # Convert input data to tensor
        input_tensor = pytorch_module.tensor(input_data, dtype=pytorch_module.float32)
        logger.debug(f"Created input tensor: {input_tensor.shape}, {input_tensor.dtype}")
        
        # Run inference
        with pytorch_module.no_grad():
            output = model(input_tensor)
        logger.debug(f"Inference result: {output}")
        
        # Add PyTorch version information
        result = {
            "result": output.tolist(),
            "pytorch_version": pytorch_module.__version__,
            "device": str(pytorch_module.device("cpu"))
        }
        logger.info(f"Inference complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": f"Inference failed: {str(e)}"}

# Initialize PyTorch during module initialization
try:
    logger.info("Starting PyTorch initialization")
    load_pytorch()
    logger.info("PyTorch initialization complete")
except Exception as e:
    logger.error(f"Failed to load PyTorch during initialization: {str(e)}")
    # Don't raise exception, let the function continue initializing

def lambda_handler(event, context):
    """
    Lambda function handler
    """
    logger.info(f"Processing request: {event}")
    
    # Get input data from request, use default if not provided
    try:
        body = json.loads(event.get('body', '{}'))
        input_data = body.get('input', [0.1] * 10)
        logger.info(f"Parsed input data: {input_data[:5]}...")
    except Exception as e:
        logger.error(f"Failed to parse input data: {e}")
        input_data = [0.1] * 10
        logger.info(f"Using default input data: {input_data}")
    
    # Run inference
    result = run_inference(input_data)
    
    # Return result
    response = {
        "statusCode": 200,
        "body": json.dumps({
            "message": "PyTorch inference complete",
            "pytorch_loaded": pytorch_module is not None,
            "result": result
        })
    }
    logger.info(f"Returning response: {response}")
    return response