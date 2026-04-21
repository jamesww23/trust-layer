"""Setup configuration for aitrustlayer package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aitrustlayer",
    version="0.1.0",
    author="MIT SFMBA MAS.664 Team 8",
    author_email="noreply@wisdomfinancialfreedom.com",
    description="Python SDK for the Agentic Reputation Infrastructure Layer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jamesww23/trust-layer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[],  # No external dependencies for core SDK
    extras_require={
        "dev": ["pytest>=6.0", "black", "flake8"],
    },
    entry_points={},
)
