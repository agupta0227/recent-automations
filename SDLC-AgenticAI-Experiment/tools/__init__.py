"""
tools package — makes `from tools.xxx import Xxx` work without
each module needing to manually append the parent directory to sys.path.
"""
import sys
import os

# Ensure the project root is on the path when tools are imported directly
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
