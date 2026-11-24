"""Pytest configuration for mosque discovery tests."""
import sys
from pathlib import Path

# Add mosque_discovery to sys.path so discovery module can be imported
sys.path.insert(0, str(Path(__file__).parent))
