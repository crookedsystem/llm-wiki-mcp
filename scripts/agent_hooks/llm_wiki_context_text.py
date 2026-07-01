from __future__ import annotations

import re


def clean_context_text(value: object) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("]]", "] ]")
        .replace("[[", "[ [")
    )
