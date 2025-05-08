#!/bin/bash
set -e

# Create a temporary directory for the layer
LAYER_DIR=$(mktemp -d)
echo "Created temporary directory: $LAYER_DIR"

# Create the Python directory structure
mkdir -p $LAYER_DIR/python/lambda_snaploader

# Copy the lambda-snaploader source files
echo "Copying lambda-snaploader source files..."
cp -r ../../src/lambda_snaploader/* $LAYER_DIR/python/lambda_snaploader/

# Copy the setup.py file
cp ../../setup.py $LAYER_DIR/

# Install dependencies
echo "Installing dependencies..."
pip install -r hello_world/requirements.txt -t $LAYER_DIR/python/

# Build the C extension
echo "Building C extension..."
cd $LAYER_DIR
python setup.py build_ext --inplace
mv lambda_snaploader*.so python/lambda_snaploader/

# Create the layer zip file
echo "Creating layer zip file..."
cd $LAYER_DIR
zip -r ../lambda_layer.zip python/

# Clean up
cd ..
echo "Layer created at: $(pwd)/lambda_layer.zip"
echo "Cleaning up temporary directory..."
rm -rf $LAYER_DIR

echo "Done!"