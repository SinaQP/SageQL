"""Digest of a frozen evaluation input, independent of checkout line endings.

Git may check text files out with CRLF on Windows and LF elsewhere. Frozen
manifests record the digest of the LF content so every checkout verifies.
"""
from hashlib import sha256


def file_digest(path):
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
