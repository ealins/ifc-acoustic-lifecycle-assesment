"""Compatibility entrypoint for the FAIR Acoustic Component Platform."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.ui.enhanced_app import run_enhanced_app

run_enhanced_app()
