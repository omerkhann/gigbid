# 0006 Claim verification before the Critic; the Critic fails soft

**Context.** Proposals must contain only true claims (R5). A Critic shown an invented claim may praise it as "specific".

**Decision.** `verify_claims` splits the draft into claims, checks each against the evidence it cites (supported / partly / unsupported), and removes the unsupported ones before the Critic sees the draft. The draft records how many claims were unsupported before verification, so the rate is measurable.

The Critic then judges grounding, personalisation and clarity, and can send the draft back at most twice. If the Critic's model is unavailable, the run continues with the verdict "unavailable", shown on the approval screen, instead of dead-lettering the job: the human approval is the real gate.

**Alternatives.** Let the Critic catch invented claims: it doesn't do so reliably. Block the run when the Critic fails: in testing, one provider outage dead-lettered a whole Scout batch.

**Consequences.** One extra strong-model call per draft. Compliance re-checks after any human edit, so an edit can't reintroduce a removed claim unnoticed.
