"""Compatibility entrypoint for the FAIR Acoustic Component Platform."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.ui.platform_app import run_platform_app

run_platform_app()
