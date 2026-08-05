---
team: AdInsight — Persuasion-Aware Ad Explainer
week: 5
date: 7-1-2026
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
- <what is now merged or deployed> We started developing the data collection pipeline for text and audio based ads. Text based ads were collected using the regular expressions library and speech from video based ads were collected using faster-whisper and WASAPI.
- Began the data collection pipeline covering both text-based and video-based ads.
- Text ads: extraction using regular expressions over collected ad copy.

## User / validation learning

We spoke informally with friends, family members, and several older relatives about what they do when an ad catches their attention. Everyone had a strategy. The strategies split fairly cleanly by age.

Younger participants verify digitally and alone: search the company or product, check Amazon ratings, look for Reddit threads, and increasingly paste the ad text or a screenshot into an LLM and ask whether it looks legitimate.

Middle-aged and older participants verify socially and by phone: ask friends or family what they think, call the company directly, or search YouTube for videos about the product. Several described buying the product first and forming a judgement afterwards — verification happening after the money was already spent.

External data supports treating the older group as the higher-stakes case, though not in the way we assumed. [The FTC reports](https://www.aarp.org/money/scams-fraud/fbi-ftc-report-2025-losses/) that adults 60 and over are actually less likely than adults 18–59 to report losing money to fraud  but when they do lose, they lose far more. Reported losses among adults 60 and over rose roughly fourfold between 2020 and 2024, from about $600 million to $2.4 billion, driven largely by losses over $100,000, and the median loss for the 60+ group was the highest of any age group. Social media is the most common contact method for investment scams across all ages. So the problem is not that older adults fall for more ads  it is that the consequences are heavier and the verification routes available to them are slower.

The evidence users want already exists publicly. Both groups are performing the same underlying task  find out what other people experienced with this product and both are doing it manually, slowly, and after the ad has already done its persuasive work. Neither group has a single place to drop an ad and get an answer.

## Metrics snapshot

<table>
  <tr>
    <td width="34%" valign="top">
      <img
        src="https://github.com/user-attachments/assets/77dd3c42-1ea1-4ab1-974a-329378b418cb"
        alt="Metrics overview"
        width="100%"
      />
    </td>
    <td width="66%" valign="top">
      <img
        src="https://github.com/user-attachments/assets/c9e506ca-d79d-4474-a584-ce7952255cbb"
        alt="Metrics details"
        width="100%"
      />
    </td>
  </tr>
</table>



## Challenges / blockers

- Audio transcription with api's (faster-whisper) use a capture rate that can cut off words. This leads to disconnected audio chuncks that lose meaning.
- The capture rate used by faster-whisper with WASAPI can cut off words mid-utterance, producing disconnected chunks that lose their meaning. Since persuasive phrasing depends on intact phrases ("only three left", "doctors are warning"), fragmented transcripts are not usable as classifier input in their current form.
- Audio transcription blocker — measured

  -We hand-transcribed a video ad (593 words) and compared it against the
   faster-whisper + WASAPI capture pipeline (model: base).

  -Word accuracy was 95.4% (WER 4.6%), which on its own looks acceptable.
The breakdown does not: deletions account for 0% of all errors, the
signature of words clipped at capture-window boundaries rather than misheard.

  -More importantly, only 3 of 3 persuasion trigger phrases
present in the reference survived transcription. Lost: none.

  -Because the classifier and the trigger-phrase matcher both depend on this
vocabulary, a headline accuracy figure materially overstates how usable the audio
path is. The errors are not randomly distributed  they concentrate in exactly
the signal the system needs.

## Next week's goal

Fix audio transcription methodology.
Finish data collection and merge different modalities into 1 dataset of ad text data.

## Individual contributions
- Chris (Engineering): I wrote a script using faster-whisper and WASAPI to capture system audio. This will be used to collect ads from various social media sources. https://github.com/cpedrett-umd/Group-6-Final-Project/pull/1
- Shashank (Evaluation): I evaluated Chris’s faster-whisper and WASAPI transcription pipeline. I tested videos from YouTube and Instagram, then performed a detailed evaluation on one Instagram advertisement by comparing the generated transcript with a manually corrected reference. The model achieved 95.4% word accuracy, a 4.6% word error rate, and preserved all identified persuasion-related phrases.

## Lean canvas changes (if any)
- <what shifted this week: user, problem, value proposition, cost, or risk>

No objective shifts this week.
