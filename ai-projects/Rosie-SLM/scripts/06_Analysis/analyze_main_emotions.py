import json
from collections import Counter

file_path = "data/processed/goemotions_mapped.jsonl"

main_counter = Counter()

with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)

        for emotion in record["main_emotions"]:
            main_counter[emotion] += 1

print("\nMain Emotion Counts:\n")

for emotion, count in main_counter.most_common():
    print(f"{emotion}: {count}")