import os
from pathlib import Path

# Check what data files are available
data_dir = Path(r"e:\thesis\thesis_experiment_vscode\thesis_experiment_vscode\data")

print("=== Data Directory Contents ===")
if data_dir.exists():
    for f in sorted(data_dir.iterdir()):
        size = f.stat().st_size if f.is_file() else 0
        print(f"  {f.name} ({size:,} bytes)")
else:
    print(f"Data directory not found: {data_dir}")

# Also search for performance record files in the whole project
print("\n=== Searching for performance/ICF files ===")
project_dir = Path(r"e:\thesis\thesis_experiment_vscode\thesis_experiment_vscode")
for root, dirs, files in os.walk(project_dir):
    # Skip venv, __pycache__, .git
    dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', '.claude', 'node_modules']]
    for file in files:
        if "performance" in file.lower() or "icf" in file.lower():
            full_path = Path(root) / file
            size = full_path.stat().st_size
            print(f"  {full_path.relative_to(project_dir)} ({size:,} bytes)")
