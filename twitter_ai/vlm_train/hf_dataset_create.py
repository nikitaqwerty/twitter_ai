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

# Base URL for the uploaded images on Hugging Face Hub.
REPO_URL = "https://huggingface.co/datasets/nikita-nrg/length_captchas/resolve/main"


def main():
    # Clean up NEW_DATASET_DIR if it exists.
    if os.path.exists(NEW_DATASET_DIR):
        shutil.rmtree(NEW_DATASET_DIR)

    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Read CSV and fill missing values.
    df = pd.read_csv(RAW_CSV)
    for col in [
        "task type",
        "bad record",
        "right ground truth",
        "first_scale_value",
        "filename right",
    ]:
        df[col] = df[col].fillna("").astype(str)

    # Filter rows based on conditions.
    mask = (
        (df["task type"].str.strip().str.lower() == "length")
        & (df["bad record"].str.strip().str.lower().isin(["", "false"]))
        & (df["right ground truth"].str.strip() != "")
        & (df["first_scale_value"].str.strip() != "")
    )
    df = df[mask].copy()

    # Process the right image: copy image if exists and update to URL.
    def process_image(path):
        if path and os.path.exists(path):
            base = os.path.basename(path)
            new_abs = os.path.join(IMAGES_DIR, base)
            if not os.path.exists(new_abs):
                shutil.copy2(path, new_abs)
            # Return the URL pointing to the image on HF Hub.
            return f"{REPO_URL}/images/{base}"
        return ""

    # Create multimodal columns.
    df["image"] = df["filename right"].apply(process_image)
    df["image_id"] = df["image"].apply(lambda x: os.path.basename(x) if x else "")
    df["ground_truth"] = df["right ground truth"]

    # Keep only the necessary columns.
    df = df[["image", "image_id", "ground_truth", "first_scale_value"]]

    # Write the new CSV file.
    new_csv = os.path.join(NEW_DATASET_DIR, "dataset.csv")
    df.to_csv(new_csv, index=False)

    # Create a README.md with YAML metadata to define multimodal features.
    readme = os.path.join(NEW_DATASET_DIR, "README.md")
    with open(readme, "w") as f:
        f.write(
            """---
dataset_info:
  features:
  - name: image
    dtype: image
  - name: image_id
    dtype: string
  - name: ground_truth
    dtype: string
  - name: first_scale_value
    dtype: string
configs:
- config_name: default
  data_files:
  - split: train
    path: dataset.csv
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
