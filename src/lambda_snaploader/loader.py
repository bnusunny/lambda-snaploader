"""
Provides functionality for loading large shared libraries in AWS Lambda
"""

import os
import sys
import ctypes
import logging
import importlib.util
import importlib.abc
import importlib.machinery
from importlib.util import spec_from_file_location

logger = logging.getLogger(__name__)

# Global variables
_memfd_create = None
_MFD_CLOEXEC = 1
_so_file_fds = {}  # Stores file descriptors for .so files
_base_path = "/var/task"  # Default base path for original files
_memory_fs = {}  # Stores file contents in memory
_module_cache = {}  # Caches module specs
_memory_importer = None  # The memory importer instance

class MemoryImporter(importlib.abc.MetaPathFinder):
    """
    Custom importer that loads Python modules directly from memory
    """
    def __init__(self, memory_fs, base_path='/var/task', target_dir='/tmp/lib_so'):
        self.memory_fs = memory_fs
        self.base_path = base_path
        self.target_dir = target_dir
        # Keep track of which modules we've seen to handle circular imports
        self.seen_modules = set()
        
    def _get_extension_suffix(self):
        """
        Get the extension suffix for C extension modules based on the current Python version and platform
        """
        # Try to get it from importlib.machinery
        try:
            return importlib.machinery.EXTENSION_SUFFIXES[0]
        except (AttributeError, IndexError):
            pass
        
        # Fallback: construct it manually
        import sysconfig
        py_version = sysconfig.get_config_var('SOABI') or f'cpython-{sys.version_info.major}{sys.version_info.minor}'
        platform_suffix = sysconfig.get_config_var('MULTIARCH') or f'{sys.platform}'
        
        # Standard format for Linux
        return f'.{py_version}-{platform_suffix}.so'
        
    def _get_potential_paths(self, fullname, path=None):
        """
        Get potential file paths for a module name, considering parent packages
        """
        module_path = fullname.replace('.', '/')

        # Get the extension suffix for C extension modules
        extension_suffix = self._get_extension_suffix()
            
        # Direct module paths
        paths = [
            f"{module_path}{extension_suffix}",  # C extension with specific suffix
            f"{module_path}.so",  # Generic C extension
            f"{module_path}.py",  # Regular module
            f"{module_path}/__init__.py",  # Package
            f"{module_path}.pyi",  # Type hint file
            f"{module_path}/__init__.pyi",  # Package type hint file
        ]
        
        # If path is provided (for submodules), check relative to those paths
        if path:
            for base in path:
                module_name = module_path.split('/')[-1]
                # Handle both package-relative and absolute paths
                if base.startswith(self.base_path):
                    # Convert absolute path to relative path within our memory filesystem
                    rel_base = base[len(self.base_path):].lstrip('/')
                    paths.extend([
                        f"{rel_base}/{module_name}{extension_suffix}",                        
                        f"{rel_base}/{module_name}.so"       
                        f"{rel_base}/{module_name}.py",
                        f"{rel_base}/{module_name}/__init__.py",
                        f"{rel_base}/{module_name}.pyi",
                        f"{rel_base}/{module_name}/__init__.pyi",                                         
                    ])
                else:
                    paths.extend([
                        f"{base}/{module_name}{extension_suffix}",
                        f"{base}/{module_name}.so",                        
                        f"{base}/{module_name}.py",
                        f"{base}/{module_name}/__init__.py",
                        f"{base}/{module_name}.pyi",
                        f"{base}/{module_name}/__init__.pyi",
                    ])
        
        return paths
    
    def find_spec(self, fullname, path, target=None):
        global _module_cache
        
        # Trace all import attempts
        logger.debug(f"Finding spec for module: {fullname}, path: {path}, target={target}")
        
        # Check if the module is already in sys.modules (Python's module cache)
        if fullname in sys.modules:
            return None
            
        # Check our own module cache
        if fullname in _module_cache:
            return _module_cache[fullname]
            
        # Skip if we've already seen this module (prevents infinite recursion)
        if fullname in self.seen_modules:
            return None
        
        self.seen_modules.add(fullname)
        
        # Get all potential file paths for this module
        potential_paths = self._get_potential_paths(fullname, path)
        
        # Check each potential path
        for module_path in potential_paths:
            if module_path in self.memory_fs:
                logger.debug(f"Found module in memory: {module_path}")
                is_package = module_path.endswith('/__init__.py')
                
                # For binary files, use ExtensionFileLoader directly
                if module_path.endswith('.so') or '.so.' in module_path:
                    # Get the path to the symbolic link
                    target_path = f"{self.target_dir}/{module_path}"
                    if os.path.exists(target_path):
                        logger.debug(f"Using symbolic link at {target_path}")
                        spec = spec_from_file_location(fullname, target_path)
                        if spec:
                            _module_cache[fullname] = spec
                            self.seen_modules.remove(fullname)
                            return spec
                
                # Create the spec with appropriate attributes for Python modules
                spec = importlib.machinery.ModuleSpec(
                    name=fullname,
                    loader=MemoryLoader(self.memory_fs, module_path, is_package=is_package, target_dir=self.target_dir),
                    origin=f"{self.base_path}/{module_path}",
                    is_package=is_package
                )
                
                # Set submodule_search_locations for packages
                if is_package:
                    package_dir = os.path.dirname(module_path)
                    spec.submodule_search_locations = [package_dir]
                
                # Cache the spec
                _module_cache[fullname] = spec
                
                self.seen_modules.remove(fullname)  # Allow future imports of this module
                return spec
        
        self.seen_modules.remove(fullname)  # Allow future imports of this module
        return None  # Module not found in our memory filesystem

