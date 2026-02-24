"""Prompts for the insights agent."""

import os


def load_narrative_prompt(version: str = "v1") -> str:
    """Load the narrative prompt template by version.

    Args:
        version: Prompt version to load (e.g. "v1", "v2"). Corresponds to a
                 markdown file in this directory.

    Returns:
        Raw prompt template string with {insight_type}, {summary}, {metrics}
        placeholders ready for .format() substitution.
    """
    with open(os.path.join(os.path.dirname(__file__), f"{version}.md"), "r") as f:
        return f.read()
