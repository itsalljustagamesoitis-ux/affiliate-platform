#!/usr/bin/env python3
"""
Dollar-Figure Cleanup — Mechanical Pass (V9 remediation)

Strips Amazon ToS Section 5(v) price claims from FSG and MLT article bodies.
Handles the high-confidence patterns that can be transformed mechanically:

  Line-level deletions:
    1. Bold callout lines:  **Currently around $X on Amazon.**
    2. Standalone currently: Currently around $X on Amazon, at the time of writing.
    3. Bold price colon:    **Price: $X**
    4. "At the time of writing, this runs around $X" standalone sentences
    5. Table / pipe price rows

  Sentence-level prefix deletions:
    6. "Currently around $X[...]. [Rest of text]" — strip price sentence, keep rest

  Inline clause strippings:
    7. ", currently around $X to $Y on Amazon [qualifiers]"
    8. ", currently runs around $X [qualifiers]"
    9. ", runs around $X to $Y [qualifiers]."
   10. ", at around $X to $Y [qualifiers]"
   11. ", costs around $X to $Y [qualifiers]"
   12. "currently around $X to $Y on Amazon [qualifiers]," (leading clause → capitalize next)

SKIP articles requiring full editorial reframes (comparison articles).
SKIP lines matching commodity/operating cost exclusions (same as V9).

Usage:
    # Dry run — show what would change, don't write
    python3 scripts/fsg-dollar-cleanup.py --site FSG --dry-run

    # Apply changes
    python3 scripts/fsg-dollar-cleanup.py --site FSG

    # Both sites
    python3 scripts/fsg-dollar-cleanup.py --site FSG MLT

    # Single article (for testing)
    python3 scripts/fsg-dollar-cleanup.py --article /path/to/article.md --dry-run
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Articles excluded from mechanical pass — need full editorial reframes
# ---------------------------------------------------------------------------
SKIP_ARTICLES = {
    # FSG full editorial reframes
    'rectangular-fire-pit-table.md',
    'wood-burning-fire-pit-table.md',
    'fire-pit-with-coffee-table.md',
    'fire-pit-with-hidden-propane-tank.md',
    'propane-fire-pit-cover.md',
    'porch-swing-daybed.md',
    # FSG minor reframes (still skip in mechanical pass)
    'outdoor-wicker-rocking-chair.md',
    'large-adirondack-chair.md',
}

SITE_PATHS = {
    'FSG': Path('/Users/keithlacy/four-season-gardener'),
    'MLT': Path('/Users/keithlacy/my-little-tablespoon'),
}

# ---------------------------------------------------------------------------
# Commodity / operating cost exclusions — identical to V9 _EXCLUDE_LINE_RE
# ---------------------------------------------------------------------------
_EXCLUDE_LINE_RE = re.compile(
    r'(?:'
    r'\$[\d.,]+\s*(?:per|/)\s*(?:kWh|kwh|kilowatt)'
    r'|(?:per\s+hour|/\s*hour|per\s*hr|/hr)\b'
    r'|\$[\d.,]+\s+(?:per|to)\s+(?:refill|fill)\b'
    r'|\$[\d.,]+\s+per\s+(?:gallon|gal)\b'
    r'|\$[\d.,]+\s+per\s+(?:battery|cell|pack)\b'
    r'|\$[\d.,]+\s+per\s+(?:sq(?:uare)?\s*f(?:oot|t|eet)?)\b'
    r'|\$[\d.,]+\s+per\s+(?:lb|pound|oz|ounce)\b'
    r'|\$[\d.,]+(?:[-–][\d.,]+)?\s+per\s+(?:tank|canister|cylinder|cartridge)\b'
    r'|\$[\d.,]+\s+per\s+(?:quart|qt|liter|litre|L)\b'
    r'|per\s+evening\b'
    r')',
    re.IGNORECASE,
)

_FRONTMATTER_RE = re.compile(r'^(---\s*\n.*?\n---\s*\n)', re.DOTALL)

# Dollar figure check pattern (same as V9)
_DOLLAR_RE = re.compile(r'\$\d{1,4}(?:[,.\d]*)?(?:\+)?', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Transformation patterns
# ---------------------------------------------------------------------------

# 1. Bold callout entire line: **Currently around $X...** or **Currently $X...**
_BOLD_CALLOUT_RE = re.compile(
    r'^\s*\*\*Currently\s+(?:around\s+)?\$[\d,.].*?\*\*\.?\s*$',
    re.IGNORECASE,
)

# 2a. Standalone "Currently around $X..." or "- Currently around $X..." line
_STANDALONE_CURRENTLY_RE = re.compile(
    r'^\s*(?:[-*]\s+)?Currently\s+(?:(?:around|in\s+the)\s+)?\$[\d,.]'
    r'(?:[^.]*\.)?\s*$',
    re.IGNORECASE,
)

# 2b. Standalone "At the time of writing, this runs around $X..." line
_STANDALONE_ATTIME_RE = re.compile(
    r'^\s*At\s+the\s+time\s+of\s+writing[,\s]+(?:this\s+)?'
    r'(?:runs?\s+around|is\s+priced\s+at|lists?\s+at|costs?\s+around)\s+\$[\d,.]'
    r'(?:[^.]*\.)?\s*$',
    re.IGNORECASE,
)

# 3. Bold "Price: $X" or "**Price:** Around $X" or "- **Price** Around $X" entire line
_BOLD_PRICE_COLON_RE = re.compile(
    r'^\s*(?:[-*]\s+)?\*\*Price[^*]*\*?\*?[^\n]*\$[\d,.]',
    re.IGNORECASE,
)

# 4. Table/pipe price row — many label variants
_TABLE_PRICE_ROW_RE = re.compile(
    r'^\|\s*(?:[Aa]pprox(?:imate)?\.?\s+)?(?:\*\*)?'
    r'(?:[Cc]urrent(?:ly)?\s+)?[Pp]rice(?:\s+[Rr]ange)?(?:\s+\([^)]*\))?(?:\*\*)?\s*\|',
    re.IGNORECASE,
)
_TABLE_AROUND_ROW_RE = re.compile(
    r'^\|\s*(?:~|[Aa]round\s+)?\$[\d,.]',
    re.IGNORECASE,
)
# Comparison table row: "| [Product link](product:...) | Currently around $X |"
_TABLE_PRODUCT_PRICE_ROW_RE = re.compile(
    r'^\|\s*\[.*?\]\(product:[^)]+\)\s*\|[^|]*\$',
    re.IGNORECASE,
)

# 5. Sentence prefix: "Currently around $X[...]. Rest of text"
_PREFIX_CURRENTLY_RE = re.compile(
    r'^(Currently\s+(?:around\s+)?\$[\d,.][^.]*\.)\s+',
    re.IGNORECASE,
)

# 5b. Sentence prefix: "Priced around $X[...], [product/description]..."
_PREFIX_PRICED_RE = re.compile(
    r'^(Priced\s+around\s+\$[\d,.][^,]*,)\s+',
    re.IGNORECASE,
)

# 5c. Mid-line price sentence: ". Currently around $X[...]. "
# e.g. "This is my recommendation. Currently around $180 to $220 depending on size."
_MID_CURRENTLY_RE = re.compile(
    r'(\.\s+)Currently\s+(?:around\s+)?\$[\d,.][^.]*\.\s*',
    re.IGNORECASE,
)

# 5d. Standalone "Price: currently around $X..." line (starts with "Price:")
_STANDALONE_PRICE_COLON_TEXT_RE = re.compile(
    r'^\s*Price:\s+currently\s+(?:around\s+)?\$[\d,.]',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Inline clause patterns (remove price clause, keep surrounding text)
# Each: (pattern, replacement)
# ---------------------------------------------------------------------------
_INLINE_SUBS = [
    # "currently around $X to $Y on Amazon [at the time of writing] [depending on X]"
    # As a comma-preceded clause: ", currently around $X..."
    (re.compile(
        r',\s+currently\s+(?:around\s+)?\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # "currently around $X to $Y on Amazon[...], " as a LEADING clause
    # Transform: "Currently around $X, it's a good pick" → "It's a good pick"
    # (Handled in sentence-level logic below, not here)

    # ", currently runs around $X to $Y [qualifiers]"
    (re.compile(
        r',\s+currently\s+runs?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # " currently runs around $X to $Y on Amazon [qualifiers]" mid-sentence
    (re.compile(
        r'\s+currently\s+runs?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:depending|for|if|and|but|which|before|when)\s|$)',
        re.IGNORECASE,
    ), ''),

    # ", runs around $X to $Y [qualifiers]"
    (re.compile(
        r',\s+runs?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # " runs around $X to $Y [qualifiers]." at end of sentence
    (re.compile(
        r'\s+runs?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?\.',
        re.IGNORECASE,
    ), '.'),

    # ", at around $X to $Y [qualifiers]"
    (re.compile(
        r',\s+at\s+around\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # ", costs around $X to $Y [qualifiers]"
    (re.compile(
        r',\s+costs?\s+around\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?',
        re.IGNORECASE,
    ), ''),

    # " is currently around $X to $Y on Amazon [qualifiers]"
    (re.compile(
        r'\s+is\s+currently\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)])',
        re.IGNORECASE,
    ), ''),

    # " lists at $X to $Y on Amazon [qualifiers]"
    (re.compile(
        r',?\s+(?:currently\s+)?lists?\s+at\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # "at $X to $Y on Amazon" as a clause
    (re.compile(
        r'\s+at\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?\s+on\s+Amazon'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)])',
        re.IGNORECASE,
    ), ''),

    # ", priced at $X [qualifiers]"
    (re.compile(
        r',\s+(?:currently\s+)?priced\s+at\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?',
        re.IGNORECASE,
    ), ''),

    # " is priced at $X" (without leading comma)
    (re.compile(
        r'\s+is\s+(?:currently\s+)?priced\s+at\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)])',
        re.IGNORECASE,
    ), ''),

    # "for around $X to $Y [qualifiers]" — accessory/add-on prices
    (re.compile(
        r'\s+for\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+and\s+is\s+widely\s+available)?'
        r'(?=\s*[,;.)]|\s+(?:on|and|at|depending)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "(currently around $X[...])" — parenthetical price callout
    (re.compile(
        r'\s*\(currently\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?[^)]*\)',
        re.IGNORECASE,
    ), ''),

    # "(around $X to $Y[...])" — parenthetical price range
    (re.compile(
        r'\s*\(around\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?[^)]*\)',
        re.IGNORECASE,
    ), ''),

    # "approximately $X to $Y" — estimated price inline
    (re.compile(
        r'\s+approximately\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.)]|\s+(?:before|if|and|or|depending|when|at|for)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "roughly $X to $Y" inline (not in excluded commodity context)
    (re.compile(
        r'\s+roughly\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+(?:per\s+unit|on\s+Amazon|for\s+the\s+\w+))?'
        r'(?=\s*[,;.)]|\s+(?:per|on|for|and|or|depending|if|at|to)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "runs $X to $Y" or "runs $X-$Y" (without "around") — e.g., "runs $1,400 to $1,600"
    (re.compile(
        r'\s+runs?\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:depending|for|if|and|but|which|before|when|compared)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "runs about $X" (without "around") — competitor/reference price
    (re.compile(
        r'\s+runs?\s+about\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:depending|for|if|and|but|which|before|when)\s|$)',
        re.IGNORECASE,
    ), ''),

    # " costs $X to $Y" (without "around") — direct price claim
    (re.compile(
        r'\s+costs?\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:depending|for|if|and|but|which|before|when)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "It's currently around $X on Amazon[, though prices shift]." — inline sentence
    (re.compile(
        r"It's\s+currently\s+(?:around\s+)?\$[\d,.]+\s+on\s+Amazon[^.]*\.\s*",
        re.IGNORECASE,
    ), ''),

    # "pays for its $X price tag" / "pays for its $X to $Y price tag"
    (re.compile(
        r'(?:pays?\s+for\s+its\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?\s+price\s+tag',
        re.IGNORECASE,
    ), 'its price'),

    # "sub-$X" qualifier → "entry-level"
    (re.compile(r'\bsub-\$[\d,.]+\b', re.IGNORECASE), 'entry-level'),

    # " runs around $X to $Y [qualifiers]" — requires "around" or "between" keyword
    # Safe: removing "around $X to $Y" leaves "runs" as intact verb
    (re.compile(
        r'\s+runs?\s+(?:around|between)\s+\$[\d,.]+(?:[-–]\$[\d,.]+)?'
        r'(?:\s+(?:to|and)\s+\$[\d,.]+)?'
        r'(?:\s+currently)?'
        r'(?:\s+on\s+Amazon)?'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:and|which|currently|making|where|but|so|depending|for|if|with|without|don\'t|doesn\'t)\s|$)',
        re.IGNORECASE,
    ), ''),

    # ", which runs around $X" / ", which costs around $X" (relative clause)
    (re.compile(
        r',\s+which\s+(?:runs?\s+around|costs?\s+around|is\s+(?:currently\s+)?(?:around\s+)?)\s*\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?',
        re.IGNORECASE,
    ), ''),

    # " are currently around $X to $Y" (are instead of is)
    (re.compile(
        r'\s+are\s+currently\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)])',
        re.IGNORECASE,
    ), ''),

    # " is currently priced around $X" (priced between currently and $)
    (re.compile(
        r'\s+is\s+currently\s+priced\s+(?:around\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)])',
        re.IGNORECASE,
    ), ''),

    # " costs around $X to $Y [qualifiers]" — requires "around" keyword (safe)
    (re.compile(
        r'\s+costs?\s+around\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.]|\s+and\s)',
        re.IGNORECASE,
    ), ''),

    # " sits around $X to $Y" — requires "around" keyword (safe; "sits" remains as verb)
    (re.compile(
        r',?\s+sits?\s+around\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+currently)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?(?=\s*[,;.)]|\s+(?:before|making|which|and)\s)',
        re.IGNORECASE,
    ), ''),

    # "in the $X to $Y range" / "in the $X-$Y range" — price range descriptor
    (re.compile(
        r'\s+in\s+the\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?\s+range'
        r'(?=\s*[,;.]|\s+(?:and|which|currently|typically|before|depending)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "Price runs around $X" / "Price at time of writing: around $X" standalone lines
    (re.compile(
        r'^Price\s+(?:runs?\s+around|at\s+(?:time|the\s+time)\s+of\s+writing[:\s]+around)\s+\$[\d,.]+[^.]*\.\s*',
        re.IGNORECASE,
    ), ''),

    # "Pricing sits in the $X range currently." / "Pricing runs around $X" — standalone
    (re.compile(
        r'Pricing\s+(?:sits?\s+in\s+the\s+|runs?\s+around\s+)\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?[^.]*\.\s*',
        re.IGNORECASE,
    ), ''),

    # "At around $X, [description]" / "At close to $X, [description]"
    # Sentence starting with "At $X, " — strip price intro, capitalize next word
    (re.compile(
        r'^At\s+(?:close\s+to\s+|around\s+|a\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+price\s+point)?[^,]*,\s+',
        re.IGNORECASE | re.MULTILINE,
    ), ''),

    # "(sold separately, around $X for ...)" — parenthetical accessory price
    (re.compile(
        r'\s*\(sold\s+separately,?\s+(?:around\s+)?\$[\d,.]+[^)]*\)',
        re.IGNORECASE,
    ), ''),

    # "push the total cost toward $X" — remove just the dollar amount
    (re.compile(
        r'(?:push(?:es)?\s+the\s+(?:total\s+)?cost\s+toward\s+)\$[\d,.]+',
        re.IGNORECASE,
    ), 'push the total cost higher'),

    # "Total cost at current pricing: approximately $X to $Y" — delete sentence
    (re.compile(
        r'Total\s+cost\s+at\s+current\s+pricing[^.]*\$[\d,.][^.]*\.\s*',
        re.IGNORECASE,
    ), ''),

    # ". At around $X[...], description" — mid-paragraph "At $X," sentence
    # Strips price intro from sentences that begin mid-line with "At $X,"
    (re.compile(
        r'(\.\s+)At\s+(?:close\s+to\s+|around\s+|a\s+)?\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?'
        r'(?:\s+price\s+point)?[^,]*,\s+(?=[A-Za-z])',
        re.IGNORECASE,
    ), r'\1'),

    # "for $X to $Y [at the time of writing]" — add-on/accessory price without "around"
    (re.compile(
        r'\s+for\s+(?:another\s+|an?\s+additional\s+)?\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:and|which|per|if|depending|on)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "costs $X to $Y" without "around" — swap verb+price for qualitative
    (re.compile(
        r'\s+costs?\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+inline)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:and|if|depending|before)\s|$)',
        re.IGNORECASE,
    ), ' is available'),

    # "costs under $X" → "is entry-level" (safe: verb + threshold → qualitative)
    (re.compile(
        r'\s+costs?\s+under\s+\$[\d,.]+(?=\s*[,;.]|$)',
        re.IGNORECASE,
    ), ' is entry-level'),

    # "under $X" / "under $X," inline — tier qualifier (broad lookahead)
    # Note: "costs under $X" → "is entry-level" is handled by the pattern above
    # so this won't see "costs under $X" after it's already been replaced
    (re.compile(
        r'\bunder\s+\$[\d,.]+(?=\s*[,;.:\)]|\s+|$)',
        re.IGNORECASE,
    ), 'entry-level'),

    # "for under $X" — pricing qualifier with "for"
    (re.compile(
        r'\s+for\s+under\s+\$[\d,.]+(?=\s*[,;.:\)]|\s+|$)',
        re.IGNORECASE,
    ), ''),

    # "- Under $X" / "- Under $X." standalone bullet lines
    (re.compile(
        r'^\s*-\s+Under\s+\$[\d,.]+(?:\.|,)?\s*$',
        re.IGNORECASE,
    ), ''),

    # "over $X" inline price — tier upper bound
    (re.compile(
        r'\bover\s+\$[\d,.]+(?=\s*[,;.\)]|\s+(?:and|or|at|each|on|if)\s|$)',
        re.IGNORECASE,
    ), 'premium'),

    # "around $X to $Y" standalone (without explicit verb) — inline price mention
    (re.compile(
        r',?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?:\s+(?:additional|each))?'
        r'(?=\s*[,;.]|\s+(?:on|and|or|depending|for|if|at)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "another $X" / "another $X to $Y" — accessory add-on
    (re.compile(
        r'\banother\s+\$[\d,.]+(?:\s+to\s+\$[\d,.]+)?(?=\s*[,;.]|\s+(?:to|for|buying|getting|and|or)\s|$)',
        re.IGNORECASE,
    ), 'more'),

    # "$X additional" / "$X more" / "$X extra" inline
    (re.compile(
        r'\$[\d,.]+\s+(?:additional|more|extra)(?=\s*[,;.]|\s+(?:and|to|than|if|per)\s|$)',
        re.IGNORECASE,
    ), 'a bit more'),

    # "$X or more" — spending/cost threshold
    (re.compile(
        r'\$[\d,.]+\s+or\s+more(?=\s*[,;.)]|\s+(?:on|and|if|than|for)\s|$)',
        re.IGNORECASE,
    ), 'significantly more'),

    # "$X-plus" / "$X+" — premium price marker
    (re.compile(r'\$[\d,.]+[-–]?plus\b', re.IGNORECASE), 'premium'),
    (re.compile(r'\$[\d,.]+\+(?=[\s,;.])', re.IGNORECASE), 'premium'),

    # "runs around $X for [qualifier], with" — extended runs-around with "for" qualifier
    (re.compile(
        r'\s+currently\s+runs?\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'\s+for\s+[^,]+,',
        re.IGNORECASE,
    ), ','),

    # "closer to $X to $Y" / "closer to $X-$Y" — investment/cost framing
    (re.compile(
        r'\s+closer\s+to\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+depending\s+on\s+[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:before|if|and|or|depending|when|with|without|this)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "starts around $X to $Y" / "starts at $X to $Y" — competitor pricing
    (re.compile(
        r'\s+starts?\s+(?:around|at)\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+(?:without|before|with|similarly)[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:and|similarly|before|without|battery)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "is $X to $Y [if/before]" — plain copula + price range
    (re.compile(
        r'\s+is\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)'
        r'(?:\s+(?:if|before|and)\s+[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:if|before|and|depending|when|at)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "additional $X to $Y" (no "for") — panels/accessories priced inline
    (re.compile(
        r'(?:an?\s+)?additional\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?=\s*[,;.]|\s+(?:if|and|or|depending|for|to)\s|$)',
        re.IGNORECASE,
    ), 'extra'),

    # "$X to $Y is [a] [description]" — price range as sentence/bullet subject
    (re.compile(
        r'^(\s*(?:[-*]\s+)?)\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)\s+is\s+',
        re.IGNORECASE,
    ), r"\1That's "),

    # "a/an $X noun" / "the $X noun" — inline price adjective: strip price keep article
    (re.compile(
        r'\b(a|an|the)\s+\$[\d,.]+\+?\s+',
        re.IGNORECASE,
    ), r'\1 '),

    # "the $X price/cost" → "the price/cost"
    (re.compile(
        r'\bthe\s+\$[\d,.]+(?:[-–]\$[\d,.]+)?\s+(?=price|cost)',
        re.IGNORECASE,
    ), 'the '),

    # "currently in the $X to $Y range" as a standalone sentence or prefix
    (re.compile(
        r'Currently\s+in\s+the\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?\s+range[^.]*\.\s*',
        re.IGNORECASE,
    ), ''),

    # "At roughly $X" sentence start — "At roughly $189, [description]"
    (re.compile(
        r'^At\s+roughly\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?[^,]*,\s+',
        re.IGNORECASE,
    ), ''),

    # ". At roughly $X[...], " mid-paragraph sentence
    (re.compile(
        r'(\.\s+)At\s+roughly\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?[^,]*,\s+(?=[A-Za-z])',
        re.IGNORECASE,
    ), r'\1'),

    # "Around $X" sentence start — "Around $12, [description]"
    (re.compile(
        r'^Around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?[^,]*,\s+',
        re.IGNORECASE,
    ), ''),

    # "$X,$Y" comma-as-range-separator notation (unusual format) — treat as price range
    # e.g. "At $15,$18, this is..." or "runs about $15,$18"
    (re.compile(
        r'\$[\d,.]+,\$[\d,.]+',
        re.IGNORECASE,
    ), ''),

    # Orphaned ",$X" artifact from partial price removal — strip comma+price
    (re.compile(
        r',\s*\$[\d,.]+(?:\s+(?:and|or|rather)\s|(?=\s*[,;.)]|$))',
        re.IGNORECASE,
    ), ''),

    # "Paying $X for [noun]" → "For [noun]" (remove price, keep context)
    (re.compile(
        r'\bPaying\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?\s+for\s+',
        re.IGNORECASE,
    ), 'For '),

    # "Budget $X to $Y per [noun] for [desc], which adds $X to $Y"
    # Strip "Budget $X to $Y per [noun] for [desc]," — editorial budget callout
    (re.compile(
        r'\bBudget\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+per\s+\w+)?(?:\s+for\s+[^,;.]+)?'
        r'(?=\s*[,;.]|\s+(?:if|and|which|combined|more|to)\s|$)',
        re.IGNORECASE,
    ), 'Budget accordingly'),

    # "adds $X to $Y to the total cost" — cost addition framing
    (re.compile(
        r'\badds?\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'\s+to\s+the\s+(?:total\s+)?(?:cost|price)'
        r'(?:\s+of\s+[^,;.]+)?(?=\s*[,;.]|$)',
        re.IGNORECASE,
    ), 'adds to the total cost'),

    # "vs $X" / "vs. $X" — comparison price qualifier
    (re.compile(
        r'\s+vs\.?\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?=\s*[,;.)]|\s+(?:for|and|or|at)\s|$)',
        re.IGNORECASE,
    ), ''),

    # Also catch bare "$X[-$Y]" at end of a list bullet: "- $X to $Y\n"
    (re.compile(
        r'^(\s*[-*]\s+)\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?\s*$',
        re.IGNORECASE,
    ), r'\1'),

    # "$X-ish" / "$X–ish" — approximate price with -ish suffix
    (re.compile(
        r'\b(a|an|the)\s+\$[\d,.]+[-–]?ish\s+',
        re.IGNORECASE,
    ), r'\1 '),

    # "below $X" / "below $X to $Y" — floor price threshold
    (re.compile(
        r'\bbelow\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?=\s*[,;.)]|\s+(?:and|or|at|if|on|in|for|per|price|that)\s|$)',
        re.IGNORECASE,
    ), 'below premium pricing'),

    # "of $X to $Y" — container/context price reference
    (re.compile(
        r'\s+of\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?=\s*[,;.)]|\s+(?:bamboo|per|and|or|that|for|in|each)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "from $X-ish" / "from $X " (plain, no around) before a noun — ranging intro
    (re.compile(
        r'\s+from\s+(?:a\s+)?\$[\d,.]+[-–]?(?:ish)?\s+(?=[a-z])',
        re.IGNORECASE,
    ), ' from an entry-level '),

    # Orphaned "to $X" artifact after partial price removal
    (re.compile(
        r'\bthe\s+to\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?(?=\s)',
        re.IGNORECASE,
    ), 'the'),

    # "from around $X to $Y" — ranging/spanning pricing (include "from" to avoid orphan)
    (re.compile(
        r'\s+from\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:and|or|depending|if|at)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "runs to $X" / "run to $X" — pricing verb (no "around")
    (re.compile(
        r'\s+runs?\s+to\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+each)?(?=\s*[,;.]|\s+(?:at|and|each|for|depending|if)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "at $X to $Y" (no "around") — comparison context
    # Only when price range (has "to"), to reduce risk of matching "at $X" main verbs
    (re.compile(
        r'\s+at\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)'
        r'(?:\s+(?:currently|per\s+unit))?'
        r'(?=\s*[,;.]|\s+(?:if|it|you|and|or|depending|for|the|is|are|gets?|makes?|works?|sits?|typically|today|don\'t|doesn\'t|with|without)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "at around $X" (no comma prefix) — standalone price qualifier
    (re.compile(
        r'\s+at\s+around\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+on\s+Amazon)?(?:\s+at\s+the\s+time\s+of\s+writing)?'
        r'(?=\s*[,;.]|\s+(?:if|it|you|and|or|depending|for|the|is|are|gets?|makes?|paired|compared|works?)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "at $X is/are" — single price + copula (no range needed)
    (re.compile(
        r'\s+at\s+\$[\d,.]+(?:[-–]\$[\d,.]+)?\s+(?=is\b|are\b)',
        re.IGNORECASE,
    ), ' '),

    # "$X and up" / "$X and above" — tier upper bound
    (re.compile(
        r'\$[\d,.]+\s+and\s+(?:up|above)(?=\s*[,:;.]|\s+|$)',
        re.IGNORECASE,
    ), 'premium'),

    # "sits about $X cheaper/less" — relative pricing
    (re.compile(
        r'\s+(?:sits?|runs?|comes?)\s+about\s+\$[\d,.]+(?:\s+(?:cheaper|less|lower|more|higher))?'
        r'(?=\s*[,;.]|\s+(?:in|and|or|than|at|if)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "and $X" orphan from compound range removal artifact
    (re.compile(
        r'(?<=\btypically)\s+and\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?=\s*[,;.)]|\s+(?:depending|for|if|and|or|when)\s|$)',
        re.IGNORECASE,
    ), ''),

    # "under $X:" (colon) — tier/section label
    (re.compile(
        r'\bunder\s+\$[\d,.]+:',
        re.IGNORECASE,
    ), 'entry-level:'),

    # "- At $X to $Y, [description]" — bullet starting with "At $X,"
    (re.compile(
        r'^(\s*[-*]\s+)At\s+(?:close\s+to\s+|around\s+|roughly\s+)?\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?[^,]*,\s+',
        re.IGNORECASE,
    ), r'\1'),

    # "Mid-range $X to $Y:" / "Budget $X to $Y:" — tier section labels
    (re.compile(
        r'^(\s*[-*]?\s*(?:Mid-range|Budget|Premium|Entry-level|High-end)\s+)\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?:',
        re.IGNORECASE,
    ), r'\1range:'),

    # "add $X to $Y" — verb + direct price object
    (re.compile(
        r'\badd\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+if\s+[^,;.]+)?(?=\s*[,;.]|\s+(?:if|and|or|to|for)\s|$)',
        re.IGNORECASE,
    ), 'budget accordingly'),

    # "spending $X" / "spend $X" inline — purchase cost mention
    (re.compile(
        r'\b(?:spending|spend)\s+\$[\d,.]+(?:[-–]\$[\d,.]+|\s+to\s+\$[\d,.]+)?'
        r'(?:\s+or\s+more)?(?=\s*[,;.)]|\s+(?:on|and|or|if|for)\s|$)',
        re.IGNORECASE,
    ), r'spending that much'),
]

# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

def _clean_artifacts(line: str) -> str:
    """Clean up double spaces, orphaned leading commas, etc. after substitutions."""
    # Double spaces
    line = re.sub(r'  +', ' ', line)
    # Orphaned leading comma/period in a sentence fragment: ". ,  text" etc.
    line = re.sub(r'\.\s+,', '.', line)
    # Orphaned "to ." artifact — e.g. "ranging from to." after price removal
    line = re.sub(r'\s+to\s*\.', '.', line)
    # Orphaned "from ." artifact — e.g. "ranging from." after price removal
    line = re.sub(r'\s+from\s*\.', '.', line)
    # Orphaned "around to." artifact — e.g. "ranging from around to."
    line = re.sub(r'\s+around\s+to\.', '.', line)
    # Orphaned ", to $X" where $X was already removed but "to" was left
    line = re.sub(r',\s+to\s*\.', '.', line)
    # Trailing space before punctuation
    line = re.sub(r'\s+([.!?,;:])', r'\1', line)
    # Leading/trailing whitespace (preserve markdown indentation though)
    return line.rstrip()


def _capitalize_first(s: str) -> str:
    """Capitalize the first letter of a string."""
    if not s:
        return s
    return s[0].upper() + s[1:]


def transform_line(line: str) -> tuple:
    """
    Apply transformations to a single body line.

    Returns:
        (result, op_name) where:
          result = None means delete the line entirely
          result = str means the (possibly modified) line to keep
          op_name = which operation fired (or '' if no change)
    """
    # Skip excluded commodity/operating cost lines
    if _EXCLUDE_LINE_RE.search(line):
        return line, ''

    stripped = line.strip()

    # --- Line-level deletions ---

    # 1. Bold callout line
    if _BOLD_CALLOUT_RE.match(stripped):
        return None, 'bold_callout'

    # 3. Bold price colon
    if _BOLD_PRICE_COLON_RE.match(stripped):
        return None, 'bold_price_colon'

    # 4. Table price rows
    if (_TABLE_PRICE_ROW_RE.match(stripped)
            or _TABLE_AROUND_ROW_RE.match(stripped)
            or _TABLE_PRODUCT_PRICE_ROW_RE.match(stripped)):
        return None, 'table_price_row'

    # 2a. Standalone "Currently around $X..." (entire line is just a price sentence)
    if _STANDALONE_CURRENTLY_RE.match(stripped) and not re.search(r'\.\s+\S', stripped):
        return None, 'standalone_currently'

    # 2b. Standalone "At the time of writing, this runs around $X..."
    if _STANDALONE_ATTIME_RE.match(stripped):
        return None, 'standalone_attime'

    # 2c. Standalone "Price: currently around $X..." line
    if _STANDALONE_PRICE_COLON_TEXT_RE.match(stripped):
        return None, 'standalone_price_colon_text'

    # If no dollar sign remains, nothing to do
    if not _DOLLAR_RE.search(line):
        return line, ''

    modified = line

    # --- Sentence prefix deletions ---

    # 5. "Currently around $X[...]. Rest of text" — strip price sentence prefix
    prefix_m = _PREFIX_CURRENTLY_RE.match(modified)
    if prefix_m:
        rest = modified[prefix_m.end():]
        rest = _capitalize_first(rest)
        modified = rest

    # 5b. "Priced around $X[...], [product description]"
    priced_m = _PREFIX_PRICED_RE.match(modified)
    if priced_m:
        rest = modified[priced_m.end():]
        rest = _capitalize_first(rest)
        modified = rest

    # 5c. Mid-line ". Currently around $X[...]." → "." (remove price sentence)
    modified = _MID_CURRENTLY_RE.sub(r'\1', modified)

    # --- Inline clause strippings ---

    for pattern, replacement in _INLINE_SUBS:
        new = pattern.sub(replacement, modified)
        if new != modified:
            modified = _clean_artifacts(new)

    if modified != line:
        return modified, 'inline_sub'

    return line, ''


def transform_body(body: str) -> tuple[str, dict]:
    """
    Transform the article body text.

    Returns:
        (new_body, stats) where stats has counts per operation type
    """
    lines = body.split('\n')
    out_lines = []
    stats: dict[str, int] = {}
    residuals = []

    for i, line in enumerate(lines):
        result, op = transform_line(line)
        if result is None:
            stats[op] = stats.get(op, 0) + 1
        elif result != line:
            stats[op] = stats.get(op, 0) + 1
            out_lines.append(result)
        else:
            out_lines.append(line)
            # Check for residual violations
            if _DOLLAR_RE.search(line) and not _EXCLUDE_LINE_RE.search(line):
                residuals.append((i + 1, line.strip()[:100]))

    # Remove consecutive blank lines left by deletions (max 1 blank line)
    collapsed = []
    prev_blank = False
    for ln in out_lines:
        is_blank = ln.strip() == ''
        if is_blank and prev_blank:
            continue
        collapsed.append(ln)
        prev_blank = is_blank

    stats['_residuals'] = residuals
    return '\n'.join(collapsed), stats


def process_article(path: Path, dry_run: bool = False) -> dict:
    """Process a single article. Returns a result dict."""
    text = path.read_text(encoding='utf-8', errors='replace')

    # Extract frontmatter + body
    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        return {'skipped': True, 'reason': 'no_frontmatter'}

    frontmatter = fm_match.group(1)
    body = text[fm_match.end():]

    new_body, stats = transform_body(body)
    changed = new_body != body

    if changed and not dry_run:
        path.write_text(frontmatter + new_body, encoding='utf-8')

    return {
        'skipped': False,
        'changed': changed,
        'dry_run': dry_run,
        'stats': stats,
        'residuals': stats.get('_residuals', []),
        'ops': {k: v for k, v in stats.items() if not k.startswith('_')},
    }


def run_site(site_root: Path, dry_run: bool, verbose: bool) -> dict:
    articles_dir = site_root / 'content' / 'articles'
    if not articles_dir.exists():
        print(f"ERROR: {articles_dir} not found", file=sys.stderr)
        return {}

    total = changed = skipped = total_residuals = 0
    total_ops: dict[str, int] = {}
    all_residuals = []

    for md in sorted(articles_dir.glob('*.md')):
        total += 1

        if md.name in SKIP_ARTICLES:
            skipped += 1
            if verbose:
                print(f"  SKIP  {md.name}  (editorial reframe required)")
            continue

        result = process_article(md, dry_run=dry_run)
        if result.get('skipped'):
            continue

        for op, n in result['ops'].items():
            total_ops[op] = total_ops.get(op, 0) + n

        res = result['residuals']
        total_residuals += len(res)

        if result['changed']:
            changed += 1
            if verbose:
                op_summary = ', '.join(f"{k}:{v}" for k, v in result['ops'].items())
                print(f"  MOD   {md.name}  [{op_summary}]  {len(res)} residuals")
                for line_no, ctx in res[:3]:
                    print(f"          line {line_no}: {ctx}")
                if len(res) > 3:
                    print(f"          ... and {len(res) - 3} more residuals")
        elif res and verbose:
            print(f"  --    {md.name}  ({len(res)} residuals, no mechanical changes)")
            for line_no, ctx in res[:2]:
                print(f"          line {line_no}: {ctx}")

        all_residuals.extend([(md.name, ln, ctx) for ln, ctx in res])

    mode = 'DRY RUN' if dry_run else 'APPLIED'
    print(f"\n{'='*60}")
    print(f"  {mode}: {site_root.name}")
    print(f"  Articles processed : {total - skipped}")
    print(f"  Articles skipped   : {skipped}  (editorial reframes)")
    print(f"  Articles modified  : {changed}")
    print(f"  Total residuals    : {total_residuals}  (need manual review)")
    if total_ops:
        print(f"  Operations:")
        for op, n in sorted(total_ops.items()):
            print(f"    {op:<28} {n:>4}")

    if total_residuals and not verbose:
        print(f"\n  (run with --verbose to see residual contexts)")

    return {'residuals': all_residuals, 'total_ops': total_ops}


def main():
    parser = argparse.ArgumentParser(description='Dollar-figure mechanical cleanup')
    parser.add_argument('--site', nargs='+', metavar='SLUG',
                        help='Site slugs: FSG MLT')
    parser.add_argument('--article', metavar='PATH',
                        help='Process a single article file')
    parser.add_argument('--dry-run', action='store_true',
                        help="Show changes without writing")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Show per-article details")
    args = parser.parse_args()

    if args.article:
        path = Path(args.article)
        result = process_article(path, dry_run=args.dry_run)
        mode = 'DRY RUN' if args.dry_run else 'APPLIED'
        print(f"{mode}: {path.name}")
        print(f"  Changed:   {result['changed']}")
        print(f"  Ops:       {result['ops']}")
        print(f"  Residuals: {len(result['residuals'])}")
        for ln, ctx in result['residuals']:
            print(f"    line {ln}: {ctx}")
        return

    if not args.site:
        parser.print_help()
        sys.exit(1)

    for slug in args.site:
        slug = slug.upper()
        if slug not in SITE_PATHS:
            print(f"Unknown site: {slug}", file=sys.stderr)
            sys.exit(1)
        run_site(SITE_PATHS[slug], dry_run=args.dry_run, verbose=args.verbose)


if __name__ == '__main__':
    main()
