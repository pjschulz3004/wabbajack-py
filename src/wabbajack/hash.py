"""Hash verification for Wabbajack archives.

Wabbajack uses xxHash64 encoded as base64. This module computes and compares
hashes, but NEVER blocks on mismatch -- it informs the user and lets them decide.
"""
import base64, logging
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False
    log.debug("xxhash not installed -- hash verification disabled (pip install xxhash)")

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks -- xxHash64 is 10+ GB/s, I/O is the bottleneck


def compute_xxhash64_b64(file_path):
    """Compute xxHash64 of a file and return as base64 string (Wabbajack format)."""
    if not HAS_XXHASH:
        return None
    h = xxhash.xxh64()
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return base64.b64encode(h.digest()).decode('ascii')


def verify_archive(file_path, expected_hash, archive_name=None):
    """Verify a downloaded archive's hash against the expected value.

    Returns a VerifyResult with .ok, .expected, .actual, and .message fields.
    Never raises -- mismatches are warnings, not errors.
    """
    label = archive_name or Path(file_path).name

    if not HAS_XXHASH:
        return VerifyResult(True, expected_hash, None,
                            f"[skip] {label}: xxhash not installed")

    if not expected_hash:
        return VerifyResult(True, None, None,
                            f"[skip] {label}: no expected hash")

    actual = compute_xxhash64_b64(file_path)
    if actual == expected_hash:
        log.debug(f"[ok] {label}: hash matches ({actual})")
        return VerifyResult(True, expected_hash, actual, f"[ok] {label}")

    log.warning(f"[MISMATCH] {label}: expected {expected_hash}, got {actual}")
    return VerifyResult(False, expected_hash, actual,
                        f"[MISMATCH] {label}: expected {expected_hash}, got {actual}")


class VerifyResult:
    __slots__ = ('ok', 'expected', 'actual', 'message')

    def __init__(self, ok, expected, actual, message):
        self.ok = ok
        self.expected = expected
        self.actual = actual
        self.message = message

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return self.message
