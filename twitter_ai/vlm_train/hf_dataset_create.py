import os
import sys
import csv
import shutil

# Ensure the repository root is in PYTHONPATH.
# This allows absolute imports like "from twitter_ai.utils.config import Config"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from twitter_ai.utils.config import Config
from huggingface_hub import create_repo, HfApi, upload_folder

# Paths
RAW_CSV = "/Users/nikita/projects/twitter_ai/data/runs.csv"
NEW_DATASET_DIR = "length_captchas"
IMAGES_DIR = os.path.join(NEW_DATASET_DIR, "images")


def filter_row(row):
    """
    Filter a CSV row based on specific conditions:
      - task_type must be "length"
      - bad record must be "FALSE" or empty
      - right ground truth must not be empty
      - first_scale_value must not be empty
    """
    if row.get("task type", "").strip().lower() != "length":
        return False
    br = row.get("bad record", "").strip().lower()
    if br not in ("", "false"):
        return False
    if not row.get("right ground truth", "").strip():
        return False
    if not row.get("first_scale_value", "").strip():
        return False
    return True


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Read CSV rows
    with open(RAW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Filter rows based on conditions
    rows = [row for row in rows if filter_row(row)]

    # Process rows: copy images and convert absolute paths to relative paths.
    for row in rows:
        for key in ["filename left", "filename right"]:
            orig_path = row.get(key, "")
            if orig_path and os.path.exists(orig_path):
                base = os.path.basename(orig_path)
                new_rel = os.path.join("images", base)
                new_abs = os.path.join(IMAGES_DIR, base)
                if not os.path.exists(new_abs):
                    shutil.copy2(orig_path, new_abs)
                row[key] = new_rel
            else:
                row[key] = ""

    # Write new CSV file in HF dataset folder.
    new_csv = os.path.join(NEW_DATASET_DIR, "dataset.csv")
    with open(new_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Create a minimal README with YAML metadata to address the warning.
    readme = os.path.join(NEW_DATASET_DIR, "README.md")
    with open(readme, "w") as f:
        f.write(
            """---
tags:
  - captcha
  - dataset
license: mit
---
# Length Captchas Dataset

Converted dataset from twitter_ai label tool.
"""
        )

    # Create the dataset repository on Hugging Face (if it doesn't exist)
    token = Config.HF_TOKEN
    try:
        create_repo("length_captchas", token=token, repo_type="dataset", exist_ok=True)
    except Exception as e:
        print("Repo creation may have been skipped:", e)

    # Upload the dataset folder using the HTTP-based alternative.
    api = HfApi()
    api.upload_folder(
        folder_path=NEW_DATASET_DIR,
        repo_id="nikita-nrg/length_captchas",
        repo_type="dataset",
        token=token,
        commit_message="Upload length captchas dataset",
    )


if __name__ == "__main__":
    main()
