from datasets import load_dataset
import pandas as pd
import re


DATASET_NAMES = [
    "smangrul/ad-copy-generation",
    "PeterBrendan/Ads_Creative_Ad_Copy_Programmatic"
]

OUTPUT_FILE = "ads_dataset_full.csv"


def extract_ad_only(text):
    text = str(text)
    if "[/INST]" in text:
        text = text.split("[/INST]", 1)[1]
    text = re.sub(r"^\s*ad:\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("<s>", "").replace("</s>", "")
    return text.strip()


def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"[^a-z0-9\s.,!?$%\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    all_data = []

    for dataset_name in DATASET_NAMES:
        print(f"Loading {dataset_name}...")
        dataset = load_dataset(dataset_name)
        split_frames = []

        if "train" in dataset:
            split_frames.append(dataset["train"].to_pandas())
        if "test" in dataset:
            split_frames.append(dataset["test"].to_pandas())
        if not split_frames:
            split_name = list(dataset.keys())[0]
            split_frames.append(dataset[split_name].to_pandas())

        df = pd.concat(split_frames, ignore_index=True)
        if "content" in df.columns:
            df["ad_text"] = df["content"].apply(extract_ad_only)
        elif "text" in df.columns:
            df["ad_text"] = df["text"]
        elif "ad_text" in df.columns:
            df["ad_text"] = df["ad_text"]

        else:
            text_cols = [
                c for c in df.columns
                if df[c].dtype == "object"
            ]
            df["ad_text"] = (
                df[text_cols]
                .fillna("")
                .astype(str)
                .agg(" ".join, axis=1)
            )

        df["ad_text"] = df["ad_text"].apply(clean_text)
        df = df[df["ad_text"].str.split().str.len() >= 3]
        all_data.append(df[["ad_text"]])

    final_df = pd.concat(all_data, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=["ad_text"])
    final_df["label"] = "advertisement"
    final_df = final_df[["ad_text", "label"]]
    final_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved {OUTPUT_FILE}")
    print(final_df.head())


if __name__ == "__main__":
    main()