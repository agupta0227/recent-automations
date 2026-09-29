from pathlib import Path
import csv
from collections import defaultdict, Counter


# --------------------------------------------------
# Basic setup
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_CSV = PROJECT_ROOT / "outputs" / "cluster_benchmark_results.csv"


# --------------------------------------------------
# Helper function
# --------------------------------------------------

def extract_emotion(emotion_with_score):
    """
    Example:
    'sadness (0.94)' -> 'sadness'
    """
    return emotion_with_score.split("(")[0].strip()


# --------------------------------------------------
# Read cluster benchmark results
# --------------------------------------------------

cluster_counts = defaultdict(Counter)
cluster_total = Counter()

with open(INPUT_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        cluster = row["concept_or_cluster"]

        emotion_1 = extract_emotion(row["emotion_1"])
        emotion_2 = extract_emotion(row["emotion_2"])
        emotion_3 = extract_emotion(row["emotion_3"])

        cluster_counts[cluster][emotion_1] += 1
        cluster_counts[cluster][emotion_2] += 1
        cluster_counts[cluster][emotion_3] += 1

        cluster_total[cluster] += 3


# --------------------------------------------------
# Print analysis
# --------------------------------------------------

print("\n" + "=" * 100)
print("CLUSTER EMOTION DISTRIBUTION ANALYSIS")
print("=" * 100)

for cluster, counter in cluster_counts.items():

    print("\n" + "-" * 100)
    print(f"CLUSTER: {cluster}")
    print("-" * 100)

    total = cluster_total[cluster]

    for emotion, count in counter.most_common():

        percent = (count / total) * 100

        print(f"{emotion:<15} {count:<5} {percent:.2f}%")