class MemoryLoader(importlib.abc.Loader):
    """
    Custom loader that loads Python modules directly from memory
    """
    def __init__(self, memory_fs, module_path, is_package=False, target_dir='/tmp/lib_so'):
        self.memory_fs = memory_fs
        self.module_path = module_path
        self.is_package = is_package
        self.target_dir = target_dir

        # Check if this is a binary file (like .so)
        self.is_binary = module_path.endswith('.so') or '.so.' in module_path
        
        # Only decode text files
        if not self.is_binary:
            self.source_code = memory_fs[module_path].decode('utf-8')
        else:
            self.source_code = None
    
    def create_module(self, spec):
        return None  # Use default module creation
    
    def get_source(self, fullname):
        """
        Return the source code for the module
        This helps with introspection and debugging tools
        """
        if self.is_binary:
            return None
        return self.source_code
    
    def get_code(self, fullname):
        """
        Return the compiled code object for the module
        This helps with proper line number reporting in tracebacks
        """
        if self.is_binary:
            return None
        return compile(self.source_code, self.module_path, 'exec')
    
    def is_package(self, fullname):
        """
        Return whether the module is a package
        """
        return self.is_package
    
    def exec_module(self, module):
        # Binary files should not be handled by this loader
        if self.is_binary:
            logger.error(f"Binary file {self.module_path} should not be handled by MemoryLoader")
            return
                    
        # Set __file__ attribute to a path that looks like a real file path
        module.__file__ = f"/var/task/{self.module_path}"
        
        # Set __cached__ attribute to prevent recompilation attempts
        module.__cached__ = None
        
        # Set __package__ attribute
        if self.is_package:
            module.__package__ = module.__name__
        else:
            module.__package__ = module.__name__.rpartition('.')[0]
        
        # Set __path__ for packages to enable submodule imports
        if self.is_package:
            package_dir = os.path.dirname(self.module_path)
            module.__path__ = [package_dir]
            
        # Set up __spec__ attribute for proper relative imports
        module.__spec__.origin = module.__file__
        if self.is_package:
            module.__spec__.submodule_search_locations = module.__path__
        
        # Set up proper __loader__ attribute
        module.__loader__ = self
        
        # Execute the module code
        try:
            code = self.get_code(module.__name__)
            exec(code, module.__dict__)
        except Exception as e:
            # Log the error but don't raise it to prevent breaking the import system
            logger.error(f"Error executing module {module.__name__}: {e}")
            # Add error information to the module
            module.__snaploader_error__ = str(e)
            import traceback
            module.__snaploader_traceback__ = traceback.format_exc()

def register_memory_importer(memory_fs, base_path='/var/task', target_dir='/tmp/lib_so'):
    """
    Registers a memory importer for Python modules
    
    Args:
        memory_fs: Dictionary mapping file names to file contents
        base_path: Base path for original files
        target_dir: Target directory for symbolic links
    
    Returns:
        MemoryImporter: The registered memory importer
    """
    global _memory_importer, _memory_fs
    
    # Update the memory filesystem
    _memory_fs.update(memory_fs)
    
    # Register the memory importer (only once)
    if _memory_importer is None:
        _memory_importer = MemoryImporter(_memory_fs, base_path, target_dir)
        sys.meta_path.insert(0, _memory_importer)
        logger.info("Registered memory importer for Python modules")
    else:
        # Update the existing importer with new files
        _memory_importer.memory_fs.update(memory_fs)
        logger.info("Updated existing memory importer with new modules")
    
    return _memory_importer

def set_base_path(path):
    """
    Sets the base path for original files
    
    Args:
        path: The base path (e.g., '/var/task', '/opt/ml/model')
    
    Returns:
        str: The new base path
    """
    global _base_path
    _base_path = path
    logger.info(f"Set base path to: {_base_path}")
    return _base_path

