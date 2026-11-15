<!-- project_id: ml-p14 | synthetic -->
# Speech-to-Text Pipeline for Call‑Centre QA

## Context
A large business‑process‑outsourcing (BPO) firm needed to dramatically improve the quality‑assurance (QA) process for its inbound call centre. Previously, only about 2 % of the daily 5,000 calls were manually reviewed, which left most interactions unchecked and made it difficult to spot compliance issues or training opportunities. The client wanted an automated solution that could reliably transcribe every call, make the text searchable, and integrate with their existing QA workflow, all while handling the high volume of audio data generated each day.

## What I built
I designed and delivered an end‑to‑end speech‑to‑text system that runs continuously in the cloud. The solution begins by automatically pulling newly recorded audio files from the storage area used by the call centre. Those files are then pre‑processed: background noise is reduced, audio is normalised, and the data is split into manageable chunks. A deep‑learning model, trained on a large corpus of conversational speech, converts each chunk into text with high accuracy. The transcribed text is enriched with timestamps and speaker labels, then stored in a searchable database that the QA team can query.

To keep the pipeline robust and scalable, I implemented a series of automated steps that move the data from one stage to the next, handling retries and error logging without human intervention. The entire workflow is orchestrated using cloud‑based compute and storage resources, ensuring that the system can process the full daily volume of 5,000 calls within minutes of the recordings being available.

## Results
The automated pipeline now transcribes every call, raising QA coverage from the original 2 % to 100 % of daily interactions. This full‑coverage approach has uncovered previously hidden compliance breaches, reduced average handling time for QA reviewers by 70 %, and enabled data‑driven coaching for agents. The client reports a measurable increase in customer satisfaction scores and a clear return on investment within the first quarter of deployment.
