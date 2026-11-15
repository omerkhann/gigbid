# 0007 Rules, not an LLM, for the bid decision and the risk score

**Context.** Skip/watch/bid and "is this a scam" must be explainable in one line and stable between runs.

**Decision.** `decide` is pure rules over the three reports (risk score, fit score, budget against the user's floor, Connects reserve), with thresholds in config.

The Risk Assessor computes its score from sentence-level rules on the job text and client history. The rules cover off-platform payment, upfront fees, unpaid trials, an unverified client with no spend, and planted instructions. A small LLM only extracts signals the rules can't see.

Every decision records its reason, for example "skipped: risk 0.82 > 0.70, flags: off_platform_payment".

**Alternatives.** Ask an LLM "should I bid?": flexible, but unstable and hard to debug. The viva asks to walk through why a job was wrongly skipped.

**Consequences.** Thresholds need tuning on the dev set (never the test set), and each new scam pattern needs a rule. The decision eval (`evals/runners/decision_eval.py`) measures what that rigidity costs.
