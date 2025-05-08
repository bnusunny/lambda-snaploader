"""
lambda-snaploader: A tool for loading large libraries in AWS Lambda with SnapStart integration
"""

from .loader import setup_preload, create_memory_file, create_symlinks, get_file_descriptors, set_base_path
from .s3_utils import download_and_extract_from_s3, stream_libraries_from_s3
from .snapstart import register_snapstart_hook

__version__ = "0.1.0"

def load_libraries_from_s3(
    bucket, 
    key, 
    base_path='/var/task',
    target_dir='/tmp/lib_so', 
    file_filter=None
):
    """
    One-step setup for loading libraries from S3 with SnapStart integration
    
    Args:
        bucket: The S3 bucket name
        key: The S3 object key
        base_path: The base path for original files (e.g., '/var/task', '/opt/ml/model')
        target_dir: The target directory for symbolic links
        file_filter: Optional file filter function, defaults to loading .so, .so.*, and .gguf files
    
    Returns:
        bool: Whether the setup was successful
    """
    # Default filter: load .so, .so.*, and .gguf files into memory files
    if file_filter is None:
        file_filter = lambda name: (
            name.endswith('.so') or 
            '.so.' in name or 
            name.endswith('.gguf')
        )
    # Set the base path for original files
    set_base_path(base_path)
    
    # Set up the preload library
    if not setup_preload():
        return False
    
    try:
        # Download and load library files from S3
        stream_libraries_from_s3(
            bucket=bucket,
            key=key,
            file_filter=file_filter,
            base_path=base_path,
            target_dir=target_dir
        )
        
        # Register the SnapStart restore hook
        register_snapstart_hook(target_dir=target_dir)
        
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to set up library from S3: {e}")
        import traceback
        logging.getLogger(__name__).error(traceback.format_exc())
        return False

__all__ = [
    "setup_preload", 
    "create_memory_file", 
    "create_symlinks", 
    "get_file_descriptors",
    "download_and_extract_from_s3",
    "stream_libraries_from_s3",
    "register_snapstart_hook",
    "load_libraries_from_s3",
    "set_base_path"
]