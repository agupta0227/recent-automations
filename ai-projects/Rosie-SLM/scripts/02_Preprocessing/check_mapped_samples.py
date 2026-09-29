import json

file_path = "data/processed/goemotions_mapped.jsonl"

with open(file_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        record = json.loads(line)

        print("TEXT:", record["text"])
        print("MAIN:", record["main_emotions"])
        print("DEEP:", record["deep_emotions"])
        print("-" * 50)

        if i == 9:
            break