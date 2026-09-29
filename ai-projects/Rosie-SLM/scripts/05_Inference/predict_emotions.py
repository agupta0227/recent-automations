from pathlib import Path
import json
import csv

import torch
from transformers import AutoTokenizer, AutoModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "models" / "emotion_classifier" / "model.pt"
MODEL_NAME = "distilbert-base-uncased"

# Change this to: "paraphrase" or "cluster" or "positive"
BENCHMARK_MODE = "positive"

if BENCHMARK_MODE == "paraphrase":
    BENCHMARK_FILE = PROJECT_ROOT / "data" / "custom" / "paraphrase_benchmark.jsonl"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "paraphrase_benchmark_results.csv"
    TITLE = "PARAPHRASE ROBUSTNESS BENCHMARK"

elif BENCHMARK_MODE == "cluster":
    BENCHMARK_FILE = PROJECT_ROOT / "data" / "custom" / "cluster_training_examples.jsonl"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "cluster_benchmark_results.csv"
    TITLE = "CLUSTER TRAINING EXAMPLES BENCHMARK"

elif BENCHMARK_MODE == "positive":
    BENCHMARK_FILE = PROJECT_ROOT / "data" / "custom" / "positive_paraphrase_benchmark.jsonl"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "positive_benchmark_results.csv"
    TITLE = "POSITIVE EMOTION BENCHMARK"

else:
    raise ValueError(
    "BENCHMARK_MODE must be 'paraphrase', 'cluster', or 'positive'.")


MAIN_EMOTIONS = [
    "joy", "neutral", "anger", "love", "sadness",
    "curiosity", "confusion", "realization", "surprise",
    "fear", "guilt", "shame", "anxiety"
]

NUM_LABELS = len(MAIN_EMOTIONS)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


class EmotionClassifier(torch.nn.Module):

    def __init__(self):
        super().__init__()

        self.encoder = AutoModel.from_pretrained(MODEL_NAME)

        self.classifier = torch.nn.Linear(
            self.encoder.config.hidden_size,
            NUM_LABELS
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        cls_embedding = outputs.last_hidden_state[:, 0]

        logits = self.classifier(cls_embedding)

        return logits


model = EmotionClassifier().to(DEVICE)

model.load_state_dict(
    torch.load(MODEL_PATH, map_location=DEVICE)
)

model.eval()


benchmark_rows = []

with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if not line:
            continue

        row = json.loads(line)

        benchmark_rows.append(row)


results = []

for row in benchmark_rows:

    concept = row.get("concept", row.get("cluster", "unknown"))
    sentence = row["text"]

    encoding = tokenizer(
        sentence,
        truncation=True,
        padding="max_length",
        max_length=64,
        return_tensors="pt"
    )

    input_ids = encoding["input_ids"].to(DEVICE)
    attention_mask = encoding["attention_mask"].to(DEVICE)

    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        probabilities = torch.sigmoid(logits).squeeze(0)

    emotion_scores = []

    for emotion, score in zip(MAIN_EMOTIONS, probabilities):
        emotion_scores.append((emotion, score.item()))

    emotion_scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    top_3 = emotion_scores[:3]

    results.append({
        "concept_or_cluster": concept,
        "sentence": sentence,
        "emotion_1": f"{top_3[0][0]} ({top_3[0][1]:.2f})",
        "emotion_2": f"{top_3[1][0]} ({top_3[1][1]:.2f})",
        "emotion_3": f"{top_3[2][0]} ({top_3[2][1]:.2f})"
    })


print("\n" + "=" * 200)
print(TITLE)
print("=" * 200)

print(
    f"{'CONCEPT / CLUSTER':<35} | "
    f"{'INPUT SENTENCE':<80} | "
    f"{'EMOTION 1':<20} | "
    f"{'EMOTION 2':<20} | "
    f"{'EMOTION 3':<20}"
)

print("-" * 200)

for row in results:
    print(
        f"{row['concept_or_cluster'][:33]:<35} | "
        f"{row['sentence'][:78]:<80} | "
        f"{row['emotion_1']:<20} | "
        f"{row['emotion_2']:<20} | "
        f"{row['emotion_3']:<20}"
    )


OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)

    writer.writerow([
        "benchmark_mode",
        "concept_or_cluster",
        "sentence",
        "emotion_1",
        "emotion_2",
        "emotion_3"
    ])

    for row in results:
        writer.writerow([
            BENCHMARK_MODE,
            row["concept_or_cluster"],
            row["sentence"],
            row["emotion_1"],
            row["emotion_2"],
            row["emotion_3"]
        ])

print(f"\nCSV exported to:\n{OUTPUT_CSV}")