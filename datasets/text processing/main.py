from datasets import load_dataset
import pandas as pd
import re


DATASET_NAME = "smangrul/ad-copy-generation"


def extract_ad_only(text):
    text = str(text)
    # Remove INST tokens for data text extraction
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
    dataset = load_dataset(DATASET_NAME)

    df_train = dataset["train"].to_pandas()
    df_test = dataset["test"].to_pandas()
    df = pd.concat([df_train, df_test], ignore_index=True)
    df["ad_text"] = df["content"].apply(extract_ad_only)
    df["ad_text"] = df["ad_text"].apply(clean_text)
    df = df[df["ad_text"].str.split().str.len() >= 3]
    df = df.drop_duplicates(subset=["ad_text"])

    df["label"] = "advertisement"
    final_df = df[["ad_text", "label"]]
    final_df.to_csv("ads_dataset_full.csv", index=False)

    print("Saved ads_dataset_full.csv")
    print(final_df.head())


if __name__ == "__main__":
    main()