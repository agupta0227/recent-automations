from pathlib import Path
import json

# PyTorch library
import torch

# Base dataset utilities
from torch.utils.data import Dataset

# Hugging Face transformer utilities
from transformers import (
    AutoTokenizer,
    AutoModel
)

# Get root folder of project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Training dataset path
TRAIN_FILE = PROJECT_ROOT / "data" / "final" / "train.jsonl"

# Pretrained transformer model name
MODEL_NAME = "distilbert-base-uncased"

# Total number of main emotions
NUM_LABELS = 13

# Load pretrained tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


# Custom dataset class
class EmotionDataset(Dataset):

    # Load JSONL samples
    def __init__(self, file_path):

        self.samples = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                self.samples.append(json.loads(line))

    # Return dataset size
    def __len__(self):
        return len(self.samples)

    # Return one processed sample
    def __getitem__(self, idx):

        # Get one row
        sample = self.samples[idx]

        # Convert sentence into tokens
        encoding = tokenizer(
            sample["text"],

            # Cut long text
            truncation=True,

            # Pad smaller sentences
            padding="max_length",

            # Fixed token size
            max_length=64,

            # Return PyTorch tensors
            return_tensors="pt"
        )

        return {

            # Numeric token IDs
            "input_ids": encoding["input_ids"].squeeze(0),

            # Mask for real tokens vs padding
            "attention_mask": encoding["attention_mask"].squeeze(0),

            # Multi-label target vector
            "labels": torch.tensor(
                sample["emotion_vector"],
                dtype=torch.float
            )
        }


# Emotion classification neural network
class EmotionClassifier(torch.nn.Module):

    def __init__(self):

        super().__init__()

        # Load pretrained DistilBERT encoder
        self.encoder = AutoModel.from_pretrained(MODEL_NAME)

        # Final prediction layer
        # Converts embeddings -> emotion scores
        self.classifier = torch.nn.Linear(

            # Input size from DistilBERT
            self.encoder.config.hidden_size,

            # Output size = emotion count
            NUM_LABELS
        )

    # Forward pass
    def forward(self, input_ids, attention_mask):

        # Pass tokens through transformer
        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        # Take first token embedding (CLS representation)
        cls_embedding = outputs.last_hidden_state[:, 0]

        # Convert embedding into emotion prediction scores
        logits = self.classifier(cls_embedding)

        return logits


# Load training dataset
dataset = EmotionDataset(TRAIN_FILE)

# Read one sample
sample = dataset[0]

# Create neural network
model = EmotionClassifier()

# Add batch dimension
input_ids = sample["input_ids"].unsqueeze(0)
attention_mask = sample["attention_mask"].unsqueeze(0)

# Run forward pass
logits = model(input_ids, attention_mask)

print("\nLogits shape:")
print(logits.shape)

print("\nRaw logits:")
print(logits)

# Convert raw logits into probabilities between 0 and 1
probabilities = torch.sigmoid(logits)

print("\nProbabilities:")
print(probabilities)