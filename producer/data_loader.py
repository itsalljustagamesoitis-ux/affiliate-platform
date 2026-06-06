"""
Data loader for platform producer.
All functions accept site_root: Path so they work for any consuming site.
"""

import json
import os
import shutil
import yaml
from datetime import date
from pathlib import Path
from typing import Optional


def load_pipeline(site_root: Path) -> list:
    with open(site_root / "data/pipeline.json") as f:
        data = json.load(f)
    articles = data.get("articles", []) if isinstance(data, dict) else data
    # Deduplicate product lists in place — source tools occasionally assign same key twice
    for a in articles:
        if isinstance(a.get("products"), list):
            seen = []
            for p in a["products"]:
                if p not in seen:
                    seen.append(p)
            a["products"] = seen
    return articles


def load_products(site_root: Path) -> dict:
    """Returns dict keyed by product slug."""
    with open(site_root / "content/products/products.yaml") as f:
        raw = yaml.safe_load(f) or {}
    products = {}
    for key, p in raw.items():
        p["key"] = key
        if isinstance(p.get("last_verified"), date):
            p["last_verified"] = p["last_verified"].isoformat()
        # Rainforest-sourced products use 'title'; platform builder expects 'name'
        if "name" not in p and "title" in p:
            p["name"] = p["title"]
        # Platform builder uses 'amazon_asin'; Rainforest uses 'asin'
        if "amazon_asin" not in p and "asin" in p:
            p["amazon_asin"] = p["asin"]
        if "default_pros" not in p:
            p["default_pros"] = []
        if "default_cons" not in p:
            p["default_cons"] = []
        products[key] = p
    return products


def load_persona(site_root: Path) -> dict:
    with open(site_root / "site.config.yaml") as f:
        cfg = yaml.safe_load(f)
    persona_path = site_root / cfg["persona"]["config_path"]
    with open(persona_path) as f:
        return yaml.safe_load(f)


def load_eeat_vault(site_root: Path) -> dict:
    with open(site_root / "data/eeat-vault.json") as f:
        return json.load(f)


def load_navigation(site_root: Path) -> dict:
    with open(site_root / "config/navigation.yaml") as f:
        return yaml.safe_load(f)


def load_site_config(site_root: Path) -> dict:
    with open(site_root / "site.config.yaml") as f:
        return yaml.safe_load(f)


def get_pending_articles(pipeline: list) -> list:
    return [a for a in pipeline if not a.get("published", False) and a.get("status") != "skip"]


def enrich_article(article: dict, nav: dict) -> dict:
    """Attach hub_label, hub_url, hub_slug, category_label, category_slug."""
    hub_slug = article.get("hub", "")
    for cat in nav.get("categories", []):
        for hub in cat.get("hubs", []):
            if hub["slug"] == hub_slug:
                article["hub_label"] = hub["label"]
                article["hub_url"] = f"/{hub_slug}/"
                article["hub_slug"] = hub_slug
                article["category_label"] = cat["label"]
                article["category_slug"] = cat["slug"]
                return article
    article.setdefault("hub_label", hub_slug.replace("-", " ").title())
    article.setdefault("hub_url", f"/{hub_slug}/")
    article.setdefault("hub_slug", hub_slug)
    article.setdefault("category_label", "")
    article.setdefault("category_slug", "")
    return article


def product_matches_hub(product: dict, hub_slug: str) -> bool:
    """True when product belongs to the given hub (supports both hub: str and hubs: [list])."""
    hubs = product.get("hubs")
    if isinstance(hubs, list):
        return hub_slug in hubs
    return product.get("hub") == hub_slug


def get_hub_products(products: dict, hub_slug: str) -> dict:
    return {k: v for k, v in products.items() if product_matches_hub(v, hub_slug)}


def get_article_by_id(pipeline: list, article_id: int) -> Optional[dict]:
    return next((a for a in pipeline if a["id"] == article_id), None)


def get_article_by_slug(pipeline: list, slug: str) -> Optional[dict]:
    return next((a for a in pipeline if a["slug"] == slug), None)


def get_eeat_for_cluster(vault: dict, cluster: str) -> dict:
    experiences = [e for e in vault.get("product_experiences", []) if cluster in e.get("clusters", [])]
    failures = [f for f in vault.get("failures", []) if cluster in f.get("clusters", [])]
    opinions = [o for o in vault.get("strong_opinions", []) if cluster in o.get("clusters", [])]
    return {
        "experiences": experiences[:3],
        "failures": failures[:2],
        "opinions": opinions[:2],
    }


def save_pipeline(pipeline: list, site_root: Path) -> None:
    path = site_root / "data/pipeline.json"
    tmp = path.with_suffix(".json.tmp")
    bak = path.with_suffix(".json.bak")
    try:
        with open(path) as f:
            existing = json.load(f)
    except Exception:
        existing = {}

    # Merge mutable status fields from in-memory pipeline into the current on-disk
    # version, so external edits made during a run (skip flags, product changes) survive.
    if isinstance(existing, dict):
        disk_articles = existing.get("articles", [])
    else:
        disk_articles = existing if isinstance(existing, list) else []

    mem_by_id = {a["id"]: a for a in pipeline}
    merged = []
    for disk_a in disk_articles:
        mem_a = mem_by_id.get(disk_a["id"])
        if mem_a is not None:
            for key in ("status", "staged", "published", "fail_count"):
                if key in mem_a:
                    disk_a[key] = mem_a[key]
        merged.append(disk_a)

    if isinstance(existing, dict):
        existing["articles"] = merged
        data = existing
    else:
        data = merged

    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    if path.exists():
        shutil.copy2(path, bak)
    os.replace(tmp, path)
