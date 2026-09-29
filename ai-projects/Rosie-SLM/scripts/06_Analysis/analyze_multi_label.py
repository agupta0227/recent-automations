import json
from collections import Counter

file_path = "data/processed/goemotions_mapped.jsonl"

main_label_count = Counter()
deep_label_count = Counter()

with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)

        main_label_count[len(record["main_emotions"])] += 1
        deep_label_count[len(record["deep_emotions"])] += 1

print("Main emotion label counts per sentence:")
for label_count, rows in sorted(main_label_count.items()):
    print(f"{label_count} emotion(s): {rows} rows")

print("\nDeep emotion label counts per sentence:")
for label_count, rows in sorted(deep_label_count.items()):
    print(f"{label_count} emotion(s): {rows} rows")