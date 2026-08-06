---
team: AdInsight
week: 8 - Week 7 lacks report due to midsemester presentation
date: <2026-07-22>
members:
  - name: Ciara Cameron
    github: Ciaracam
    hat: Data&Eval
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: Jonathan Kim
    github: jonathanjkim5108
    hat: Product | Engineering | Data&Eval
north_star:
  metric: task success rate
  value: 100%
  previous: 100%
---

## Shipped this week
- Planned tasks following processed dataset, including the tokenizer and baseline NLP model.
- Consolidated multiple advertising datasets containing real, synthetic, and OCR-extracted advertisement text.
- Applied preprocessing steps including text cleaning, duplicate removal, quality filtering, and heuristic labeling.
- Defined the next modeling tasks, including finalizing the model architecture, creating the tokenizer, and preparing the labeled dataset for baseline training

## User / validation learning
- By reviewing comments across several social media platforms, we noticed that some users had already learned to recognize common persuasive phrases used in advertisements. For example, one Instagram user commented, “As soon as I hear or see ‘limited stock,’ I just scroll away.”

- We contacted several users through advertisement comment sections and asked how they recognized when an ad was being persuasive or potentially misleading. Their responses were consistent: certain repeated phrases immediately raised suspicion. Examples included “Stop before you go,” “I know you’re facing this problem—here’s a solution that makes it disappear,” “$100 giveaway,” “limited stock,” and “bonus offer.”
- Based on these findings, we curated a dataset containing advertisements and labeled persuasive language patterns. This dataset is fed into our model so it can learn to identify similar phrases, classify the persuasion tactics being used, and explain how an advertisement may be attempting to influence the user.

## Metrics snapshot
- 7,768 advertisement texts in the unified dataset
- 2 active input modalities: text and image
- 8 annotation labels: seven persuasion tactics and one neutral class

## Challenges / blockers
- None this week

## Next week's goal
- Define model architecure
- Create tokenizer and tokenize the labeled dataset
- Calculate Baseline classifier F1 score

## Individual contributions
- Ciara (Data&Eval) : Worked on midsemester presentation, expanded the advertisement dataset by manually collecting additional ads, and improved representation across persuasion categories.
- Chris (Engineering | Data&Eval): Worked on midsemester presentation, drafted end product wireframe, and drafted the tokenizer for NLP model ingestion.
- Jonathan (Data&Eval) : Worked on midsemester presentation, data preprocessing techniques, and baseline NLP model creation
- Shashank (App | Browser Extension): Worked on the midsemester presentation, prototyped a simple app interface and browser extension where users can upload advertisement text or screenshots, and began developing the review-insight layer to collect product experiences and reviews from sources like amazon , quora or reddit.

## Lean canvas changes (if any)
- Shifted away from ASR/audio modality and decided to focus on purely textual ad data.
