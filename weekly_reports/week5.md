---
team: AdInsight — Persuasion-Aware Ad Explainer
week: 4
date: 6-24-2026
members:
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: Shashank Ashoka
    github: shashk09-coder 
    hat: Architecture | OCR | Agents
  - name: Ciara Cameron
    github: Ciaracam
    hat: Data Quality | Annotation | Evaluation
  - name: Jonathan Kim
    github: jonathanjkim5108 
    hat: Product | Engineering | Data&Eval
    
north_star:
  metric: Task success rate
  value: 1.75/2
  previous: 1/1
---


## Shipped this week
- <what is now merged or deployed> 

We started developing the data collection pipeline for text and audio based ads. Text based ads were collected using the regular expressions library and speech from video based ads were collected using faster-whisper and WASAPI.

## User / validation learning

Today, users usually deal with suspicious or persuasive ads in a manual and
inconsistent way. Some users ignore the ad if it feels suspicious, while others click
through and try to judge the product after seeing the landing page. They may Google
the product or company, check Amazon reviews, search Reddit threads, read comments
under the ad, ask friends or family members, or report the ad to the platform.

## Metrics snapshot

No metrics to report yet

## Challenges / blockers

Audio transcription with api's (faster-whisper) use a capture rate that can cut off words. This leads to disconnected audio chuncks that lose meaning.

## Next week's goal

Fix audio transcription methodology.
Finish data collection and merge different modalities into 1 dataset of ad text data.

## Individual contributions
- Chris (Engineering): I wrote a script using faster-whisper and WASAPI to capture system audio. This will be used to collect ads from various social media sources. https://github.com/cpedrett-umd/Group-6-Final-Project/pull/1

## Lean canvas changes (if any)
- <what shifted this week: user, problem, value proposition, cost, or risk>

No objective shifts this week.
