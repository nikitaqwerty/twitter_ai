import os
import sys
import shutil
import pandas as pd

# Ensure the repository root is in PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from twitter_ai.utils.config import Config
from huggingface_hub import create_repo, HfApi, upload_folder

# Paths
RAW_CSV = "/Users/nikita/projects/twitter_ai/data/runs.csv"
NEW_DATASET_DIR = "length_captchas"
IMAGES_DIR = os.path.join(NEW_DATASET_DIR, "images")


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Read CSV using pandas and ensure necessary columns are strings.
    df = pd.read_csv(RAW_CSV)
    df["task type"] = df["task type"].fillna("").astype(str)
    df["bad record"] = df["bad record"].fillna("").astype(str)
    df["right ground truth"] = df["right ground truth"].fillna("").astype(str)
    df["first_scale_value"] = df["first_scale_value"].fillna("").astype(str)
    df["filename right"] = df["filename right"].fillna("").astype(str)

    # Filter rows based on conditions.
    mask = (
        (df["task type"].str.strip().str.lower() == "length")
        & (df["bad record"].str.strip().str.lower().isin(["", "false"]))
        & (df["right ground truth"].str.strip() != "")
        & (df["first_scale_value"].str.strip() != "")
    )
    df = df[mask].copy()

    # Set left image references to empty.
    df["filename left"] = ""

    # Process right image: copy image if exists and update path.
    def process_right_image(row):
        orig_path = row["filename right"]
        if orig_path and os.path.exists(orig_path):
            base = os.path.basename(orig_path)
            new_rel = os.path.join("images", base)
            new_abs = os.path.join(IMAGES_DIR, base)
            if not os.path.exists(new_abs):
                shutil.copy2(orig_path, new_abs)
            return new_rel
        return ""

    df["filename right"] = df.apply(process_right_image, axis=1)

    # Write the new CSV file.
    new_csv = os.path.join(NEW_DATASET_DIR, "dataset.csv")
    df.to_csv(new_csv, index=False)

    # Create a minimal README with YAML metadata.
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

    # Create the dataset repository on Hugging Face (if it doesn't exist).
    token = Config.HF_TOKEN
    try:
        create_repo("length_captchas", token=token, repo_type="dataset", exist_ok=True)
    except Exception as e:
        print("Repo creation may have been skipped:", e)

    # Upload the dataset folder.
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
