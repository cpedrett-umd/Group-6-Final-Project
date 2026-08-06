---
team: Persuasive Ad Explainer
week: 6
date: 2026-07-08
members:
  - name: Ciara Cameron
    github: Ciaracam
    hat: Data&Eval
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: Shashank Ashoka
    github: shashk09-coder
    hat: Architecture | OCR | Agents
  - name: Jonathan Kim
    github: jonathanjkim5108
    hat: Product | Engineering | Data&Eval
    
north_star:
  metric: <e.g. task success rate>
  value: <this week>
  previous: <last week>
---

## Shipped this week
- Drafted an architecture of the tranformer workflow using PyTorch. This includes a data loader, tokenizer, and the model. The data loader is responsible for taking a labeled dataset and performing text cleaning, word tokenizing, and building vocab. The model will use multi head self attention with an encoder block and classifier. We also plan to use supporting scripts for label parsing and classifying a single ad from a model checkpoint.
- Collected approximately 50 Instagram advertisements and used the ad_asr_pipeline_fixed.ipynb pipeline to download their audio and convert the spoken content into transcripts using faster-whisper. These transcripts were prepared as inputs for testing how well text embeddings capture the semantic and persuasive content relevant to our use case.

## User / validation learning
- Today, users usually deal with suspicious or persuasive ads in a manual and inconsistent way. Some users ignore the ad if it feels suspicious, while others click through and try to judge the product after seeing the landing page. They may Google the product or company, check Amazon reviews, search Reddit threads, read comments under the ad, ask friends or family members, or report the ad to the platform.

## Metrics snapshot
- No metrics to report yet.

## Challenges / blockers
- Our initial dataset did not accurately reflect all of our persuasion labels. The dataset was heavily skewed toward urgency and scarcity language, while categories such as FOMO, social proof, authority, and fear appeal were less represented. We also realized that cleaning and labeling the dataset required more manual review than expected due to noisy OCR text, near-duplicate ads, and inconsistent advertisement quality.
- Audio speech recognition for video ads proved to be too inconsistent for collecting data, therefore we narrowed scope.

## Next week's goal
- Refine model architecure
- Finalize preprocessing and labeling dataset
- Create pipeline for processing input into the model

## Individual contributions
- Ciara (Data&Eval) : labeled an initial subset of ads, and developed a data-cleaning script to reduce noisy OCR text and near-duplicate entries.
- Chris (Engineering | Data&Eval): Explored ASR pipeline for audio to text transcription for increasing modalities, drafted initial nlp model architecture in PyTorch. We are exploring a tokenizer to process textual data and a multi head self attention transformer to handle the classification task. See modeling for more info.
- Jonathan (Data&Eval) : Developed data collection pipeline and associated script to obtain raw OCR and HuggingFace text, developed intermediate data labeling scripts

## Lean canvas changes (if any)
- Shifted away from OCR and ASR and decided to focus on purely textual ad data.
