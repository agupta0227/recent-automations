from pathlib import Path
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "final" / "emotion_dataset.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "data" / "final"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 80% train, 20% temp
train_lines, temp_lines = train_test_split(
    lines,
    test_size=0.2,
    random_state=42
)

# split remaining 20% into 10% val + 10% test
val_lines, test_lines = train_test_split(
    temp_lines,
    test_size=0.5,
    random_state=42
)

splits = {
    "train.jsonl": train_lines,
    "val.jsonl": val_lines,
    "test.jsonl": test_lines
}

for filename, data in splits.items():

    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(data)

    print(f"Saved: {output_path} ({len(data)} rows)")