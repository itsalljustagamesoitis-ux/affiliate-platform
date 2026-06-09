"""Shared test fixtures for the site producer."""

import sys
import json
import yaml
import pytest
from pathlib import Path

_cwd = Path.cwd()
ROOT = _cwd if (_cwd / "site.config.yaml").exists() else Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))  # always add producer/ to path


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def site_config():
    with open(ROOT / "site.config.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def navigation():
    with open(ROOT / "config/navigation.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def pipeline():
    with open(ROOT / "data/pipeline.json") as f:
        data = json.load(f)
    return data.get("articles", data) if isinstance(data, dict) else data


@pytest.fixture(scope="session")
def products():
    from data_loader import load_products
    return load_products(ROOT)


@pytest.fixture(scope="session")
def all_hub_slugs(navigation):
    slugs = set()
    for cat in navigation.get("categories", []):
        for hub in cat.get("hubs", []):
            slugs.add(hub["slug"])
    return slugs


@pytest.fixture(scope="session")
def image_dir(root):
    return root / "public/images/articles"


@pytest.fixture(scope="session")
def pipeline_hub_slugs(pipeline):
    """Hub slugs that actually appear in pipeline.json — a subset of all nav hubs."""
    slugs = set()
    for a in pipeline:
        hub = a.get("hub_slug") or a.get("hub", "")
        if hub:
            slugs.add(hub)
    return slugs
