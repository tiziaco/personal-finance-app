import os


def load_categorization_prompt(version: str = "v1") -> str:
    """Load the categorization prompt template by version.

    Args:
        version: Prompt version to load (e.g. "v1", "v2"). Corresponds to a
                 markdown file in this directory.

    Returns:
        Raw prompt template string with {categories}, {keywords_section}, and
        {transactions} placeholders ready for .format() substitution.
    """
    path = os.path.join(os.path.dirname(__file__), f"{version}.md")
    with open(path) as f:
        return f.read()
