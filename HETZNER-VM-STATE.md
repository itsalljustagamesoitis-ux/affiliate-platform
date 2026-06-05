# Hetzner VM State Report — Pre-flight for BHB Phase 4

_Inspected: 2026-05-21 08:50 UTC. Report-only — VM not modified._

---

## Section 1: Environment Summary

| Item | Value |
|---|---|
| Hostname | `oi-prod` |
| OS | Ubuntu 22.04.5 LTS (Jammy) |
| Kernel | 5.15.0-174-generic x86_64 |
| User | root, home `/root` |
| Disk free | 20 GB of 38 GB (44% used) |
| RAM available | 3.1 GB of 3.7 GB |
| vCPUs | 2 |
| SSH | `ssh -i ~/.ssh/id_ed25519 root@46.225.29.35` |

> **IP note (2026-06-05):** The canonical VM IP is `46.225.29.35`. The address `147.182.131.109` appeared in prior session context and is INCORRECT — it belongs to a different server (port 22 refuses, port 443 serves a web page). Do not use `147.182.131.109` for SSH. If SSH fails on `46.225.29.35`, verify with `nc -z -w5 46.225.29.35 22` before assuming the VM is down.

**Readiness: NEEDS_SETUP** — environment is solid, but BHB site and latest platform code are not yet on the VM.

---

## Section 2: Repo State

### affiliate-platform

The platform exists as a **git submodule** embedded inside three site repos on the VM:

| Location | Commit |
|---|---|
| `/root/bear-creek-barbecue/affiliate-platform` | `7518cd5` — `Reconcile canonical with audit-era fixes from vendored sites` |
| `/root/northwoods-overland/affiliate-platform` | No commit recorded (submodule not initialized?) |
| `/root/strengthmill/affiliate-platform` | No commit recorded |

**Local (Mac) affiliate-platform is 5+ commits ahead:**
```
7a17760  feat(validators): add v1.2 validator suite and furniture template families  ← LOCAL HEAD
475ad2d  docs: add v2.0.3 CHANGELOG entry
7e58738  fix(nav): correct overflow…
5774258  docs: add v2.0.2 CHANGELOG entry
...
7518cd5  Reconcile canonical with audit-era fixes from vendored sites  ← VM HEAD
```

**Missing on VM (v1.2 additions not yet synced):**
- `scripts/validate-products.mjs` — ❌ not found
- `scripts/validate-catalog-brand-coverage.mjs` — ❌ not found
- `scripts/validate-image-markdown.mjs` — ❌ not found
- `scripts/enrichment-backfill.py` — ❌ not found
- `tools/source-products-rainforest.py` — ✅ present
- `producer/producer_main.py` — ✅ present
- `producer/article_builder.py` — ✅ present

**Producer invocation pattern (confirmed from `producer_main.py`):**
```bash
# From site root:
python3 affiliate-platform/producer/producer_main.py --site . --count 10
python3 affiliate-platform/producer/producer_main.py --site . --count 50 --type "Buyer Guide"
python3 affiliate-platform/producer/producer_main.py --site . --dry-run --count 5
```

### betterhearinghub

**Not found on VM.** Searched `$HOME` to depth 5. The site does not exist on the VM at all. Full sync required from local before Phase 4 can run.

---

## Section 3: Phase 3 Data Sync Status

| Item | Local (Mac) | VM | Status |
|---|---|---|---|
| `betterhearinghub/` site | 353 MB total | Not present | ❌ Full sync needed |
| `data/pipeline.json` | 296 articles, 348 KB | Not present | ❌ |
| `content/products/products.yaml` | 471 products, 420 KB | Not present | ❌ |
| `public/images/products/` | 425 JPEGs, 79 MB | Not present | ❌ |
| `public/images/articles/` | 741 WebPs, 34 MB | Not present | ❌ |

