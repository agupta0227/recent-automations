from datasets import load_dataset
import json

dataset = load_dataset("go_emotions")

label_names = dataset["train"].features["labels"].feature.names

output_path = "../data/processed/goemotions.jsonl"

with open(output_path, "w", encoding="utf-8") as f:

    for row in dataset["train"]:

        emotions = [label_names[i] for i in row["labels"]]

        record = {
            "text": row["text"],
            "emotions": emotions
        }

        f.write(json.dumps(record) + "\n")

print(f"Saved to {output_path}")