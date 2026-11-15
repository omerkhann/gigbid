<!-- project_id: ml-p18 | synthetic -->
# Named-entity extraction from shipping invoices

## Context
In 2025, a logistics company faced a costly bottleneck: every shipping invoice had to be manually keyed into their system. The process was slow, error‑prone, and required a sizable staff effort. The client wanted an automated solution that could reliably pull out critical information—such as shipper, consignee, dates, and item descriptions—from a wide variety of invoice formats. The goal was to dramatically reduce manual data entry while maintaining high accuracy, enabling the operations team to focus on higher‑value tasks.

## What I built
I designed an end‑to‑end pipeline that ingested scanned or digital invoices, applied optical character recognition to obtain raw text, and then passed that text through a custom‑trained natural‑language‑processing model specialized in named‑entity extraction. The model was fine‑tuned on a curated set of annotated invoices to recognize the specific entities relevant to the logistics workflow. To ensure the solution could handle the volume of daily invoices, I wrapped the model in a lightweight web service that accepted text payloads and returned structured JSON with the extracted fields. The service was containerized and deployed behind a load balancer, allowing horizontal scaling as demand grew. I also implemented a post‑processing step that applied rule‑based validation (e.g., date formats, known company names) to further boost precision.

## Results
The production system achieved an extraction F1 score of 0.93, surpassing the client’s internal benchmark for acceptable accuracy. Because the automated extraction was so reliable, the team reduced manual keying effort by roughly 70 %, translating into significant time savings and a measurable drop in data‑entry errors. The solution now runs continuously, handling hundreds of invoices each day with minimal latency, and the logistics company reports smoother operations and faster invoice processing cycles.
