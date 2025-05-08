"""
Provides functionality for integrating with Lambda SnapStart
"""

import os
import logging
from typing import Optional, Callable, Any

from .loader import create_symlinks, set_base_path

logger = logging.getLogger(__name__)

def register_snapstart_hook(
    target_dir: str = '/tmp/libs_so',
    hook_module: str = 'snapshot_restore_py',
    hook_function: str = 'register_after_restore',
    base_path: str = None
):
    """
    Registers a SnapStart restore hook
    
    Args:
        target_dir: The target directory for symbolic links
        hook_module: The SnapStart hook module name
        hook_function: The function name for registering hooks
        base_path: Optional base path to set during restore
    
    Returns:
        bool: Whether the hook was successfully registered
    """
    try:
        # Dynamically import the SnapStart hook module
        import importlib
        module = importlib.import_module(hook_module)
        register_func = getattr(module, hook_function)
        
        # Define the restore hook
        def snapstart_restore_hook():
            logger.info("SnapStart restore hook called")
            try:
                # Reset base path if provided
                if base_path:
                    set_base_path(base_path)
                
                # Recreate symbolic links
                create_symlinks(target_dir)
                logger.info("SnapStart restore completed")
            except Exception as e:
                logger.error(f"SnapStart restore hook failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Register the hook
        register_func(snapstart_restore_hook)
        logger.info("Successfully registered SnapStart restore hook")
        return True
    except Exception as e:
        logger.error(f"Failed to register SnapStart restore hook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False