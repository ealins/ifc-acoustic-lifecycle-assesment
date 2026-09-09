"""Compatibility entrypoint for the Acoustic Component Research Object prototype."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.ui.research_enhanced_app import run_research_enhanced_app

run_research_enhanced_app()
