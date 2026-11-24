import sys
from pathlib import Path

# Add mosque_discovery to Python path so tests can import discovery module
sys.path.insert(0, str(Path(__file__).parent.parent))
