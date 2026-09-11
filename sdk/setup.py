from setuptools import setup, find_packages

setup(
    name="shivai",
    version="1.0.0",
    description="Official Python SDK for the ShivAI AI Backend.",
    author="ShivAI Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.7.0",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
    ],
)
