import json
from pathlib import Path

# Check what data files are available
data_dir = Path(r"e:\thesis\thesis_experiment_vscode\thesis_experiment_vscode\data")

print("Available data files:")
if data_dir.exists():
    for f in data_dir.iterdir():
        print(f"  {f.name}")
else:
    print(f"Data directory not found: {data_dir}")

# Check if icf_performance_records.json exists anywhere
print("\nSearching for performance record files...")
for root, dirs, files in data_dir.walk():
    for file in files:
        if "performance" in file.lower() or "icf" in file.lower():
            print(f"  Found: {root / file}")