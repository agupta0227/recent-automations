from pathlib import Path
import json

import torch
from torch.utils.data import Dataset, DataLoader

from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm


# --------------------------------------------------
# Basic setup
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRAIN_FILE = PROJECT_ROOT / "data" / "final" / "train.jsonl"

HARD_EMOTIONS_FILE = (
    PROJECT_ROOT / "data" / "custom" / "hard_emotions_vectorized.jsonl"
)

NEGATIVE_CLUSTER_FILE = (
    PROJECT_ROOT / "data" / "custom" / "cluster_training_examples_vectorized.jsonl"
)

POSITIVE_CLUSTER_FILE = (
    PROJECT_ROOT / "data" / "custom" / "positive_cluster_training_examples_vectorized.jsonl"
)

MODEL_PATH = PROJECT_ROOT / "models" / "emotion_classifier" / "model.pt"

MODEL_NAME = "distilbert-base-uncased"

NUM_LABELS = 13
BATCH_SIZE = 16
EPOCHS = 1
LEARNING_RATE = 2e-5

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


# --------------------------------------------------
# Dataset
# --------------------------------------------------

class EmotionDataset(Dataset):

    def __init__(self, file_paths):

        self.samples = []

        for file_path in file_paths:

            with open(file_path, "r", encoding="utf-8") as f:

                for line in f:

                    line = line.strip()

                    if not line:
                        continue

                    self.samples.append(json.loads(line))

            print(f"Loaded file: {file_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):

        sample = self.samples[idx]

        encoding = tokenizer(
            sample["text"],
            truncation=True,
            padding="max_length",
            max_length=64,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(
                sample["emotion_vector"],
                dtype=torch.float
            )
        }


# --------------------------------------------------
# Model
# --------------------------------------------------

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


# --------------------------------------------------
# Load combined training data
# --------------------------------------------------

train_dataset = EmotionDataset([
    TRAIN_FILE,
    HARD_EMOTIONS_FILE,
    NEGATIVE_CLUSTER_FILE,
    POSITIVE_CLUSTER_FILE
])

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True
)

print(f"\nTotal training samples loaded: {len(train_dataset)}")
print(f"Total training batches: {len(train_loader)}")


# --------------------------------------------------
# Load existing model
# --------------------------------------------------

model = EmotionClassifier().to(DEVICE)

if MODEL_PATH.exists():

    print(f"\nLoading existing model from: {MODEL_PATH}")

    model.load_state_dict(
        torch.load(MODEL_PATH, map_location=DEVICE)
    )

else:

    print("\nNo existing model found. Training from scratch.")


# --------------------------------------------------
# Training setup
# --------------------------------------------------

loss_fn = torch.nn.BCEWithLogitsLoss()

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE
)


# --------------------------------------------------
# Training loop
# --------------------------------------------------

for epoch in range(EPOCHS):

    model.train()

    total_train_loss = 0

    for batch in tqdm(
        train_loader,
        desc=f"Rosie v2 Augmented Epoch {epoch + 1}/{EPOCHS}"
    ):

        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)
        labels = batch["labels"].to(DEVICE)

        optimizer.zero_grad()

        logits = model(input_ids, attention_mask)

        loss = loss_fn(logits, labels)

        loss.backward()

        optimizer.step()

        total_train_loss += loss.item()

    avg_train_loss = total_train_loss / len(train_loader)

    print(f"\nRosie v2 Augmented Epoch {epoch + 1}/{EPOCHS}")
    print(f"Training loss: {avg_train_loss:.4f}")


# --------------------------------------------------
# Save updated model
# --------------------------------------------------

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

torch.save(
    model.state_dict(),
    MODEL_PATH
)

print(f"\nUpdated model saved to: {MODEL_PATH}")