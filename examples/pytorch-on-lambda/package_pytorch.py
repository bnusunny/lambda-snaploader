#!/usr/bin/env python
"""
Package PyTorch libraries and upload to S3
"""

import os
import sys
import subprocess
import shutil
import zipfile
import boto3
import argparse
import logging
import glob
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def install_libraries(build_dir, requirements_file):
    """
    Install libraries from requirements.txt in the build directory
    """
    logger.info(f"Installing libraries in build directory {build_dir}")
    
    # Create build directory if it doesn't exist
    os.makedirs(build_dir, exist_ok=True)
    
    # Install libraries to the build directory
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", requirements_file,
        "-t", build_dir,
        "--index-url", "https://download.pytorch.org/whl/cpu",
        "--no-cache-dir",  # Don't use the pip cache
        "--no-deps"  # Don't install dependencies (we'll install them explicitly)
    ]
    
    logger.info(f"Executing command: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    logger.info("Libraries installation complete")
    

def create_zip_file(source_dir, output_path):
    """
    Create a zip file from a directory, only including essential files
    """
    logger.info(f"Creating zip file: {output_path}")
    
    file_count = 0
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                
                zipf.write(file_path, arcname)
                file_count += 1
                
                # Log progress every 1000 files
                if file_count % 1000 == 0:
                    logger.info(f"Added {file_count} files to zip...")
    
    logger.info(f"Zip file created with {file_count} files, size: {os.path.getsize(output_path) / (1024 * 1024):.2f} MB")

def upload_to_s3(file_path, bucket_name, key):
    """
    Upload a file to S3
    """
    logger.info(f"Uploading file to S3: s3://{bucket_name}/{key}")
    
    s3_client = boto3.client('s3')
    
    try:
        s3_client.upload_file(file_path, bucket_name, key)
        logger.info("Upload complete")
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise e

def main():
    parser = argparse.ArgumentParser(description='Package PyTorch libraries and upload to S3')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--key', default='pytorch_libs.zip', help='S3 object key')
    parser.add_argument('--output', default='pytorch_libs.zip', help='Local output file path')
    
    args = parser.parse_args()
    
    # Get the directory of the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not script_dir:
        script_dir = '.'
    
    # Path to requirements.txt in the same directory as the script
    requirements_file = os.path.join(script_dir, 'requirements.txt')
    
    # Check if requirements file exists
    if not os.path.exists(requirements_file):
        logger.error(f"Requirements file not found: {requirements_file}")
        sys.exit(1)
    
    # Build directory path
    build_dir = os.path.join(script_dir, 'build')
    
    # Clean up build directory if it exists
    if os.path.exists(build_dir):
        logger.info(f"Cleaning up existing build directory: {build_dir}")
        shutil.rmtree(build_dir)
    
    try:
        # Install libraries
        install_libraries(build_dir, requirements_file)
        
        # Create zip file
        create_zip_file(build_dir, args.output)
        
        # Upload to S3
        upload_to_s3(args.output, args.bucket, args.key)
        
        logger.info("Processing complete")
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up build directory
        if os.path.exists(build_dir):
            logger.info(f"Cleaning up build directory: {build_dir}")
            shutil.rmtree(build_dir)

if __name__ == "__main__":
    main()
