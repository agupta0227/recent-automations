from pathlib import Path
import random


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CUSTOM_DIR = PROJECT_ROOT / "data" / "custom"

INPUT_FILES = [
    CUSTOM_DIR / "hard_emotions_vectorized.jsonl",
    CUSTOM_DIR / "cluster_training_examples_vectorized.jsonl",
    CUSTOM_DIR / "positive_cluster_training_examples_vectorized.jsonl"
]

OUTPUT_TRAIN = CUSTOM_DIR / "custom_train.jsonl"
OUTPUT_VAL = CUSTOM_DIR / "custom_val.jsonl"
OUTPUT_TEST = CUSTOM_DIR / "custom_test.jsonl"

RANDOM_SEED = 42


def read_jsonl(file_path):
    lines = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                lines.append(line + "\n")

    return lines


all_lines = []

for input_file in INPUT_FILES:
    rows = read_jsonl(input_file)

    print(f"Loaded {len(rows)} rows from: {input_file}")

    all_lines.extend(rows)


random.seed(RANDOM_SEED)
random.shuffle(all_lines)

total = len(all_lines)

train_end = int(total * 0.8)
val_end = int(total * 0.9)

train_lines = all_lines[:train_end]
val_lines = all_lines[train_end:val_end]
test_lines = all_lines[val_end:]


with open(OUTPUT_TRAIN, "w", encoding="utf-8") as f:
    f.writelines(train_lines)

with open(OUTPUT_VAL, "w", encoding="utf-8") as f:
    f.writelines(val_lines)

with open(OUTPUT_TEST, "w", encoding="utf-8") as f:
    f.writelines(test_lines)


print("\nCustom split created:")
print(f"Train: {len(train_lines)} rows -> {OUTPUT_TRAIN}")
print(f"Val:   {len(val_lines)} rows -> {OUTPUT_VAL}")
print(f"Test:  {len(test_lines)} rows -> {OUTPUT_TEST}")