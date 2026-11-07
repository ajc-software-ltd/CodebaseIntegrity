"""File hashing.

Content fingerprints are SHA-256 (configurable to "sha256" only for now) and
are computed by streaming the file in chunks — whole files are never loaded
into memory (PLAN.md §7.4, §17.2).
"""

import hashlib
from pathlib import Path

_CHUNK_SIZE = 65536


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """Return the hex digest of a file's content.

    Raises:
        OSError: the file cannot be read.
        ValueError: the algorithm is not supported.
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as error:
        raise ValueError(f"unsupported hash algorithm: {algorithm}") from error
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()
