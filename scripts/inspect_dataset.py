from pathlib import Path
import sys
import pandas as pd

if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python scripts/inspect_dataset.py "
        "data/raw/Stravl_Travel_Preference_Data.csv"
    )

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"File not found: {path}")

# Read in chunks to avoid loading the full file into memory.
reader = pd.read_csv(path, chunksize=10_000, low_memory=False)
total_rows = 0
first_chunk = None
null_counts = None

for chunk in reader:
    if first_chunk is None:
        first_chunk = chunk.head(5)
        null_counts = chunk.isna().sum()
    else:
        null_counts = null_counts.add(chunk.isna().sum(), fill_value=0)
    total_rows += len(chunk)

print("\n=== DATASET PROFILE ===")
print(f"File: {path}")
print(f"Rows: {total_rows:,}")
print(f"Columns: {len(first_chunk.columns)}")
print("\n=== COLUMN NAMES ===")
for col in first_chunk.columns:
    print(f"- {col}")
print("\n=== SAMPLE ROWS ===")
print(first_chunk.to_string(index=False))
print("\n=== NULL COUNTS (first chunk only; indicative) ===")
print(null_counts.sort_values(ascending=False).to_string())
print("\n=== INFERRED DTYPES (first chunk) ===")
print(first_chunk.dtypes.to_string())
print(
    "\nNote: Null counts above are from the first chunk only. "
    "We will run a complete profiling pass after confirming the file."
)
