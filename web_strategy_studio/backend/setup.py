# Minimal shim for `pip install -e .` on older pip / conda that does not fully
# support PEP 660 with pyproject.toml-only projects. Metadata comes from pyproject.toml.
from setuptools import setup

if __name__ == "__main__":
    setup()
