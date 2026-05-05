"""Recursive image scanner that finds visually similar photos via perceptual hashing."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError
import imagehash
from PySide6.QtCore import QThread, Signal


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png", ".bmp", ".gif", ".webp",
    ".tif", ".tiff",
}

HASH_SIZE = 8
TOTAL_BITS = HASH_SIZE * HASH_SIZE
SIMILARITY_THRESHOLD_PERCENT = 90.0
MAX_HAMMING_DISTANCE = int(round(TOTAL_BITS * (1 - SIMILARITY_THRESHOLD_PERCENT / 100)))


def _enumerate_images(root_folders: list[str]) -> list[str]:
    """Walk every folder, collect image files, deduplicate by case-folded realpath."""
    seen: set[str] = set()
    files: list[str] = []
    for root in root_folders:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if Path(fn).suffix.lower() in IMAGE_EXTENSIONS:
                    full = os.path.normpath(os.path.join(dirpath, fn))
                    try:
                        key = os.path.realpath(full).lower()
                    except OSError:
                        key = full.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    files.append(full)
    return files


class ScanWorker(QThread):
    """Background worker that scans one or more folders, hashes images, and reports similar pairs."""

    progress = Signal(int, int, str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, folders: list[str], parent=None):
        super().__init__(parent)
        self.folders = list(folders)
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            files = _enumerate_images(self.folders)
            total = len(files)
            if total == 0:
                self.finished_ok.emit([])
                return

            hashes: list[tuple[str, imagehash.ImageHash]] = []
            for i, path in enumerate(files, start=1):
                if self._cancel:
                    return
                self.progress.emit(i, total, f"Scanning {i}/{total}: {os.path.basename(path)}")
                try:
                    with Image.open(path) as img:
                        img.draft("RGB", (256, 256))
                        h = imagehash.phash(img, hash_size=HASH_SIZE)
                    hashes.append((path, h))
                except (UnidentifiedImageError, OSError, ValueError):
                    continue

            n = len(hashes)
            if n < 2:
                self.finished_ok.emit([])
                return

            duplicates: list[tuple[str, str, float]] = []
            total_pairs = n * (n - 1) // 2
            done = 0
            report_every = max(1, total_pairs // 100)
            for i in range(n):
                if self._cancel:
                    return
                path_a, hash_a = hashes[i]
                for j in range(i + 1, n):
                    done += 1
                    if done % report_every == 0:
                        self.progress.emit(done, total_pairs, f"Comparing pairs {done}/{total_pairs}")
                    path_b, hash_b = hashes[j]
                    distance = hash_a - hash_b
                    if distance <= MAX_HAMMING_DISTANCE:
                        similarity = (1 - distance / TOTAL_BITS) * 100
                        duplicates.append((path_a, path_b, similarity))

            duplicates.sort(key=lambda t: t[2], reverse=True)
            self.finished_ok.emit(duplicates)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
