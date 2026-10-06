"""Fixed name matching normalization, distinct from literal reporting filters."""

NAME_REPLACEMENTS = (("ي", "ی"), ("ك", "ک"), (" ", ""), ("\u200c", ""),
                     ("\t", ""), ("\r", ""), ("\n", ""), ("\u00a0", ""))


def normalize_name(value: str) -> str:
    for original, replacement in NAME_REPLACEMENTS:
        value = value.replace(original, replacement)
    return value
