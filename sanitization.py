# =========================================================
# sanitization.py
# Unicode-safe sanitization for ALL text inputs
# =========================================================
import re

def sanitize(value: str):
    """Remove smart quotes, invisible unicode, control chars, normalize whitespace."""
    if not isinstance(value, str):
        return value

    replacements = {
        "“": '"', "”": '"',
        "‘": "'", "’": "'",
        "–": "-", "—": "-",
        "•": "-", "…": "...",
        "\u00a0": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)

    # Remove ASCII control characters
    value = re.sub(r"[\x00-\x1F\x7F]", "", value)

    return value.strip()


def sanitize_payload(payload: dict):
    """Sanitize every string field inside a data dict."""
    clean = {}
    for k, v in payload.items():
        clean[k] = sanitize(v) if isinstance(v, str) else v
    return clean
