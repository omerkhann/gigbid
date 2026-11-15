---
node: verify_claims
version: 1
---
You check a proposal draft against the evidence it cites.

Split the cover letter into atomic claims about the freelancer (skills, projects, results, years,
employers, tools). For each claim, look at the cited evidence ids and decide:
- supported: the evidence says this.
- partly_supported: the evidence supports part of it, or a weaker version.
- unsupported: no cited evidence says this (including claims with no citation).

Statements about the client's job or about what the freelancer *would* do are not claims; skip them.

Then return revised_cover_letter: the same letter with unsupported claims removed and partly
supported ones softened to exactly what the evidence shows. Keep the [evidence_id] citations.
Change nothing else.
