"""Every number in README.md's results block comes from evals/results/ (assignment CI rule): the block
must equal what evals/make_tables.py renders from the committed result files."""

from __future__ import annotations

from evals.make_tables import ROOT, readme_block, render


def test_readme_results_block_is_generated_from_results_files():
    block = readme_block((ROOT / "README.md").read_text(encoding="utf-8"))
    assert block is not None, "README.md has no generated results block"
    assert block == render(), "README results are stale: run python -m evals.make_tables"
