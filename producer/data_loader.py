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
        return json.load(f)


def load_products(site_root: Path) -> dict:
    """Returns dict keyed by product slug."""
    with open(site_root / "content/products/products.yaml") as f:
        raw = yaml.safe_load(f) or {}
    products = {}
    for key, p in raw.items():
        p["key"] = key
        if isinstance(p.get("last_verified"), date):
            p["last_verified"] = p["last_verified"].isoformat()
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
    return [a for a in pipeline if not a.get("published", False)]


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


def get_hub_products(products: dict, hub_slug: str) -> dict:
    return {k: v for k, v in products.items() if v.get("hub") == hub_slug}


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
    with open(tmp, "w") as f:
        json.dump(pipeline, f, indent=2)
    if path.exists():
        shutil.copy2(path, bak)
    os.replace(tmp, path)
