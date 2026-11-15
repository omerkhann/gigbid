<!-- project_id: ml-p02 | synthetic -->
# RAG Assistant for Internal Policy Documents

## Context
The client, a large insurance provider, maintained a growing library of over 4,000 policy PDFs. These documents contained critical compliance and underwriting guidelines that employees needed to reference quickly. Existing search tools were slow and returned results without context, forcing staff to manually sift through pages. The goal was to create an intelligent assistant that could understand natural language queries, retrieve relevant sections from the PDFs, and provide concise answers with clear citations, all while handling a high volume of simultaneous requests.

## What I built
I designed a Retrieval‑Augmented Generation (RAG) system that combined semantic search with a large language model to produce accurate, citation‑rich responses. First, the PDFs were converted into clean text and split into manageable chunks. Each chunk was embedded into a dense vector space using a pretrained language model, enabling similarity search based on the meaning of the query rather than simple keyword matching.

To keep the service responsive, I implemented an asynchronous task queue that handled heavy background work such as embedding updates and batch indexing. This allowed the front‑end API to remain fast for user queries while the heavy lifting happened behind the scenes. The assistant was exposed through a RESTful API that could be called from the company’s internal chat platform. When a user asked a question, the system retrieved the top‑matching document fragments, fed them together with the query to the language model, and generated an answer that included direct references to the source PDFs.

## Results
The assistant was evaluated on a 200‑question test set representing typical policy‑related inquiries. It answered 85 % of the questions correctly, and each answer included a citation pointing back to the exact PDF page, giving users confidence in the information. The solution reduced the average time to locate policy details from several minutes to under ten seconds, dramatically improving productivity for compliance and underwriting teams. The client reported higher satisfaction among staff and a measurable decrease in support tickets related to policy lookup.
