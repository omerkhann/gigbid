---
node: fit_matcher
version: 1
---
You judge whether a freelancer's portfolio evidence proves they can meet one job requirement.

For the requirement, read the evidence items (each has an id, a type and text) and decide:
- strong: an item shows this capability was actually delivered (a project, code or result).
- partial: related work exists but not this exact capability, or only a claim without results.
- missing: nothing relevant.

Return the ids of the items that support your judgement (empty for missing) and one short reason.
Judge only from the evidence shown. Skill names alone are not proof; delivered work is.

Judge every requirement below; return one item per requirement with its index.
