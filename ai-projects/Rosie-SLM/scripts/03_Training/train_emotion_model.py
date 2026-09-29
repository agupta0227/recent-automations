from pathlib import Path
import json

# PyTorch core utilities
import torch
from torch.utils.data import Dataset, DataLoader

# Hugging Face tokenizer
from transformers import AutoTokenizer

# Get project root folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Path to training dataset
TRAIN_FILE = PROJECT_ROOT / "data" / "final" / "train.jsonl"

# Pretrained tokenizer name
MODEL_NAME = "distilbert-base-uncased"

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


# Custom dataset class for emotion data
class EmotionDataset(Dataset):

    # Load all JSONL samples into memory
    def __init__(self, file_path):

        self.samples = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                self.samples.append(json.loads(line))

    # Return total number of samples
    def __len__(self):
        return len(self.samples)

    # Return one processed sample
    def __getitem__(self, idx):

        sample = self.samples[idx]

        # Convert text into token IDs
        encoding = tokenizer(
            sample["text"],
            truncation=True,          # cut long sentences
            padding="max_length",    # fixed-size padding
            max_length=64,           # max token length
            return_tensors="pt"      # return PyTorch tensors
        )

        return {

            # Numeric token representation of text
            "input_ids": encoding["input_ids"].squeeze(0),

            # Mask showing real tokens vs padding
            "attention_mask": encoding["attention_mask"].squeeze(0),

            # Emotion vector target labels
            "labels": torch.tensor(
                sample["emotion_vector"],
                dtype=torch.float
            )
        }


# Create dataset object
dataset = EmotionDataset(TRAIN_FILE)

print("Dataset size:", len(dataset))

# Read first processed sample
sample = dataset[0]

print("\nSample tensors:\n")

# Shape of token tensor
print("input_ids shape:", sample["input_ids"].shape)

# Shape of attention mask
print("attention_mask shape:", sample["attention_mask"].shape)

# Multi-label emotion vector
print("labels:", sample["labels"])