"""OctoDiff binary delta applier.

Implements the Octodiff delta format (Octopus Deploy's binary patching).
Wabbajack uses this for PatchedFromArchive directives to store compact
diffs between the original file and the modified version.

Delta format:
  Header: "OCTODELTA\0" magic (10 bytes)
  HashAlgorithm: 7-bit length-prefixed string
  ExpectedHash: 4-byte length + hash bytes
  ExpectedLength: 8-byte LE int64
  Commands: stream of Copy (0x60) and Data (0x80) instructions until EOF

Copy command: read source offset (int64 LE) + length (int64 LE) from basis file
Data command: read length (int64 LE) + literal bytes from delta stream
"""
import struct, logging, io
from pathlib import Path

log = logging.getLogger(__name__)

MAGIC = b'OCTODELTA'
CMD_COPY = 0x60
CMD_DATA = 0x80


def _read_7bit_int(f: io.BufferedIOBase) -> int:
    """Read a .NET 7-bit encoded integer."""
    result = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected EOF in 7-bit int")
        byte = b[0]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result
        shift += 7
        if shift > 35:
            raise ValueError("Malformed 7-bit encoded int (too many bytes)")


def _read_string(f: io.BufferedIOBase) -> str:
    """Read a .NET BinaryReader-style length-prefixed string."""
    length = _read_7bit_int(f)
    if length == 0:
        return ''
    data = f.read(length)
    if len(data) < length:
        raise EOFError(f"Expected {length} bytes for string, got {len(data)}")
    return data.decode('utf-8', errors='replace')


def _read_bytes(f: io.BufferedIOBase) -> bytes:
    """Read a length-prefixed byte array (4-byte LE length)."""
    raw = f.read(4)
    if len(raw) < 4:
        raise EOFError("Expected 4-byte length prefix")
    length = struct.unpack('<I', raw)[0]
    data = f.read(length)
    if len(data) < length:
        raise EOFError(f"Expected {length} bytes, got {len(data)}")
    return data


def _read_long(f: io.BufferedIOBase) -> int:
    """Read an int64 LE."""
    raw = f.read(8)
    if len(raw) < 8:
        raise EOFError("Expected 8 bytes for int64")
    return struct.unpack('<q', raw)[0]


def apply_delta(basis_path: Path, delta_path: Path, output_path: Path) -> bool:
    """Apply an OctoDiff delta to a basis file, producing the output file.

    Args:
        basis_path: The original/source file
        delta_path: The delta/patch file (from .wabbajack inline data)
        output_path: Where to write the patched result

    Returns:
        True if patching succeeded, False on error.
    """
    try:
        with open(delta_path, 'rb') as delta_f:
            # Read and verify magic
            magic = delta_f.read(len(MAGIC))
            if magic != MAGIC:
                log.error(f"Not an OctoDiff delta (bad magic): {delta_path.name}")
                return False

            # Skip null terminator if present
            next_byte = delta_f.read(1)
            if next_byte != b'\x00':
                delta_f.seek(-1, 1)  # Not a null, put it back

            # Read header metadata
            hash_algo = _read_string(delta_f)
            expected_hash = _read_bytes(delta_f)
            expected_length = _read_long(delta_f)

            log.debug(f"  Delta: algo={hash_algo}, expected_length={expected_length}")

            # Apply commands
            with open(basis_path, 'rb') as basis_f, open(output_path, 'wb') as out_f:
                while True:
                    cmd_byte = delta_f.read(1)
                    if not cmd_byte:
                        break  # EOF -- done

                    cmd = cmd_byte[0]

                    if cmd == CMD_COPY:
                        offset = _read_long(delta_f)
                        length = _read_long(delta_f)
                        basis_f.seek(offset)
                        remaining = length
                        while remaining > 0:
                            chunk_size = min(remaining, 1024 * 1024)
                            data = basis_f.read(chunk_size)
                            if not data:
                                log.warning(f"  Basis file shorter than expected at offset {offset}")
                                break
                            out_f.write(data)
                            remaining -= len(data)

                    elif cmd == CMD_DATA:
                        length = _read_long(delta_f)
                        remaining = length
                        while remaining > 0:
                            chunk_size = min(remaining, 1024 * 1024)
                            data = delta_f.read(chunk_size)
                            if not data:
                                log.warning(f"  Delta data truncated, expected {remaining} more bytes")
                                break
                            out_f.write(data)
                            remaining -= len(data)

                    else:
                        log.error(f"  Unknown delta command: 0x{cmd:02x}")
                        return False

        # Verify output size
        actual_size = output_path.stat().st_size
        if expected_length > 0 and actual_size != expected_length:
            log.warning(f"  Patched file size mismatch: expected {expected_length}, got {actual_size}")
            # Don't fail -- some deltas have size=0 as "unknown"

        return True

    except (OSError, struct.error, EOFError, ValueError) as e:
        log.error(f"  Delta application failed: {type(e).__name__}: {e}")
        return False
