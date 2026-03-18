# Functional Proof-of-Concept

## What format should the prototype be?

For this project, the best prototype format is **a working web-based demo backed by seeded scenario data**.

That means your prototype is not a design mockup, static slide, or Figma-only concept. It should be:

- a runnable system
- able to show the core workflow end to end
- realistic enough that a reviewer can see the value of the idea
- intentionally limited to the most important features rather than a full product

For this project, the correct prototype format is:

1. A live frontend where different users can log in
2. A backend that processes care events and generates outputs
3. A small set of curated demo scenarios that clearly prove the core idea
4. A short scripted walkthrough that explains what is happening

## What is the core idea that must be proven?

The prototype does **not** need to prove a complete healthcare platform.

It only needs to prove this core concept:

**A multi-agent eldercare coordination system can ingest care-related events, generate role-specific proposals, and pass them through mandatory safety review before anything is delivered.**

If the demo successfully shows that workflow, then it is already a valid proof-of-concept.

## What already counts as the working prototype in this repo?

This repository already contains a strong proof-of-concept because it demonstrates:

- multimodal event ingestion
- a shared patient state
- specialized agent outputs
- mandatory centralized risk review
- escalation and human-review paths
- role-based UI for patient, caregiver, and reviewer users

So the main task is not to invent a different prototype format. The main task is to **package the current system as a prototype deliverable**.

## Recommended prototype deliverable

Your submission can be framed as:

**Functional Proof-of-Concept: Eldercare Multi-Agent Coordination Dashboard**

The prototype should include these 4 parts:

1. **Live system**
   - React frontend
   - FastAPI backend
   - PostgreSQL demo data

2. **Three high-value demo scenarios**
   - missed medication follow-up
   - caregiver support task generation
   - escalation / human-review safety handling

3. **Short presenter walkthrough**
   - what event happened
   - what agent response was generated
   - how safety review changed or blocked the output
   - what different roles can see

4. **Presentation support material**
   - slide deck
   - this prototype definition
   - optional short backup video recording

## Minimum viable prototype scope

If you need to define the prototype in one sentence, use this:

**A role-based web application that demonstrates how eldercare events can be turned into reviewed, safe, audience-specific care actions through a multi-agent coordination workflow.**

That is specific, credible, and narrow enough for an innovation challenge.

## Demo scenarios to show

These are the best scenarios to include because they show both usefulness and safety.

### Scenario 1: Missed medication pattern

What it proves:

- the system can ingest a behavioral event
- the system updates patient state
- the system generates a follow-up proposal
- the proposal is reviewed before delivery

Suggested message to the audience:

“This shows that the system is not just storing data. It turns a care signal into a reviewed next step.”

### Scenario 2: Caregiver task card with consent-aware sharing

What it proves:

- the system can create caregiver-facing support tasks
- outputs differ by recipient role
- caregiver access is bounded by patient-controlled sharing preferences

Suggested message to the audience:

“This demonstrates that coordination is useful, but still privacy-aware and role-aware.”

### Scenario 3: Escalation or human-review path

What it proves:

- unsafe or urgent content is not automatically released
- the system can escalate or route to manual review
- governance is part of the workflow, not an afterthought

Suggested message to the audience:

“The real value is not only generation. It is controlled, auditable decision-making.”

## What to actually show during the demo

A good prototype demo for this project is 3 to 5 minutes.

Use this sequence:

1. Show the login screen and explain that the system has different human roles.
2. Log in as a reviewer and show:
   - proposal queue
   - escalation visibility
   - human-review queue
   - safety metrics
3. Switch to a patient or caregiver account and show:
   - role-specific interface
   - filtered visibility
   - caregiver sharing controls or caregiver task cards
4. Explain one scenario from event to reviewed output.
5. End by explaining that the prototype proves safe coordination, not full clinical deployment.

## What reviewers usually expect from a proof-of-concept

A reviewer is usually asking:

- Does it run?
- Does it demonstrate the central idea clearly?
- Is there a believable user flow?
- Is the system solving a real coordination problem?
- Is the scope realistic for a prototype?

They are usually **not** expecting:

- production-grade deployment
- complete integrations with hospitals
- regulatory completeness
- polished commercial UX in every corner

## How to describe the prototype in your report or presentation

You can use this wording directly:

> Our working prototype is a functional web-based proof-of-concept that demonstrates how multimodal eldercare events can be processed by specialized AI agents, reviewed through a centralized safety layer, and delivered as role-appropriate outputs to patients, caregivers, and reviewers.

Shorter version:

> The prototype is a live dashboard that proves the end-to-end multi-agent coordination workflow with safety review and role-based visibility.

## Recommended evidence package

When presenting or submitting, include:

- the live demo
- 3 to 5 slides explaining the concept
- one architecture slide
- one workflow slide
- one screenshot per key role if live demo fails
- a short backup recording if possible

## Final recommendation

For this project, your prototype format should be:

**a live, scenario-driven dashboard demo**

That is the strongest format because it directly proves:

- the system runs
- the workflow is functional
- the multi-agent logic is meaningful
- the safety layer changes outcomes
- different stakeholders receive different outputs

This is already much stronger than a static mockup.
