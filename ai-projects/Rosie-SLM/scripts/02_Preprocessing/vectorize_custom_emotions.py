from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "custom" / "positive_cluster_training_examples.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "custom" / "positive_cluster_training_examples_vectorized.jsonl"

MAIN_EMOTIONS = [
    "joy",
    "neutral",
    "anger",
    "love",
    "sadness",
    "curiosity",
    "confusion",
    "realization",
    "surprise",
    "fear",
    "guilt",
    "shame",
    "anxiety"
]

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as fin, \
     open(OUTPUT_FILE, "w", encoding="utf-8") as fout:

    for line in fin:
        line = line.strip()

        if not line:
            continue

        record = json.loads(line)
        vector = []

        for emotion in MAIN_EMOTIONS:
            if emotion in record["main_emotions"]:
                vector.append(1)
            else:
                vector.append(0)

        output_record = {
            "text": record["text"],
            "main_emotions": record["main_emotions"],
            "deep_emotions": record["deep_emotions"],
            "emotion_vector": vector
        }

        fout.write(json.dumps(output_record, ensure_ascii=False) + "\n")

print(f"Saved: {OUTPUT_FILE}")