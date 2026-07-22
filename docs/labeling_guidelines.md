# Persuasive Ad Labeling Guidelines

## Purpose

The purpose of these guidelines is to standardize how persuasive advertising tactics are labeled throughout the dataset. Consistent labeling will improve annotation quality and help train and evaluate the NLP classification model more effectively.


# Label Definitions

## 1. Urgency

Definition:
Language that pressures the user to act immediately or within a short time frame.

Examples:

* “Act now”
* “Limited time offer”
* “Today only”
* “Before midnight”
* "Sale ends tonight"

Annotation Rule:
Apply the Urgency label when the advertisement encourages users to act quickly due to a time-sensitive condition.


## 2. Scarcity

Definition:
Language suggesting limited quantity, availability, or access to a product, service, or opportunity.

Examples:

* “Only 3 left”
* “Exclusive access”
* “Limited spots available”
* "While supplies last"

Annotation Rule:
Apply the Scarcity label when reduced availability is used to increase desirability or pressure the user into acting.


## 3. FOMO (Fear of Missing Out)

Definition:
Language implying the user may miss an opportunity, trend, experience, or social benefit if they do not engage.

Examples:

* “Everyone is switching”
* “Don’t miss out”
* “Join thousands already using this”
* "Be the first to try it"

Annotation Rule:
Apply the FOMO label when the advertisement uses exclusion, popularity, or social comparison to persuade users.


## 4. Fear Appeal

Definition:
Language that uses fear, anxiety, risk, or potential negative outcomes to influence behavior.

Examples:

* “Protect your family”
* “Your health may be at risk”
* “Avoid financial disaster"
* "Stop harmful bacteria"

Annotation Rule:
Apply the Fear Appeal label when fear or concern is used as the primary persuasive tactic.


## 5. Social Proof

Definition:
Language suggesting popularity or approval by a large group of people.

Examples:

* “Trusted by millions”
* “Top rated product”
* “Best seller”

Annotation Rule:
Label as social proof if popularity is used to increase trust.


## 6. Authority

Definition:
Language using experts, professionals, credentials, or institutions to build credibility.

Examples:

* “Doctor recommended”
* “Scientifically proven”
* “Expert approved”
* "Backed by researchers"

Annotation Rule:
Apply the Authority label when expertise, credentials, or institutional trust is used as persuasion.


## 7. Exaggerated Claim

Definition:
Language making extreme, unrealistic, or overly absolute promises or outcomes.

Examples:

* “Lose 20 pounds instantly”
* “Guaranteed success”
* “Become rich overnight”

Annotation Rule:
Apply the Exaggerated Claim label when the advertisement uses unrealistic or highly inflated claims.


## 8. Neutral

Definition:
Advertisements that do not contain a clear persuasive tactic from the categories above.

Examples:

* "New product available now”
* "Visit our website for more information"

Annotation Rule:
Apply the Neutral label only when no strong persuasive strategy is clearly present.


# General Annotation Rules

* Ads may contain multiple labels.
* Label the primary persuasion tactic first.
* Focus only on the advertisement content itself.
* Do not classify ads as scams or illegal.
* Ignore platform interface text or comments.


# Edge Cases

## Humor/Satire

If persuasion is clearly intended as a joke, annotate cautiously.

## Influencer Ads

Focus on persuasive wording rather than influencer popularity alone.

## Legitimate Promotions

Normal discounts can still contain urgency or scarcity tactics.



# Intended Use

These labels are intended for educational NLP analysis of persuasive advertising language and not legal classification.
