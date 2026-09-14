"""
SatyaScan Dataset Quality & Distribution Report
Computes sample counts, category distributions, resolution statistics,
and tamper type breakdowns for evaluation transparency.
"""

import os
import csv
import cv2
from collections import Counter


def generate_report(metadata_path: str = "data/metadata.csv"):
    print("==================================================")
    print("SATYASCAN DATASET DISTRIBUTION REPORT")
    print("==================================================")

    if not os.path.exists(metadata_path):
        print(f"Error: {metadata_path} not found.")
        return

    with open(metadata_path, "r") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    total_samples = len(records)
    categories = Counter([r["category"] for r in records])
    tamper_types = Counter([r["tamper_type"] for r in records])
    doc_types = Counter([r["document_type"] for r in records])

    resolutions = []
    file_sizes = []

    for r in records:
        path = r["doc_path"]
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                resolutions.append(f"{img.shape[1]}x{img.shape[0]}")
            file_sizes.append(os.path.getsize(path) / 1024.0)

    print(f"Total Evaluated Samples: {total_samples}")
    print("\n--- Category Breakdown ---")
    for cat, count in categories.items():
        print(f"  • {cat.ljust(20)}: {count} ({count/total_samples*100:.1f}%)")

    print("\n--- Tamper / Anomaly Types ---")
    for ttype, count in tamper_types.items():
        print(f"  • {ttype.ljust(22)}: {count}")

    print("\n--- Document Types ---")
    for dt, count in doc_types.items():
        print(f"  • {dt.ljust(20)}: {count}")

    print("\n--- Image Resolution & Storage ---")
    res_counter = Counter(resolutions)
    for res, count in res_counter.items():
        print(f"  • Resolution {res.ljust(12)}: {count} images")
    if file_sizes:
        print(f"  • Average File Size   : {sum(file_sizes)/len(file_sizes):.1f} KB")

    print("==================================================")


if __name__ == "__main__":
    generate_report()
