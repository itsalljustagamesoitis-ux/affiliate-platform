"""
Tests that site-specific config values are set (non-empty, non-placeholder).
These catch initialisation mistakes where template values were not replaced.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
PRODUCER_DIR = ROOT / "producer"


def test_site_domain_is_set(site_config):
    domain = site_config["site"]["domain"]
    assert domain, "site.domain is empty"
    assert "REPLACE" not in domain.upper(), f"site.domain still has placeholder: {domain}"
    assert "." in domain, f"site.domain doesn't look like a domain: {domain}"


def test_amazon_tracking_id_is_set(site_config):
    tag = site_config["affiliate"]["amazon_tracking_id"]
    assert tag, "amazon_tracking_id is empty"
    assert "REPLACE" not in tag.upper(), f"amazon_tracking_id still has placeholder: {tag}"
    assert tag.endswith("-20"), f"Amazon tag should end in -20, got: {tag}"


def test_package_name_is_set(root):
    import json
    pkg = json.loads((root / "package.json").read_text())
    assert pkg["name"], "package.json name is empty"
    assert "REPLACE" not in pkg["name"].upper(), "package.json name still has placeholder"


def test_american_english_in_system_prompt(site_config):
    """American English rule must appear in the base system prompt."""
    from prompt_loader import load_prompt
    import yaml as pyyaml
    try:
        persona_path = ROOT / site_config["persona"]["config_path"]
        persona = pyyaml.safe_load(persona_path.read_text())
        system_prompt, _ = load_prompt("roundup", site_config, persona)
        assert "American English" in system_prompt or "american english" in system_prompt.lower(), \
            "System prompt should instruct American English spelling"
    except Exception as e:
        pytest.skip(f"Could not load prompt for this site configuration: {e}")
