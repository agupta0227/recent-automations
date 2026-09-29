from datasets import load_dataset
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent

output_path = PROJECT_ROOT / "data" / "processed" / "goemotions_mapped.jsonl"
output_path.parent.mkdir(parents=True, exist_ok=True)

dataset = load_dataset("go_emotions")
label_names = dataset["train"].features["labels"].feature.names

MAIN_EMOTION_MAP = {
    "admiration": "joy",
    "amusement": "joy",
    "approval": "joy",
    "caring": "love",
    "desire": "love",
    "excitement": "joy",
    "gratitude": "joy",
    "joy": "joy",
    "love": "love",
    "optimism": "joy",
    "pride": "joy",
    "relief": "joy",

    "anger": "anger",
    "annoyance": "anger",
    "disapproval": "anger",
    "disgust": "anger",

    "sadness": "sadness",
    "disappointment": "sadness",
    "grief": "sadness",
    "remorse": "guilt",
    "embarrassment": "shame",

    "fear": "fear",
    "nervousness": "anxiety",

    "confusion": "confusion",
    "curiosity": "curiosity",
    "realization": "realization",
    "surprise": "surprise",
    "neutral": "neutral",
}

with open(output_path, "w", encoding="utf-8") as f:
    for row in dataset["train"]:
        deep_emotions = [label_names[i] for i in row["labels"]]
        main_emotions = sorted(set(MAIN_EMOTION_MAP[e] for e in deep_emotions))

        record = {
            "text": row["text"],
            "main_emotions": main_emotions,
            "deep_emotions": deep_emotions,
        }

        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Saved: {output_path}")