# Platform Fix: Apostrophe Escaping in Producer Output

**Type:** Producer output / YAML escaping fix  
**Severity if missed:** SEV-2 (broken article frontmatter, possible build failure)  
**First surfaced:** Site 15 (rmflyfishing) Phase 4 UAT — doubled apostrophes (`''`) in 76 article files  
**Status:** Fixed on Site 15 (sed one-liner across all articles); root cause in producer not yet addressed

---

## Problem

The article generator produces YAML frontmatter with string fields that contain apostrophes (e.g., `"Greg's setup"`, `"it's the right tool"`). When the producer writes these fields inside double-quoted YAML strings, it sometimes escapes apostrophes as `''` (two single quotes), which is valid in *single-quoted* YAML strings but renders as a literal double-apostrophe character inside *double-quoted* YAML strings.

The result: 76 article files on Site 15 contained visible `Greg''s` and similar constructs in rendered article body text.

## Root Cause

The producer (`producer/article_builder.py` or the LLM-generated output) writes string fields using double-quote YAML syntax but sometimes applies single-quote YAML escaping rules. In YAML:

```yaml
# Correct: single-quoted string ('' escapes ')
article_specific_pros:
  - 'Greg''s rod has been reliable'    # renders as: Greg's rod has been reliable

# Correct: double-quoted string (\' or unescaped are both fine)
article_specific_pros:
  - "Greg's rod has been reliable"     # renders as: Greg's rod has been reliable

# BROKEN: double-quoted string with '' escape
article_specific_pros:
  - "Greg''s rod has been reliable"   # renders as: Greg''s rod has been reliable (two apostrophes)
```

The LLM generating the YAML output applies `''` escaping when it produces single-quoted strings in the output, but the string delimiter used by the producer template is double-quotes. The mismatch produces broken output.

## Site 15 Fix

Bulk sed across all article files:
```bash
grep -rl "''" content/articles/ | xargs sed -i '' "s/''/'/g"
```

This replaced all `''` occurrences in the articles directory with single `'`. Because these files use double-quoted YAML strings (not single-quoted), this was safe.

## Permanent Fix

### Option A — Producer template fix

Change the producer's YAML template to use single-quoted strings for fields that may contain apostrophes, and validate that apostrophes are escaped as `''`:

```python
def yaml_single_quote(value: str) -> str:
    """Wrap value in single quotes, escaping any ' as ''"""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
```

### Option B — Post-generation validation

In `producer/article_builder.py`, after generating the YAML frontmatter:

```python
import yaml
try:
    yaml.safe_load(generated_frontmatter)
except yaml.YAMLError as e:
    raise ValueError(f"Generated frontmatter is invalid YAML: {e}")
```

This catches YAML syntax errors before writing to disk. A doubled apostrophe in a double-quoted string is valid YAML (it's just wrong text content), so this won't catch the specific `''` bug — but it catches actual parse failures.

### Option C — Prompt constraint

Add to the article generation system prompt:
```
When generating YAML string fields, use double-quoted strings. Never use '' to escape apostrophes — write apostrophes as literal ' characters inside double-quoted YAML strings.
```

**Recommended:** All three, as defense in depth.

## Done Criteria

- Producer generates clean apostrophes in all YAML output
- `producer/tests/` includes a test that generates a string with apostrophes and verifies single-apostrophe output
- `scripts/preflight.py` or build-validator.mjs has a check: `grep -c "''" content/articles/*.md` must return 0

## Related

- `platform-fix-card-voice-inheritance.md` — another producer output quality issue in frontmatter fields
