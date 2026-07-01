---
team: To Be Determined Next Meeting
week: 5
date: 7-1-2026
members:
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: <name>
    github: <handle>
    hat:
  - name: <name>
    github: <handle>
    hat:
north_star:
  metric: <e.g. task success rate>
  value: <this week>
  previous: <last week>
---

## Shipped this week
- <what is now merged or deployed> 

We started developing the data collection pipeline for text and audio based ads. Text based ads were collected using the regular expressions library and speech from video based ads were collected using faster-whisper and WASAPI.

## User / validation learning
- <what you learned + how you got it: an interview, usage data, a task test>

Today, users usually deal with suspicious or persuasive ads in a manual and
inconsistent way. Some users ignore the ad if it feels suspicious, while others click
through and try to judge the product after seeing the landing page. They may Google
the product or company, check Amazon reviews, search Reddit threads, read comments
under the ad, ask friends or family members, or report the ad to the platform.

## Metrics snapshot
- <metric>:

No metrics to report yet

## Challenges / blockers
- <what is hard, and what help you need>

Audio transcription with api's (faster-whisper) use a capture rate that can cut off words. This leads to disconnected audio chuncks that lose meaning.

## Next week's goal
- <the one thing>

Fix audio transcription methodology.
Finish data collection and merge different modalities into 1 dataset of ad text data.

## Individual contributions
- <name> (<hat>): <what they did>  (evidence: PR #34, #12)
- Chris (Engineering): I wrote a script using faster-whisper and WASAPI to capture system audio. This will be used to collect ads from various social media sources. https://github.com/cpedrett-umd/Group-6-Final-Project/pull/1

## Lean canvas changes (if any)
- <what shifted this week: user, problem, value proposition, cost, or risk>

No objective shifts this week.
