from setuptools import find_packages, setup
import os
import sys

# Add the package directory to the path to import version
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fetchx_cli"))
from _version import __version__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements from requirements.txt, excluding dev dependencies
with open("requirements.txt", "r", encoding="utf-8") as fh:
    lines = fh.readlines()

requirements = []
for line in lines:
    line = line.strip()
    # Skip comments, empty lines, and development dependencies
    if (
        line
        and not line.startswith("#")
        and line not in ["pytest", "pytest-asyncio", "black", "flake8", "mypy"]
    ):
        requirements.append(line)

setup(
    name="fetchx",
    version=__version__,
    author="Fetchx IDM Team",
    author_email="",
    description="A powerful command-line Internet Download Manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/theany-org/fetchx",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "fetchx=fetchx_cli.main:main",
            "fx=fetchx_cli.main:main",
        ],
    },
)
