# lambda-snaploader Design Document

This document outlines the design principles, architecture, and implementation details of the lambda-snaploader tool.

## Problem Statement

AWS Lambda has several limitations when working with large libraries:

1. **Size Limitations**: Lambda layers are limited to 250MB, and the total deployment package size is limited to 50MB (zipped) or 250MB (unzipped).
2. **Temporary Storage**: The `/tmp` directory is limited to 512MB (or 10GB with ephemeral storage), but Lambda SnapStart doesn't support ephemeral storage.
3. **Cold Start**: Large libraries like PyTorch can cause significant cold start delays.
4. **SnapStart Compatibility**: Lambda SnapStart can reduce cold starts but has limitations with EFS and large `/tmp` usage.

## Solution Overview

lambda-snaploader addresses these challenges by:

1. Using memory-based file storage via `memfd_create` to bypass `/tmp` size limitations
2. Intercepting system calls to redirect file access from original paths to memory-based files
3. Automatically discovering and mapping shared libraries
4. Integrating with Lambda SnapStart to maintain performance across function invocations

## Architecture

The tool consists of several key components:

### 1. Memory File System

- Uses Linux's `memfd_create` system call to create files in memory
- Stores file descriptors in a global dictionary for reference
- Creates symbolic links in `/tmp` that point to memory-based files

### 2. System Call Interception

- Uses `LD_PRELOAD` to inject a custom shared library
- Intercepts `dlopen`, `open`, and `fopen` system calls
- Redirects file access from original paths to memory-based files

### 3. Path Mapping

- Creates a mapping file in `/tmp` that maps original paths to memory-based files
- Supports both exact path matches and basename matches
- Configurable base path for original files

### 4. S3 Integration

- Downloads library files from S3
- Extracts and loads files into memory
- Supports custom file filtering

### 5. SnapStart Integration

- Registers a restore hook with Lambda SnapStart
- Recreates symbolic links when the function is restored
- Maintains the memory-based file system across function invocations

## Component Details

### Memory File System (`loader.py`)

The memory file system is implemented in `loader.py` and provides functions for:

- Creating memory-based files using `memfd_create`
- Managing file descriptors
- Creating symbolic links to memory-based files
- Setting the base path for original files
- Storing file contents in memory for Python modules
- Custom import hooks for loading Python modules from memory

Key functions:
- `create_memory_file`: Creates a file in memory and returns its file descriptor
- `create_symlinks`: Creates symbolic links for files in memory
- `set_base_path`: Sets the base path for original files
- `register_memory_importer`: Registers a custom importer for Python modules

### System Call Interception (`libpreload.c`)

The system call interception is implemented in `libpreload.c` and provides:

- Function hooks for `dlopen`, `open`, and `fopen`
- Path redirection based on a mapping file
- Support for both exact and basename matches

Key components:
- `redirect_path`: Redirects file paths based on the mapping file
- `load_path_mappings`: Loads path mappings from a file
- Intercepted functions: `dlopen`, `open`, `fopen`

### Path Mapping

Path mapping is implemented across both `loader.py` and `libpreload.c`:

- `create_path_mapping_file` in `loader.py` creates the mapping file
- `load_path_mappings` in `libpreload.c` loads the mapping file
- The mapping file format is `original_path:target_path` per line

### S3 Integration (`s3_utils.py`)

S3 integration is implemented in `s3_utils.py` and provides:

- Functions for downloading files from S3
- Functions for extracting and loading files into memory
- Support for custom file filtering

Key functions:
- `download_and_extract_from_s3`: Downloads and extracts files from S3
- `stream_libraries_from_s3`: Downloads, extracts, and loads libraries from S3

### Python Module Loading (`loader.py`)

Python module loading is implemented in `loader.py` and provides:

- Custom import hooks for loading Python modules directly from memory
- Support for packages with __init__.py files
- Support for relative imports within packages
- Module caching to prevent reloading

Key classes and functions:
- `MemoryImporter`: Custom importer that loads Python modules from memory
- `MemoryLoader`: Custom loader that executes Python modules from memory
- `register_memory_importer`: Registers the memory importer in the Python import system

### SnapStart Integration (`snapstart.py`)

SnapStart integration is implemented in `snapstart.py` and provides:

- Functions for registering a restore hook with Lambda SnapStart
- Functions for recreating symbolic links when the function is restored

Key function:
- `register_snapstart_hook`: Registers a SnapStart restore hook

## Design Decisions

### 1. Memory-Based File Storage

**Decision**: Use `memfd_create` instead of `/tmp` for storing large files.

**Rationale**:
- Bypasses the 512MB limit of `/tmp` in Lambda SnapStart
- Files exist only in memory, not on disk
- Provides file descriptors that can be used with symbolic links

**Trade-offs**:
- Increases memory usage
- Requires special handling for file access

### 1a. Hybrid Approach for Python Modules

**Decision**: Use memory files for .so files but load Python modules directly from memory.

**Rationale**:
- Reduces memory overhead by not creating memory files for .py files
- Improves performance by loading Python modules directly from memory
- Maintains compatibility with libraries that use a mix of shared libraries and Python modules

**Trade-offs**:
- Requires custom import hooks
- Adds complexity to the module loading process
- Needs special handling for packages and relative imports

### 2. System Call Interception

**Decision**: Use `LD_PRELOAD` to intercept system calls.

