# DISAVOW.md — Aged-Domain Disavow Workflow

**First use:** undisclosedsounds.com (site 13), 2026-05-29.
**Pattern:** Any future aged-domain acquisition requiring a disavow file follows this document.

---

## What a disavow file is

A plain-text file uploaded to Google Search Console that instructs Google to ignore specified backlinks when evaluating the site's link profile. Used when a domain has a backlink profile contaminated by spam, link farms, or legacy low-quality links that could suppress rankings.

Google re-evaluates the disavow after a crawl cycle (typically 4–12 weeks). The effect is not immediate.

---

## When to submit

Submit the disavow file **immediately after** GSC DNS verification and **before** the site accumulates indexable content. Submitting early means the spam links are disavowed before Google's first substantive crawl of the new content. Submitting late means spam signals may be associated with early content in Google's evaluation.

**Hard sequence:**
1. DNS verified in GSC → property confirmed
2. Disavow file uploaded via GSC UI → submitted
3. Content pipeline starts → articles published

Never reverse steps 2 and 3.

---

## How to submit

1. Go to [Google Search Console](https://search.google.com/search-console)
2. Select the property (e.g., `undisclosedsounds.com`)
3. Navigate to: **Links → Disavow Links** (or use the direct tool URL)
4. Upload the `.txt` file — one `domain:example.com` line per spam domain, comments allowed (`# comment`)
5. Confirm submission. Google will confirm the file was parsed.

---

## Disavow file format

```
# Disavow file for undisclosedsounds.com
# Generated: 2026-05-29
# Semrush analysis: 210 total backlinks, 56 spam domains
# Preserved: ~20 legitimate editorial backlinks

domain:spamexample.blogspot.com
domain:linkfarm.tk
# (one domain per line)
```

Lines starting with `#` are comments and are ignored by Google.
Use `domain:example.com` (not full URLs) to disavow all links from a domain.

---

## Re-evaluation timeline

Google processes disavow files on the next crawl cycle after submission. Typical re-evaluation: **4–12 weeks**. There is no notification when re-evaluation is complete — monitor GSC's Links report and Search Performance for ranking movement.

---

## Per-site disavow state tracking

Each site requiring a disavow file has a `disavow` section in `site.config.yaml`:

```yaml
disavow:
  required: true
  file: "undisclosedsounds-disavow.txt"
  submitted_to_gsc: false        # Keith updates to true after submission
  submitted_date: null           # Keith updates to ISO date after submission
  reason: "Aged-domain pickup..."
  notes: "..."
```

Update `submitted_to_gsc: true` and `submitted_date` in `site.config.yaml` after submission.

---

## Sites requiring disavow as of 2026-05-29

| Site | Domain | Status | Submitted |
|---|---|---|---|
| undisclosedsounds | undisclosedsounds.com | Pending GSC verification | — |

Sites 1–12 were new registrations with no legacy backlink profiles. No disavow required.

---

## Future aged-domain acquisitions

1. Run Semrush (or Ahrefs) backlink audit before or immediately after registration
2. Export spam domains to a `.txt` disavow file following the format above
3. Stage the file in the site repo root (e.g., `undisclosedsounds-disavow.txt`)
4. Add `disavow` section to `site.config.yaml` with `submitted_to_gsc: false`
5. Submit via GSC immediately after DNS verification
6. Update `site.config.yaml` after submission