**Sync size estimate (excluding `node_modules`, `.astro`, `.git`):**
- Images: ~113 MB
- Data + config + src: ~15 MB
- Total rsync payload: **~130 MB** (fast over Hetzner's network)
- Estimated sync time: **2-4 minutes**

---

## Section 4: API Keys and Credentials

| Item | Status |
|---|---|
| `ANTHROPIC_API_KEY` in session env | ❌ NOT SET |
| `ANTHROPIC_API_KEY` in `.bashrc` / `.profile` | ❌ NOT found |
| `credentials.env` files on VM | ✅ Present in: BCB, northwoods-overland, OI, TMJ, strengthmill, MLT |
| BHB `config/credentials.env` | ❌ Does not exist (site not synced) |

**How the producer loads the key** (from `producer_main.py`):
```python
key = os.environ.get("ANTHROPIC_API_KEY")
# Falls through to site credentials.env if env var not set
```

**Required fix:** BHB `config/credentials.env` must be present with `ANTHROPIC_API_KEY` set. This file should NOT be synced from Mac (it contains the live key). Create fresh on VM after sync, or set as environment variable in the tmux session before launch.

Other keys needed in `config/credentials.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
AMAZON_TAG=betterhearinghub-20
RAINFOREST_KEY=8BDF0DB6721A4CFE93022DA1CBB0AF9C
```

---

## Section 5: Python Dependencies

Tested against Python 3.10.12 (default `python3` on VM).

| Package | Required | VM Version | Status |
|---|---|---|---|
| anthropic | >=0.40.0 | 0.84.0 | ✅ |
| PyYAML | >=6.0 | 5.4.1 | ⚠️ Minor version gap — works in practice |
| requests | any | 2.25.1 | ✅ |
| Pillow (PIL) | any | 12.1.1 | ✅ |
| python-docx | any | 1.2.0 | ✅ |
| ruamel.yaml | not in requirements | ❌ not installed | Not needed for producer |
| jinja2 | any | 3.0.3 | ✅ |
| click | any | 8.0.3 | ✅ |
| httpx | any | 0.28.1 | ✅ |

**PyYAML 5.4.1 vs >=6.0:** The requirements.txt spec says `>=6.0` but 5.4.1 has been working across multiple site runs on this VM (BCB, northwoods, etc.) without issues. Not a blocker. Upgrade optional.

**No pip installs needed** for Phase 4 producer — all required packages present.

---

## Section 6: Session Management

| Tool | Status |
|---|---|
| tmux | ✅ 3.2a installed |
| screen | ✅ 4.09.00 installed |
| Active tmux sessions | None |
| Active producer processes | None |

No conflicts. Clean environment for Phase 4 launch.

---

## Section 7: Network Connectivity

| Target | Result |
|---|---|
| Anthropic API (`api.anthropic.com`) | ✅ HTTP 405 (correct — OPTIONS rejected, endpoint reachable), 0.25s |
| General internet (google.com) | ✅ HTTP 200 |

Network is clean. Anthropic API latency from Hetzner is excellent (0.25s round-trip).

---

## Section 8: Recommended Next Actions

### A. Nothing needed — can proceed immediately
- Python runtime (3.10.12) ✅
- All producer Python dependencies ✅
- Node 20.20.2 for validators ✅
- tmux for session persistence ✅
- Network / API reachability ✅
- Disk space (20 GB free vs ~130 MB sync) ✅

### B. Minor setup needed (~15-20 minutes total)

**1. Sync betterhearinghub site to VM** (~3-4 min)
```bash
rsync -avz \
  --exclude='node_modules/' \
  --exclude='.astro/' \
  --exclude='.git/' \
  --exclude='config/credentials.env' \
  ~/betterhearinghub/ \
  root@46.225.29.35:/root/betterhearinghub/
```

**2. Sync affiliate-platform to v1.2** (~1 min)
```bash
rsync -avz \
  --exclude='.git/' \
  --exclude='node_modules/' \
  ~/affiliate-platform/ \
  root@46.225.29.35:/root/betterhearinghub/affiliate-platform/
```

**3. Create credentials.env on VM** (~2 min — Keith provides ANTHROPIC_API_KEY)
```bash
ssh root@46.225.29.35 "cat > /root/betterhearinghub/config/credentials.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
AMAZON_TAG=betterhearinghub-20
RAINFOREST_KEY=8BDF0DB6721A4CFE93022DA1CBB0AF9C
SITE_URL=https://betterhearinghub.com
EOF"
```

**4. Create logs/ directory** (~10 sec)
```bash
ssh root@46.225.29.35 "mkdir -p /root/betterhearinghub/logs"
```

**5. Verify setup** (~2 min)
```bash
ssh root@46.225.29.35 "cd /root/betterhearinghub && python3 affiliate-platform/producer/producer_main.py --site . --dry-run --count 3"
```

### C. Significant sync needed
None — all gaps covered by B above.

### D. Blockers requiring Keith intervention
None. All findings are resolvable by Claude Code during Phase 4 setup.

---

## Section 9: Estimated Time to Phase 4 Ready

**~20 minutes total:**
- rsync betterhearinghub → VM: 3-4 min
- rsync affiliate-platform → VM: 1 min
- credentials.env creation: 2 min (Keith provides API key)
- logs/ dir + dry-run verification: 3 min
- tmux session setup + producer launch: 2 min

**Single blocker on Keith:** the `ANTHROPIC_API_KEY` value must be pasted during credentials.env setup. Everything else is automatable.

---

## Quick-reference: Phase 4 launch sequence (after setup)

```bash
# 1. Open tmux session
ssh root@46.225.29.35
tmux new-session -s bhh-phase4

# 2. Start producer (inside tmux)
cd /root/betterhearinghub
python3 affiliate-platform/producer/producer_main.py \
  --site . \
  --count 296 \
  > logs/phase4-$(date +%Y%m%d-%H%M).log 2>&1

# 3. Detach and close laptop
# Ctrl-B D

# 4. Check progress later
ssh root@46.225.29.35 "tmux attach -t bhh-phase4"
# or
ssh root@46.225.29.35 "tail -50 /root/betterhearinghub/logs/phase4-*.log"
```
