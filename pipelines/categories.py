"""Map a free-text job/contract title onto GigBid's four job categories.

The jobs dataset has categories; the contracts dataset only has titles. Pricing stats
per category need contracts mapped onto the same four categories, so we use keyword
rules: transparent, fast on 1.3M titles, and easy to explain or fix in the viva.
Anything that matches no rule is `other` (writing, translation, video, admin, ...).
"""

from __future__ import annotations

import re

CATEGORIES = ("development", "data_science", "marketing", "3d_design")

# Order matters only for ties: more specific categories come first.
_KEYWORDS: dict[str, list[str]] = {
    "3d_design": [
        r"3d", r"blender", r"render(?:ing|s)?", r"cad", r"autocad", r"sketchup", r"revit",
        r"3ds ?max", r"maya", r"zbrush", r"cinema ?4d", r"c4d", r"solidworks", r"fusion ?360",
        r"stl", r"archviz", r"architectural visuali[sz]ation", r"unreal", r"substance painter",
    ],
    "data_science": [
        r"data analy(?:st|sis|tics)", r"data scien(?:ce|tist)", r"machine learning", r"ml",
        r"deep learning", r"nlp", r"computer vision", r"llms?", r"ai model", r"data engineer(?:ing)?",
        r"power ?bi", r"tableau", r"looker", r"dashboards?", r"sql", r"postgres(?:ql)?",
        r"statistic(?:s|al)", r"forecast(?:ing)?", r"regression", r"pandas", r"etl",
        r"data visuali[sz]ation", r"analytics", r"bigquery", r"snowflake", r"pytorch",
        r"tensorflow", r"spss", r"r programming", r"jupyter", r"predictive",
        r"segmentation", r"object detection", r"classification", r"classifier", r"neural",
        r"openai", r"gpt", r"rag", r"fine[- ]?tun(?:e|ing)", r"data model(?:l?ing)?",
    ],
    "marketing": [
        r"marketing", r"seo", r"sem", r"ppc", r"social media", r"smm", r"facebook ads?",
        r"google ads?", r"meta ads?", r"tiktok ads?", r"ads manager", r"media buyer",
        r"lead generation", r"email campaign", r"klaviyo", r"mailchimp", r"influencer",
        r"growth hack(?:er|ing)?", r"campaigns?", r"advertis(?:er|ers|ing)", r"backlinks?",
        r"ads", r"instagram", r"tiktok", r"facebook", r"followers", r"engagement",
        r"google analytics", r"ga4", r"conversion", r"funnels?", r"affiliate",
    ],
    "development": [
        r"develop(?:er|ment)?", r"web ?site", r"web app", r"wordpress", r"shopify", r"woocommerce",
        r"webflow", r"apps?", r"api", r"react(?: native)?", r"next\.?js", r"node(?:\.?js)?",
        r"vue", r"angular", r"javascript", r"typescript", r"python", r"django", r"flask",
        r"fastapi", r"php", r"laravel", r"ruby", r"rails", r"java", r"kotlin", r"swift",
        r"flutter", r"ios", r"android", r"html", r"css", r"front[ -]?end", r"back[ -]?end",
        r"full[ -]?stack", r"software", r"programmer", r"bug", r"script", r"automation",
        r"bot", r"chrome extension", r"plugin", r"integration", r"aws", r"devops", r"docker",
        r"saas", r"database", r"scrap(?:er|ing)", r"golang", r"c\+\+", r"c#", r"\.net",
    ],
}

_PATTERNS = {
    cat: re.compile(r"(?<![a-z0-9])(?:" + "|".join(words) + r")(?![a-z0-9])", re.IGNORECASE)
    for cat, words in _KEYWORDS.items()
}


def categorise(title: str) -> str:
    """Return the category with the most keyword hits, or 'other' if none match."""
    if not isinstance(title, str):
        return "other"
    best, best_hits = "other", 0
    for cat in _KEYWORDS:  # insertion order = tie-break priority
        hits = len(_PATTERNS[cat].findall(title))
        if hits > best_hits:
            best, best_hits = cat, hits
    return best
