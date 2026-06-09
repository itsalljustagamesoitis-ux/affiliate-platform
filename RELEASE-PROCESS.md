# Platform Release Process

## When to release

A platform release happens when:
- One or more B-bugs are fixed that other sites should inherit
- A new tool, validator, or prompt is added to the platform
- A breaking change requires a version bump

Releases should be incremental — one session's work, one commit. Do not accumulate
multiple sessions of work before committing. If a session ends with uncommitted
platform changes, create a release commit before closing the session.

## Release steps

### 1. Pre-commit hygiene

```bash
# Verify nothing operational is staged
git status --short
# Confirm: no active-launches.yaml, persona-unlock-log.yaml, logs/, launches/, sites/*.state.json
```

### 2. Commit on Mac canonical

```bash
cd /Users/keithlacy/affiliate-platform/

# Bump version in package.json to next version
# Stage all changes (gitignore handles operational exclusions)
git add -A

# Verify staged files — no operational state should appear
git status

# Commit with structured message
git commit -m "release: vX.Y.Z — short description"

# Tag the release
git tag -a vX.Y.Z -m "vX.Y.Z — short description"
```

### 3. Push to remote

```bash
git push origin main
git push origin vX.Y.Z
```

### 4. Sync VM canonical

```bash
ssh root@46.225.29.35 "cd /root/affiliate-platform && git pull && git log --oneline -3"
```

Verify the VM shows the same SHA as Mac:
```bash
# Mac
git rev-parse HEAD

# VM (should match)
ssh root@46.225.29.35 "cd /root/affiliate-platform && git rev-parse HEAD"
```

### 5. Site submodule bumps (separate decision)

For each site pinned to a submodule (Sites 19+), bumping to the new release is a
separate decision per site. Do not bump all sites automatically — only bump a site
when it's about to be worked on or deployed.

Document in portfolio.yaml which platform SHA each site's submodule is pinned to.

---

## Runtime state — never commit

These files are gitignored and must never appear in a release commit:

| File/Pattern | Reason |
|---|---|
| `active-launches.yaml` | Runtime concurrency lock for launch-site.mjs |
| `persona-unlock-log.yaml` | Audit log for persona lock/unlock events |
| `logs/` | Per-session log files |
| `launches/` | Per-launch state directories |
| `sites/*.state.json` | Per-site launch-site state |
| `sites/*/state.yaml` | Per-site launch-site state (nested) |
| `sites/*/decisions.log` | Per-site decision audit logs |

---

## Version numbering

- **Patch (x.y.Z)**: Bug fixes, docs, validator calibration
- **Minor (x.Y.0)**: New tools, new validators, new prompts, new features
- **Major (X.0.0)**: Breaking changes to producer/sourcing contract, site migration required

The launch orchestrator rewrite (v2.3.0 consolidation) would be a major bump under
strict semver. In practice, use judgment — the audience is internal, and version
inflation has costs. Label consolidation commits clearly in the message.

---

## Remote

- Mac canonical: `/Users/keithlacy/affiliate-platform/`
- VM canonical: `/root/affiliate-platform/` (must track Mac via `git pull`)
- Remote: `https://github.com/itsalljustagamesoitis-ux/affiliate-platform.git` (private)