def create_path_mapping_file(so_file_fds, target_dir):
    """
    Creates a mapping file that maps original paths to memory file paths
    
    Args:
        so_file_fds: Dictionary mapping file names to file descriptors
        target_dir: Target directory for symbolic links
    
    Returns:
        str: Path to the mapping file
    """
    global _base_path
    mapping_file = '/tmp/snaploader_path_mapping.txt'
    
    try:
        with open(mapping_file, 'w') as f:
            for file_name, fd in so_file_fds.items():
                # Get the original path using the configured base path
                original_path = f"{_base_path}/{file_name}"
                
                # Get the target path - preserve directory structure
                target_path = f"{target_dir}/{file_name}"
                
                # Write the mapping
                f.write(f"{original_path}:{target_path}\n")
        
        logger.debug(f"Created path mapping file: {mapping_file}")
        return mapping_file
    except Exception as e:
        logger.error(f"Failed to create path mapping file: {e}")
        return None

def setup_preload():
    """
    Sets up the preload library
    
    Returns:
        bool: Whether the setup was successful
    """
    try:
        # Get the module path
        module_path = importlib.util.find_spec("lambda_snaploader.libpreload").origin
        
        # Set the LD_PRELOAD environment variable
        os.environ['LD_PRELOAD'] = module_path
        
        # Load the preload library
        preload_lib = ctypes.CDLL(module_path)
        
        logger.debug(f"Successfully set up preload library: {module_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to set up preload library: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def _init_memfd_create():
    """
    Initializes the memfd_create function
    """
    global _memfd_create
    
    if _memfd_create is not None:
        return True
    
    try:
        libc = ctypes.CDLL('libc.so.6')
        _memfd_create = libc.memfd_create
        _memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        _memfd_create.restype = ctypes.c_int
        return True
    except Exception as e:
        logger.error(f"Failed to initialize memfd_create: {e}")
        return False

def create_memory_file(name, content):
    """
    Creates a file in memory and returns its file descriptor
    
    Args:
        name: The file name
        content: The file content (bytes)
    
    Returns:
        int: The file descriptor
    """
    global _so_file_fds
    
    if not _init_memfd_create():
        raise RuntimeError("memfd_create is not available")
    
    logger.debug(f"Creating memory file: {name}, size: {len(content) / 1024:.2f} KB")
    
    # Create memory file
    fd = _memfd_create(name.encode(), _MFD_CLOEXEC)
    if fd < 0:
        errno = ctypes.get_errno()
        error_msg = os.strerror(errno)
        logger.error(f"memfd_create failed: {error_msg} (errno={errno})")
        raise OSError(f"memfd_create failed: {error_msg}")
    
    # Write content
    try:
        bytes_written = os.write(fd, content)
        
        # Reset file pointer to the beginning
        os.lseek(fd, 0, os.SEEK_SET)
        
        # Store file descriptor
        _so_file_fds[name] = fd
        
        return fd
    except Exception as e:
        logger.error(f"Failed to write content to fd={fd}: {e}")
        os.close(fd)  # Close file descriptor to avoid leaks
        raise

def create_symlinks(target_dir='/tmp/lib_so'):
    """
    Creates symbolic links for files in memory
    
    Args:
        target_dir: The target directory for symbolic links
    
    Returns:
        str: The symbolic link directory path
    """
    global _so_file_fds
    
    logger.debug(f"Creating symbolic links, {len(_so_file_fds)} files total")
    
    # Create target directory
    if os.path.exists(target_dir):
        import shutil
        shutil.rmtree(target_dir)
    
    os.makedirs(target_dir)
    
    # Create symbolic links for each .so file
    for file_name, fd in _so_file_fds.items():
        try:
            # Check if file descriptor is valid
            try:
                os.fstat(fd)
            except OSError:
                logger.error(f"File descriptor {fd} is invalid")
                continue
            
            # Create symbolic link with directory structure
            dirname = os.path.dirname(file_name)
            if dirname:
                # Create directory if it doesn't exist
                target_subdir = os.path.join(target_dir, dirname)
                os.makedirs(target_subdir, exist_ok=True)
                link_path = os.path.join(target_dir, file_name)
            else:
                link_path = os.path.join(target_dir, os.path.basename(file_name))
            
            proc_path = f"/proc/self/fd/{fd}"
            
            # Remove symbolic link if it already exists
            if os.path.exists(link_path):
                os.remove(link_path)
            
            os.symlink(proc_path, link_path)
            logger.debug(f"Successfully created symbolic link: {link_path}")
        except Exception as e:
            logger.error(f"Failed to create symbolic link for {file_name}: {e}")
    
    # Create path mapping file
    create_path_mapping_file(_so_file_fds, target_dir)
    
    # Set LD_LIBRARY_PATH environment variable
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    new_ld_library_path = f"{target_dir}:{ld_library_path}" if ld_library_path else target_dir
    os.environ['LD_LIBRARY_PATH'] = new_ld_library_path
    
    return target_dir

def get_file_descriptors():
    """
    Gets a mapping of all file descriptors
    
    Returns:
        dict: A mapping of file names to file descriptors
    """
    return _so_file_fds.copy()

def get_memory_filesystem():
    """
    Gets a copy of the memory filesystem
    
    Returns:
        dict: A mapping of file names to file contents
    """
    return _memory_fs.copy()
