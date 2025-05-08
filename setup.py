from setuptools import setup, Extension, find_packages
import platform
import os

# Check if running on Linux platform
if platform.system() != 'Linux':
    raise RuntimeError("lambda-snaploader only supports Linux platforms")

# Define C extension
libpreload = Extension(
    'lambda_snaploader.libpreload',
    sources=['src/lambda_snaploader/libpreload.c'],
    extra_compile_args=['-fPIC', '-Wall'],
    extra_link_args=['-ldl'],
)

# Read README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="lambda-snaploader",
    version="0.1.0",
    author="Harold Sun",
    author_email="sunhua@amazon.com",
    description="A tool for loading large libraries in AWS Lambda with SnapStart integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bnusunny/lambda-snaploader",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    ext_modules=[libpreload],
    install_requires=[
        "boto3>=1.24.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    keywords="aws, lambda, snapstart, shared libraries, pytorch",
)