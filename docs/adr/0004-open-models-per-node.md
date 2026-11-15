# 0004 Open-weight models per node, with fallback chains

**Context.** The assignment says open-weight and local models first. The laptop GPU has 6 GB, and the free hosted tiers have tight tokens-per-minute limits.

**Decision.** `agent/config.yaml` maps every node to a tier (small / strong / critic / judge), and each tier to an ordered chain of models.
- Profile `open`: small tier `qwen3:4b` on local Ollama, falling back to hosted `gpt-oss-20b`; strong tier `gpt-oss-120b` on Groq.
- Profile `open_hosted` (for the VM without a GPU): the small tier is hosted too.

`agent/llm.py` asks for structured output with a JSON schema, then plain JSON mode, then the next model in the chain. The GigSim client and the eval judge use Qwen, a different family from the Writer, so neither grades its own style.

**Alternatives.** One large hosted model everywhere: simpler, but it burns the free tier on cheap tasks like intent detection. Paid APIs: allowed if costed, but not needed.

**Consequences.** No model name appears in code, and switching profile is one env var. Small models need strict schemas and validators. The fallback chain hides provider 429s but can change which model answered, so traces record the model per span.
