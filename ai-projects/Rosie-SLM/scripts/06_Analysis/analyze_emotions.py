from datasets import load_dataset
from collections import Counter

dataset = load_dataset("go_emotions")

label_names = dataset["train"].features["labels"].feature.names

counter = Counter()

for row in dataset["train"]:

    emotions = [label_names[i] for i in row["labels"]]

    for emotion in emotions:
        counter[emotion] += 1

print("\nEmotion Counts:\n")

for emotion, count in counter.most_common():
    print(f"{emotion}: {count}")