from urllib.parse import urlsplit


def is_safe_redirect_target(target):
    """
    True only for a same-site relative path such as "/dashboard?x=1".
    Rejects absolute URLs, scheme-relative "//evil.example", backslash
    tricks browsers normalise to "//", and anything with control
    characters -- the usual open-redirect bypasses for a ?next= value.
    """

    if not target or not isinstance(target, str):
        return False

    if not target.startswith("/") or target.startswith("//"):
        return False

    if "\\" in target or any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
        return False

    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc
