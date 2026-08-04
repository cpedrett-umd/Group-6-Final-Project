"""Plain-language copy and trigger-phrase evidence for the 7 persuasion tactics.

The classifier returns one label per ad. The wireframe, though, quotes the
specific words that make an ad pushy ("Only 7 left" - counters like this are
usually fake). A sequence-classification head has no span output, so the quoted
evidence comes from here instead: a lexicon transcribed from the "Examples"
bullets in docs/labeling_guidelines.md, extended with close variants.

Keeping the lexicon anchored to the annotation guidelines matters -- the phrases
the UI highlights are the same ones the annotators were told to label on, so the
explanation is traceable to the project's own spec rather than invented.

Two independent signals therefore reach the panel, and the UI labels which is
which:
  * "model"  -- what the tuned DistilBERT predicted, with confidence
  * "phrase" -- a guideline trigger phrase literally present in the ad text
"""
from __future__ import annotations

import re

# Short labels for the panel. The dataset's class names are long
# ("Authority Manipulation"); the wireframe shows terse ones ("Authority").
DISPLAY_NAMES = {
    "Urgency": "Urgency",
    "Scarcity": "Scarcity",
    "FOMO": "FOMO",
    "Fear Appeals": "Fear",
    "Social Proof": "Social proof",
    "Authority Manipulation": "Authority",
    "Exaggerated Claims": "Big claim",
}

# Written at a reading level suited to the 60+ audience the wireframe targets:
# short sentences, no jargon, no hedging. "{phrase}" is replaced with the words
# actually found in the ad, so the explanation quotes the user's own ad back.
PHRASE_TEMPLATES = {
    "Urgency": '"{phrase}" is there to rush you. Real offers keep.',
    "Scarcity": '"{phrase}" — counters like this are usually fake.',
    "FOMO": '"{phrase}" is there to make you feel left out.',
    "Fear Appeals": '"{phrase}" builds pressure out of worry, not fact.',
    "Social Proof": '"{phrase}" is a crowd number you cannot check.',
    "Authority Manipulation": '"{phrase}," but no doctor or study is named.',
    "Exaggerated Claims": '"{phrase}" is a promise nothing can guarantee.',
}

# Shown when the model predicts a tactic but no trigger phrase matched --
# the wording is subtler than the lexicon, which is worth saying plainly.
GENERIC_EXPLANATIONS = {
    "Urgency": "The wording pushes you to act quickly. Real offers keep.",
    "Scarcity": "The wording suggests it is about to run out.",
    "FOMO": "The wording suggests you are being left behind.",
    "Fear Appeals": "The wording uses worry to move you.",
    "Social Proof": "The wording leans on what a crowd supposedly does.",
    "Authority Manipulation": "The wording borrows authority it does not show.",
    "Exaggerated Claims": "The wording promises more than can be proven.",
}

# ads_dataset_labeled.csv contains no "Neutral" rows, even though the labeling
# guidelines define the class. The classifier therefore has no way to say "this
# ad is fine" -- softmax must put its mass on one of the 7 tactics, so a plain
# ad still comes back as a tactic, just weakly (a bakery's opening-hours ad
# scores ~0.45 Urgency).
#
# A row backed only by a weak model score, with no trigger phrase anywhere in
# the text, is treated as "not sure" rather than reported as a finding. Saying
# "this ad uses 1 pressure tactic" about a harmless ad is exactly the kind of
# false alarm that would teach a 60+ user to stop trusting the tool. The score
# is not hidden -- it still appears in the full distribution under "Read the
# full explanation".
LOW_CONFIDENCE = 0.60

