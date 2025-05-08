"""
Provides functionality for downloading and loading libraries from S3
"""

import os
import io
import sys
import zipfile
import logging
import boto3
from typing import List, Dict, Optional, Union, Callable

from .loader import create_memory_file, create_symlinks, register_memory_importer

logger = logging.getLogger(__name__)

def download_and_extract_from_s3(
    bucket: str, 
    key: str
) -> Dict[str, bytes]:
    """
    Downloads a ZIP file from S3 and extracts it to memory
    
    Args:
        bucket: The S3 bucket name
        key: The S3 object key
    
    Returns:
        Dict[str, bytes]: A mapping of file names to file contents
    """
    logger.info(f"Downloading from S3: s3://{bucket}/{key}")
    
    # Create S3 client
    s3_client = boto3.client('s3')
    
    try:
        # Download file
        response = s3_client.get_object(Bucket=bucket, Key=key)
        zip_content = response['Body'].read()
        
        logger.info(f"Download complete, size: {len(zip_content) / (1024 * 1024):.2f} MB")
        
        # Extract to memory
        memory_fs = {}
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
            for file_name in zip_ref.namelist():
                content = zip_ref.read(file_name)
                memory_fs[file_name] = content
        
        logger.info(f"Extraction complete, file count: {len(memory_fs)}")
        return memory_fs
    except Exception as e:
        logger.error(f"Download or extraction failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def stream_libraries_from_s3(
    bucket: str, 
    key: str, 
    file_filter: Callable[[str], bool],
    base_path: str = '/var/task',
    target_dir: str = '/tmp/lib_so'
) -> str:
    """
    Downloads library files from S3, loads them into memory, and creates symbolic links
    
    Args:
        bucket: The S3 bucket name
        key: The S3 object key
        file_filter: Required file filter function to determine which files to load into memory
        base_path: Base path for original files
        target_dir: The target directory for symbolic links
    
    Returns:
        str: The symbolic link directory path
    """
    # file_filter must be provided by the caller
    if file_filter is None:
        raise ValueError("file_filter must be provided")
    
    # Download and extract all files
    memory_fs = download_and_extract_from_s3(bucket, key)
    
    # Load .so files into memory files
    loaded_count = 0
    for file_name, content in memory_fs.items():
        if file_filter(file_name):
            create_memory_file(file_name, content)
            loaded_count += 1
    
    logger.info(f"Loaded {loaded_count} shared library files into memory files")
    
    # Create symbolic links for .so files
    symlink_dir = create_symlinks(target_dir)
    
    # Register the memory importer for .py files
    register_memory_importer(memory_fs, base_path, target_dir)
    
    return symlink_dir