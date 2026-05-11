"""
Site prompt_loader override.
Delegates to the platform loader then reinforces the Buying Guide word count floor,
which the LLM frequently underruns without an explicit reminder.
"""
import importlib.util
from pathlib import Path


def _platform_load_prompt(article_type, site_config, persona):
    """Load the platform prompt_loader by file path to avoid module-cache conflicts."""
    platform_path = Path(__file__).parent.parent / "affiliate-platform/producer/prompt_loader.py"
    spec = importlib.util.spec_from_file_location("_platform_prompt_loader", platform_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_prompt(article_type, site_config, persona)


_BUYING_GUIDE_REMINDER = (
    "\n\n**WORD COUNT CHECK — BUYING GUIDE SECTION:** "
    "Before finalizing, count the words in your ## Buying Guide section. "
    "It must total 500–700 words across all H3 subsections. "
    "If it falls below 500, add one additional specific, decision-relevant sentence "
    "to the thinnest subsection — a genuine point, not padding."
)


def load_prompt(article_type: str, site_config: dict, persona: dict) -> tuple:
    system_text, metadata = _platform_load_prompt(article_type, site_config, persona)
    if system_text and article_type.lower().replace(" ", "_") == "buyer_guide":
        system_text += _BUYING_GUIDE_REMINDER
    return system_text, metadata