**Rationale**:
- Allows transparent redirection of file access
- No need to modify the original library code
- Works with any library that uses standard file access functions

**Trade-offs**:
- Requires a C extension
- May not work with all libraries
- Adds complexity to the solution

### 3. Automatic Path Discovery

**Decision**: Automatically discover and map shared libraries.

**Rationale**:
- Simplifies usage by not requiring manual path configuration
- Works with any library structure
- Reduces the chance of errors

**Trade-offs**:
- May map unnecessary files
- Requires more memory for storing the mapping

### 4. Configurable Base Path

**Decision**: Allow configuration of the base path for original files.

**Rationale**:
- Supports different deployment scenarios (e.g., container-based Lambda, custom runtimes)
- Provides flexibility for different library locations
- Maintains backward compatibility with default `/var/task`

**Trade-offs**:
- Adds an additional configuration parameter
- Requires careful handling during SnapStart restore

### 5. SnapStart Integration

**Decision**: Integrate with Lambda SnapStart via restore hooks.

**Rationale**:
- Maintains performance across function invocations
- Recreates necessary symbolic links when the function is restored
- Preserves the memory-based file system

**Trade-offs**:
- Requires additional code for handling restore events
- Depends on the SnapStart restore hook mechanism

## Implementation Details

### Memory File Creation

```python
def create_memory_file(name, content):
    fd = _memfd_create(name.encode(), _MFD_CLOEXEC)
    os.write(fd, content)
    os.lseek(fd, 0, os.SEEK_SET)
    _so_file_fds[name] = fd
    return fd
```

### Python Module Loading

```python
class MemoryImporter(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Check module caches to prevent reloading
        if fullname in sys.modules or fullname in _module_cache:
            return None
            
        # Get potential file paths for this module
        potential_paths = self._get_potential_paths(fullname, path)
        
        # Check each potential path
        for module_path in potential_paths:
            if module_path in self.memory_fs:
                # Create and return the module spec
                is_package = module_path.endswith('/__init__.py')
                spec = importlib.machinery.ModuleSpec(
                    name=fullname,
                    loader=MemoryLoader(self.memory_fs, module_path, is_package),
                    origin=f"{self.base_path}/{module_path}",
                    is_package=is_package
                )
                return spec
        return None
```

### System Call Interception

```c
void* dlopen(const char* filename, int flags) {
    init_real_functions();
    const char* new_path = redirect_path(filename);
    void* result = real_dlopen(new_path, flags);
    if (!result && filename != new_path) {
        result = real_dlopen(filename, flags);
    }
    return result;
}
```

### Path Mapping

```python
def create_path_mapping_file(so_file_fds, target_dir):
    with open('/tmp/snaploader_path_mapping.txt', 'w') as f:
        for file_name, fd in so_file_fds.items():
            original_path = f"{_base_path}/{file_name}"
            target_path = f"{target_dir}/{os.path.basename(file_name)}"
            f.write(f"{original_path}:{target_path}\n")
```

### SnapStart Restore Hook

```python
def snapstart_restore_hook(event):
    if base_path:
        set_base_path(base_path)
    module_path = os.environ.get('LD_PRELOAD')
    if module_path and os.path.exists(module_path):
        os.environ['LD_PRELOAD'] = module_path
    create_symlinks(target_dir)
```

## Performance Considerations

1. **Memory Usage**: The tool stores library files in memory, which increases memory usage. Users should allocate sufficient memory to their Lambda functions.

2. **Initialization Time**: The initial download and loading of libraries can take time, but this is mitigated by Lambda SnapStart.

3. **File Size**: Larger files require more memory and take longer to download and load.

4. **Number of Files**: A large number of files can increase the overhead of path mapping and symbolic link creation.

5. **Hybrid Loading**: The hybrid approach (memory files for .so files, direct memory loading for .py files) optimizes memory usage while maintaining compatibility.

## Security Considerations

1. **S3 Access**: The tool requires access to S3, which should be properly secured with IAM policies.

2. **Memory Protection**: Memory-based files are protected by the Lambda execution environment.

3. **System Call Interception**: The `LD_PRELOAD` mechanism is a standard Linux feature and is secure within the Lambda execution environment.

## Limitations

1. **Linux Only**: The tool relies on Linux-specific features like `memfd_create` and `LD_PRELOAD`.

2. **Python 3.8+**: The tool requires Python 3.8 or later.

3. **Library Compatibility**: Some libraries may use non-standard file access methods that bypass the intercepted system calls.

4. **Memory Limits**: Lambda functions have memory limits (up to 10GB), which may still be insufficient for extremely large libraries.

5. **Import Edge Cases**: The custom import system may not handle all edge cases in Python's import system, particularly for libraries with complex import patterns.

## Future Improvements

1. **Compression**: Add support for compressed memory files to reduce memory usage.

2. **Caching**: Implement caching mechanisms to avoid downloading the same libraries repeatedly.

3. **Profiling**: Add profiling tools to help users optimize their library usage.

4. **Multi-Library Support**: Enhance support for loading multiple libraries with different configurations.

5. **Custom Interception**: Allow users to define custom interception rules for specific libraries.

## Conclusion

lambda-snaploader provides a robust solution for using large libraries in AWS Lambda with SnapStart integration. By leveraging memory-based file storage and system call interception, it overcomes the limitations of Lambda's file system and enables the use of libraries that would otherwise be too large or cause excessive cold start times.