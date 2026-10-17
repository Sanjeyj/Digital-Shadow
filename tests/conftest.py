"""
tests/conftest.py — Shared pytest fixtures and configuration.
"""

import os
import sys

# Ensure project root is on the path for all test modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