# Trigger phrases per tactic. Each entry is a regex fragment matched
# case-insensitively on word boundaries. Entries marked "guideline" are taken
# verbatim from docs/labeling_guidelines.md; the rest are near variants of the
# same idea that show up throughout ads_dataset_labeled.csv.
TRIGGER_PATTERNS = {
    "Urgency": [
        r"act now",              # guideline
        r"limited time",         # guideline
        r"today only",           # guideline
        r"before midnight",      # guideline
        r"sale ends(?: \w+)?",   # guideline
        r"ends toni ght|ends tonight",
        r"final hours?",
        r"last chance",
        r"hurry",
        r"don'?t wait",
        r"order now",
        r"buy now",
        r"expires? (?:soon|today|tonight)",
        r"while it lasts",
        r"right now",
        r"immediately",
    ],
    "Scarcity": [
        # "Only 7 left" (guideline) and its common longer form, "Only 7
        # bottles left" -- the optional noun keeps the whole phrase in the
        # quote rather than clipping it at the noun.
        r"only \d[\d,]* (?:\w+ )?(?:left|remaining|available)",  # guideline
        r"only \d[\d,]* (?:spots?|bottles?|seats?|items?|units?)",
        r"limited stock",        # guideline
        r"limited supply",
        r"limited spots? available",   # guideline
        r"while supplies last",  # guideline
        r"exclusive access",     # guideline
        r"limited edition",
        r"almost gone",
        r"selling fast",
        r"running out",
        r"few (?:left|remaining)",
        r"low stock",
    ],
    "FOMO": [
        r"everyone is (?:switching|using|talking)",  # guideline
        r"don'?t miss out",      # guideline
        r"join thousands",       # guideline
        r"join millions",
        r"be the first",         # guideline
        r"missing out",
        r"don'?t be left (?:out|behind)",
        r"others are already",
        r"everybody'?s",
    ],
    "Fear Appeals": [
        r"protect your \w+",     # guideline
        r"(?:your |may be )?at risk",   # guideline
        r"avoid (?:financial )?disaster",  # guideline
        r"stop harmful \w+",     # guideline
        r"harmful",
        r"dangerous",
        r"before it'?s too late",
        r"doctors? are alarmed",
        r"warning",
        r"suffer(?:ing)?",
        r"(?:supplement |product )?ban\b",
        r"side effects",
    ],
    "Social Proof": [
        r"trusted by millions",  # guideline
        r"top rated",            # guideline
        r"best sell(?:er|ing)",  # guideline
        r"#\s?1\b",
        r"\d[\d,.]*\+? (?:million |thousand )?(?:satisfied |happy )?customers",
        r"over \d[\d,.]*(?: million| thousand)? (?:users|customers|people)",
        r"loved by",
        r"rated \d(?:\.\d)? (?:stars?|out of)",
        r"thousands of (?:reviews|customers)",
    ],
    "Authority Manipulation": [
        r"doctors?[- ]recommended",   # guideline
        r"scientifically proven",     # guideline
        r"experts?[- ]approved",      # guideline
        r"backed by (?:researchers|science|experts)",  # guideline
        r"clinically (?:proven|tested)",
        r"as seen on(?: tv)?",
        r"lab[- ]tested",
        r"certified",
        r"endorsed by",
        r"specialists? (?:recommend|agree)",
        r"science[- ]backed",
        r"patented",
    ],
    "Exaggerated Claims": [
        r"lose \d+ pounds? (?:instantly|overnight|in \w+)",  # guideline
        r"guaranteed(?: success| results)?",  # guideline
        r"become rich overnight",             # guideline
        r"overnight",
        r"instantly",
        r"miracle",
        r"cures? (?:in \w+|everything)?",
        r"reverses? \w+(?: \w+)? in \d+ \w+",
        r"100%",
        r"never again",
        r"revolutionary",
        r"breakthrough",
        r"eliminates?",
        r"permanently",
        r"unbelievable",
        r"transform your \w+",
    ],
}

# Compiled once at import. \b guards stop "ban" matching inside "banner" and
# "certified" inside "uncertified".
_COMPILED = {
    label: [
        re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)
        for pattern in patterns
    ]
    for label, patterns in TRIGGER_PATTERNS.items()
}


def display_name(label: str) -> str:
    return DISPLAY_NAMES.get(label, label)


def find_phrases(text: str) -> dict[str, list[dict]]:
    """Locate every trigger phrase in `text`, grouped by tactic.

    Returns ``{label: [{"text": matched, "start": i, "end": j}, ...]}`` with the
    match's original casing preserved so the panel can quote the ad verbatim.
    Overlapping matches for the same tactic are dropped, longest first, so
    "only 7 bottles left" is reported once rather than also as a shorter hit.
    """
    found: dict[str, list[dict]] = {}

    for label, patterns in _COMPILED.items():
        spans: list[dict] = []

        for pattern in patterns:
            for match in pattern.finditer(text):
                spans.append(
                    {
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        if not spans:
            continue

        # Longest first, then keep a match only if it doesn't sit inside one
        # already kept.
        spans.sort(key=lambda s: (s["start"] - s["end"], s["start"]))

        kept: list[dict] = []

        for span in spans:
            overlaps = any(
                span["start"] < other["end"] and other["start"] < span["end"]
                for other in kept
            )

            if not overlaps:
                kept.append(span)

        kept.sort(key=lambda s: s["start"])
        found[label] = kept

    return found


def explain(label: str, phrases: list[dict]) -> str:
    """Plain-language line for one tactic, quoting a trigger phrase if present."""
    if phrases:
        template = PHRASE_TEMPLATES.get(label, '"{phrase}" is a pressure tactic.')
        return template.format(phrase=phrases[0]["text"])

    return GENERIC_EXPLANATIONS.get(label, "This is a pressure tactic.")


def build_tactics(prediction: dict, text: str) -> list[dict]:
    """Merge the model's prediction with phrase evidence into panel rows.

    The classifier is single-label, so it alone cannot fill the wireframe's list
    of five tactics. Combining the two signals does, without either pretending
    the model is multi-label or inventing findings: a row appears because the
    model chose that class, because a guideline phrase is literally present, or
    both -- and `sources` says which.
    """
    phrases_by_label = find_phrases(text)
    predicted = prediction["label"]

    confidence_by_label = {
        entry["label"]: entry["confidence"]
        for entry in prediction["distribution"]
    }

    labels = set(phrases_by_label) | {predicted}
    rows = []

    for label in labels:
        phrases = phrases_by_label.get(label, [])

        sources = []
        if label == predicted:
            sources.append("model")
        if phrases:
            sources.append("phrase")

        confidence = confidence_by_label.get(label, 0.0)

        # Weak model guess with nothing in the text to back it up.
        uncertain = (
            not phrases
            and sources == ["model"]
            and confidence < LOW_CONFIDENCE
        )

        rows.append(
            {
                "label": label,
                "display": display_name(label),
                "confidence": confidence,
                "sources": sources,
                "phrases": phrases,
                "explanation": explain(label, phrases),
                "uncertain": uncertain,
            }
        )

    # The model's own pick leads the panel; the rest follow by how much
    # evidence backs them, then by model confidence.
    rows.sort(
        key=lambda row: (
            "model" not in row["sources"],
            -len(row["phrases"]),
            -row["confidence"],
        )
    )

    return rows
