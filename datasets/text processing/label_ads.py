import pandas as pd
import re
from rapidfuzz import fuzz


INPUT_FILE = "ads_dataset_full.csv"
CLEANED_FILE = "ads_dataset_cleaned.csv"
OUTPUT_FILE = "ads_dataset_labeled.csv"

TEXT_COLUMN = "ad_text"


LABEL_PATTERNS = {
    "Urgency": [
        "act now", "hurry", "today only", "ends soon", "last chance",
        "limited time", "book now", "shop now", "try it now",
        "apply today", "get tickets", "download now", "register now"
    ],
    "FOMO": [
        "don't miss", "miss out", "exclusive", "join", "trending",
        "popular", "be part of", "new arrivals", "just dropped"
    ],
    "Fear Appeals": [
        "risk", "protect", "danger", "avoid", "prevent", "unsafe",
        "warning", "secure", "safety", "threat", "privacy", "insurance"
    ],
    "Scarcity": [
        "limited stock", "limited supply", "while supplies last",
        "only a few", "few left", "selling fast", "limited edition"
    ],
    "Exaggerated Claims": [
        "best", "perfect", "amazing", "ultimate", "incredible",
        "unbeatable", "spectacular", "powerful", "revolutionary",
        "transform", "conquer", "premium", "exceptional", "effortless"
    ],
    "Authority Manipulation": [
        "expert", "doctor", "approved", "recommended", "certified",
        "sponsored by", "official", "industry leading", "clinically",
        "research", "science", "institute", "academy"
    ],
    "Social Proof": [
        "trusted by", "loved by", "customers", "reviews", "rated",
        "thousands", "millions", "award winning", "community", "fans"
    ],
}


def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"[^a-z0-9\s.,!?$%\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_low_quality(text):
    words = text.split()
    if len(words) < 6:
        return True
    if len(re.findall(r"[a-z]", text)) < 20:
        return True
    if text.count("?") >= 5:
        return True
    code_patterns = [
        r"\bapp\.post\b",
        r"\breq\.body\b",
        r"\bconsole\.log\b",
        r"\bwebhook\b",
        r"\bswitch\b",
        r"\bcase\b",
        r"\bbreak\b",
    ]

    if any(re.search(pattern, text) for pattern in code_patterns):
        return True
    return False


def score_label(text, keywords):
    score = 0
    for keyword in keywords:
        if keyword in text:
            score += 3
        else:
            for phrase in text.split("."):
                if fuzz.partial_ratio(keyword, phrase) >= 90:
                    score += 1
                    break
    return score


def assign_label(text):
    scores = {}
    for label, keywords in LABEL_PATTERNS.items():
        scores[label] = score_label(text, keywords)
    best_label = max(scores, key=scores.get)

    if scores[best_label] == 0:
        return None
    return best_label


def main():
    df = pd.read_csv(INPUT_FILE)
    df = df.dropna(subset=[TEXT_COLUMN])
    df[TEXT_COLUMN] = df[TEXT_COLUMN].apply(clean_text)

    df = df.drop_duplicates(subset=[TEXT_COLUMN])
    df = df[~df[TEXT_COLUMN].apply(is_low_quality)]
    cleaned_df = df[[TEXT_COLUMN]].copy()
    cleaned_df.to_csv(CLEANED_FILE, index=False)

    df["label"] = df[TEXT_COLUMN].apply(assign_label)

    labeled_df = df.dropna(subset=["label"])
    labeled_df = labeled_df[[TEXT_COLUMN, "label"]]
    labeled_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Cleaned dataset to {CLEANED_FILE}")
    print(f"Labeled dataset to {OUTPUT_FILE}")
    print(labeled_df["label"].value_counts())


if __name__ == "__main__":
    main()