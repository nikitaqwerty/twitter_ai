import os
import csv
import shutil
from utils.config import Config
from huggingface_hub import Repository, create_repo

# Paths
RAW_CSV = "/Users/nikita/projects/twitter_ai/data/runs.csv"
NEW_DATASET_DIR = "length_captchas"
IMAGES_DIR = os.path.join(NEW_DATASET_DIR, "images")


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Read CSV rows
    with open(RAW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

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

    # Create a minimal README.
    readme = os.path.join(NEW_DATASET_DIR, "README.md")
    with open(readme, "w") as f:
        f.write(
            "# Length Captchas Dataset\n\nConverted dataset from twitter_ai label tool.\n"
        )

    # Create the dataset repository on Hugging Face (if it doesn't exist)
    token = Config.HF_TOKEN
    try:
        create_repo("length_captchas", token=token, repo_type="dataset", exist_ok=True)
    except Exception as e:
        print("Repo creation may have been skipped:", e)

    # Clone (or initialize) and push the new dataset folder.
    repo = Repository(
        local_dir=NEW_DATASET_DIR,
        clone_from="nikita-nrg/length_captchas",
        use_auth_token=True,
    )
    repo.git_add(auto_lfs_track=True)
    repo.git_commit("Upload length captchas dataset")
    repo.git_push()


if __name__ == "__main__":
    main()
