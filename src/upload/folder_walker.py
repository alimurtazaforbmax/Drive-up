"""Cross-platform folder walking with skip rules."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.config.settings import DEFAULT_SKIP_NAMES, DEFAULT_SKIP_SUFFIXES

logger = logging.getLogger(__name__)


@dataclass
class WalkResult:
    """Files discovered under a root folder."""

    root: Path
    files: list[Path] = field(default_factory=list)
    total_bytes: int = 0
    skipped: list[str] = field(default_factory=list)


class FolderWalker:
    """Walk a local folder tree in an OS-agnostic way using pathlib."""

    def __init__(
        self,
        skip_names: frozenset[str] | None = None,
        skip_suffixes: frozenset[str] | None = None,
    ) -> None:
        self._skip_names = skip_names or DEFAULT_SKIP_NAMES
        self._skip_suffixes = skip_suffixes or DEFAULT_SKIP_SUFFIXES

    def should_skip_name(self, name: str) -> bool:
        if name in self._skip_names:
            return True
        lower = name.lower()
        if lower in {n.lower() for n in self._skip_names}:
            return True
        for suffix in self._skip_suffixes:
            if name.endswith(suffix) or lower.endswith(suffix.lower()):
                return True
        return False

    def walk(self, root: Path) -> WalkResult:
        """Return all uploadable files under root (resolved absolute path)."""
        try:
            resolved = root.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise FileNotFoundError(f"Cannot resolve folder {root}: {exc}") from exc

        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {resolved}")

        result = WalkResult(root=resolved)
        for dirpath, dirnames, filenames in self._walk_dirs(resolved):
            # Prune skipped directories in-place so os.walk-style traversal skips them
            dirnames[:] = [d for d in dirnames if not self.should_skip_name(d)]
            current = Path(dirpath)
            for filename in filenames:
                if self.should_skip_name(filename):
                    result.skipped.append(str(current / filename))
                    continue
                file_path = current / filename
                try:
                    if not file_path.is_file():
                        continue
                    size = file_path.stat().st_size
                except OSError as exc:
                    logger.warning("Skipping unreadable file %s: %s", file_path, exc)
                    result.skipped.append(str(file_path))
                    continue
                result.files.append(file_path)
                result.total_bytes += size
        return result

    def relative_parts(self, root: Path, file_path: Path) -> tuple[str, ...]:
        """
        Parent folder parts relative to root (excluding the file name).

        Uses POSIX-style logical parts for Drive folder names regardless of OS.
        """
        rel = file_path.relative_to(root)
        parents = rel.parts[:-1]
        return parents

    @staticmethod
    def _walk_dirs(root: Path):
        """Yield (dirpath, dirnames, filenames) like os.walk via pathlib."""
        # Use os.walk through Path for performance / symlink control
        import os

        yield from os.walk(root, followlinks=False)
