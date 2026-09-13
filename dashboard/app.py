"""Compatibility entrypoint for the IFC-linked vibrometry thesis demonstrator."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.ui.vibrometry_thesis_app import run_vibrometry_thesis_app


run_vibrometry_thesis_app()