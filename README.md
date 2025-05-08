# lambda-snaploader

A tool for loading large libraries in AWS Lambda with SnapStart integration, especially useful for machine learning libraries like PyTorch, TensorFlow, and other large dependencies.

## Features

- Uses `memfd_create` to create files in memory, avoiding the size limitations of the `/tmp` directory
- Intercepts system calls via `LD_PRELOAD` to redirect library file loading paths
- Downloads and loads libraries directly from S3
- Seamlessly integrates with Lambda SnapStart to reduce cold start times
- Simple and easy-to-use Python API
- Automatically discovers and maps all shared libraries, no configuration needed

## Installation

```bash
pip install lambda-snaploader
```

## Usage

### Simplified Usage

```python
import os
from lambda_snaploader import load_libraries_from_s3

# One-step setup for any library
load_libraries_from_s3(
    bucket='your-bucket',
    key='libraries.zip',
    target_dir='/tmp/lib_so'
)

# Now you can import your library
import your_library
```

### PyTorch Example (Simplified)

```python
from lambda_snaploader import load_libraries_from_s3

# Setup for PyTorch - no need to specify source paths!
load_libraries_from_s3(
    bucket='your-bucket',
    key='pytorch_libs.zip',
    target_dir='/tmp/pytorch_so'
)

# Now you can import PyTorch
import torch
import functorch  # Works with all .so files automatically!
```

### Custom Base Path Example

```python
from lambda_snaploader import load_libraries_from_s3

# For libraries installed in a different location
load_libraries_from_s3(
    bucket='your-bucket',
    key='libraries.zip',
    target_dir='/tmp/lib_so',
    base_path='/opt/ml/model'  # Custom base path
)

# Now you can import your library
import your_library
```

### Complete Lambda Function Example

```python
import json
import os
import logging
import time
from lambda_snaploader import setup_library_from_s3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variables
ml_module = None
model = None

def load_library():
    """
    Load the machine learning library
    """
    global ml_module, model
    
    # If library is already loaded, return immediately
    if ml_module is not None:
        return True
    
    start_time = time.time()
    
    try:
        # Setup library from S3
        load_libraries_from_s3(
            bucket=os.environ.get('LIBRARY_BUCKET'),
            key=os.environ.get('LIBRARY_KEY'),
            target_dir=os.environ.get('LIBRARY_TARGET_DIR', '/tmp/lib_so'),
            base_path=os.environ.get('LIBRARY_BASE_PATH', '/var/task')
        )
        
        # Import the library (PyTorch in this example)
        import torch
        ml_module = torch
        
        # Create a simple model
        model = torch.nn.Sequential(
            torch.nn.Linear(10, 5),
            torch.nn.ReLU(),
            torch.nn.Linear(5, 1)
        )
        
        logger.info(f"Library loaded successfully, version: {torch.__version__}")
        logger.info(f"Total time: {time.time() - start_time:.2f} seconds")
        
        return True
    except Exception as e:
        logger.error(f"Failed to load library: {e}")
        return False

# Load library during module initialization
load_library()

def lambda_handler(event, context):
    """
    Lambda function handler
    """
    # Ensure library is loaded
    if ml_module is None:
        if not load_library():
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to load library"})
            }
    
    # From request body
    try:
        body = json.loads(event.get('body', '{}'))
        input_data = body.get('input', [0.1] * 10)
    except:
        input_data = [0.1] * 10
    
    # Run inference
    try:
        input_tensor = ml_module.tensor(input_data, dtype=ml_module.float32)
        with ml_module.no_grad():
            output = model(input_tensor)
        
        result = {
            "result": output.tolist(),
            "version": ml_module.__version__
        }
    except Exception as e:
        result = {"error": str(e)}
    
    # Return the result
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Inference completed",
            "result": result
        })
    }
```

### Advanced Usage

#### Manual Configuration

```python
from lambda_snaploader import setup_preload, stream_libraries_from_s3, register_snapstart_hook, set_base_path

# Set the base path for original files
set_base_path('/opt/ml/model')

# Set up the preload library
setup_preload()

# Download and load library files from S3
stream_libraries_from_s3(
    bucket='your-bucket',
    key='libraries.zip',
    target_dir='/tmp/custom_libs'
)

# Register the SnapStart restore hook
register_snapstart_hook(target_dir='/tmp/custom_libs')
```

#### Custom File Filter

```python
from lambda_snaploader import load_libraries_from_s3

# Load only specific library files
load_libraries_from_s3(
    bucket='your-bucket',
    key='libraries.zip',
    target_dir='/tmp/lib_so',
    file_filter=lambda name: (
        name.endswith('.so') or 
        '.so.' in name or 
        name.startswith('lib/') and name.endswith('.py')
    )
)
```

#### Manual Memory File Management

```python
from lambda_snaploader import create_memory_file, create_symlinks, set_base_path

# Set the base path for original files
set_base_path('/opt/ml/model')

# Create a memory file
with open('large_lib.so', 'rb') as f:
    content = f.read()
    fd = create_memory_file('large_lib.so', content)

# Create symbolic links
create_symlinks('/tmp/custom_libs')
```

## How It Works

1. **Memory File Creation**: The library uses `memfd_create` to create files in memory, avoiding the size limitations of the `/tmp` directory.

2. **Path Mapping**: When you load libraries, the library automatically:
   - Creates a mapping file in `/tmp` that maps original paths to memory file paths
   - Sets up a preload library that intercepts system calls and redirects file paths

3. **Automatic Discovery**: The library automatically discovers all shared libraries in your ZIP file, so you don't need to specify any paths.

4. **SnapStart Integration**: When Lambda uses SnapStart to restore your function, the library automatically recreates the symbolic links.

## API Reference

### load_libraries_from_s3(bucket, key, base_path='/var/task', target_dir='/tmp/lib_so', file_filter=None)

One-step setup for loading libraries from S3 with SnapStart integration.

### set_base_path(path)

Sets the base path for original files (e.g., '/var/task', '/opt/ml/model').

### setup_preload()

Sets up the preload library to intercept system calls and redirect library file loading paths.

### stream_libraries_from_s3(bucket, key, file_filter, base_path='/var/task', target_dir='/tmp/pytorch_so')

Downloads library files from S3, loads them into memory, and creates symbolic links.

### register_snapstart_hook(target_dir='/tmp/pytorch_so')

Registers a SnapStart restore hook to recreate symbolic links when the Lambda function is restored.

### create_memory_file(name, content)

Creates a file in memory and returns its file descriptor.

### create_symlinks(target_dir='/tmp/pytorch_so')

Creates symbolic links for files in memory.

### get_file_descriptors()

Gets a mapping of all file descriptors.

## License

MIT