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

CUSTOM_VAL_FILE = PROJECT_ROOT / "data" / "custom" / "custom_val.jsonl"

MODEL_PATH = PROJECT_ROOT / "models" / "emotion_classifier" / "model.pt"

MODEL_NAME = "distilbert-base-uncased"

NUM_LABELS = 13
BATCH_SIZE = 16

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


# --------------------------------------------------
# Dataset
# --------------------------------------------------

class EmotionDataset(Dataset):

    def __init__(self, file_path):

        self.samples = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:

                line = line.strip()

                if not line:
                    continue

                self.samples.append(json.loads(line))

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
# Load custom validation data
# --------------------------------------------------

custom_val_dataset = EmotionDataset(CUSTOM_VAL_FILE)

custom_val_loader = DataLoader(
    custom_val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)

print(f"Custom validation samples: {len(custom_val_dataset)}")


# --------------------------------------------------
# Load trained model
# --------------------------------------------------

model = EmotionClassifier().to(DEVICE)

model.load_state_dict(
    torch.load(MODEL_PATH, map_location=DEVICE)
)

model.eval()


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

loss_fn = torch.nn.BCEWithLogitsLoss()

total_loss = 0

with torch.no_grad():

    for batch in tqdm(custom_val_loader, desc="Custom Validation"):

        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)
        labels = batch["labels"].to(DEVICE)

        logits = model(input_ids, attention_mask)

        loss = loss_fn(logits, labels)

        total_loss += loss.item()


avg_loss = total_loss / len(custom_val_loader)

print("\nCustom Validation Loss:")
print(f"{avg_loss:.4f}")