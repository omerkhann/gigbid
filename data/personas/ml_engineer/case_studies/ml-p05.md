<!-- project_id: ml-p05 | synthetic -->
# Fine‑tuned Sentiment Model for Urdu‑English Product Reviews

## Context
Hamza Siddiqui was engaged by an e‑commerce client that receives a high volume of product reviews written in a code‑mixed Urdu‑English style. The existing off‑the‑shelf sentiment classifier, trained on monolingual English data, struggled with the linguistic nuances of the mixed language, delivering an F1 score of only 0.71. The client needed a more accurate solution to automatically tag reviews as positive, negative, or neutral, enabling better product ranking, personalized recommendations, and faster moderation.

## What I built
Leveraging expertise in Natural Language Processing and Deep Learning, Hamza designed a custom pipeline in PyTorch. The workflow included:
1. **Data collection & preprocessing** – extracted 12 k code‑mixed reviews, applied language‑identification tags, and performed tokenization using a multilingual tokenizer that respects both Urdu script and Romanized English.
2. **Model selection** – started from a multilingual BERT base model, which already captures cross‑lingual representations, and added a classification head.
3. **Fine‑tuning strategy** – employed a two‑stage training regime: first a general fine‑tune on the entire dataset, then a targeted curriculum that emphasized hard‑to‑classify samples (e.g., reviews with heavy code‑mixing or slang). Hyper‑parameters such as learning rate, batch size, and dropout were iteratively tuned.
4. **Evaluation & deployment** – used stratified k‑fold cross‑validation to ensure robust performance, and packaged the model into a Docker container for seamless integration with the client’s review ingestion pipeline.

## Results
The fine‑tuned model achieved an F1 score of **0.88** on the held‑out code‑mixed test set, a substantial improvement over the baseline 0.71. This 17‑point gain translated into:
- **30% reduction** in manual review moderation effort.
- More reliable sentiment signals feeding into the recommendation engine, boosting click‑through rates by an estimated 4%.
- A scalable production‑ready solution that can be retrained quarterly as new review data arrives.

The project demonstrated how targeted model tuning and multilingual NLP techniques can unlock value from linguistically complex data in e‑commerce environments.
