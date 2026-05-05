# PhotoDuplicatorApp

A desktop app for Windows that finds duplicate and near-identical photos in a folder (and all its subfolders) and lets you review pairs side-by-side, choosing which to delete. Deleted files are sent to the **Recycle Bin** so you can restore them if you change your mind.

## Features

- Pick any folder; recursively scans every subfolder.
- Detects visual duplicates using **perceptual hashing (pHash)** — catches identical photos even after minor edits like resize, recompression, or slight color shifts.
- Only shows pairs that are **≥ 90% similar** (configurable in `duplicate_finder.py`).
- Side-by-side comparison with full path, filename, and file size.
- One-click delete sends the file to the Recycle Bin (recoverable).

## Requirements

- Windows 10 or 11
- Python 3.10 or newer ([download](https://www.python.org/downloads/) — during install, **check "Add Python to PATH"**)

## Quick start

1. **First time only**: double-click `setup.bat`. This creates a virtual environment and installs the dependencies.
2. **Every time after**: double-click `run.bat`.

## How it works

1. **Welcome screen** → choose a mode:
   - **Scan One Folder** — walks one folder (and subfolders) and finds duplicates inside it.
   - **Compare Two Folders** — walks both folders (and subfolders), then finds duplicates *across* them and *within* each. Useful for comparing, e.g., a OneDrive photo library against an external-drive backup.
2. **Scanning** → the app walks the folder tree(s), opens each image, and computes a 64-bit perceptual hash. If the two folders overlap (one contains the other), files are deduplicated by real path so they aren't scanned twice.
3. **Comparison** → every image is compared to every other image; pairs whose hashes differ by ≤ 6 bits (≥ 90.6% similarity) are flagged.
4. **Grouping** → pairs are merged into **groups** via transitive closure (if A is similar to B and B is similar to C, all three end up in the same group). Each photo is therefore reviewed exactly once, no matter how many of its neighbors are also similar.
5. **Review** → groups are shown one at a time, sorted with the highest-similarity match first. The whole group is laid out in a grid; under each photo you can:
   - **Delete this one** — sends that single photo to the Recycle Bin. The group view refreshes with the deleted photo removed; the rest of the group stays visible so you can keep deleting.
   - **Skip This Group →** — keeps every photo in the group and moves on.
   - **Stop Reviewing** — ends the session and shows a summary.

When fewer than two photos remain in a group (because you deleted enough), the app moves on automatically.

## Project structure

```
PhotoDuplicatorApp/
├── main.py                  Entry point
├── gui.py                   PySide6 windows and pages
├── duplicate_finder.py      Folder walk + perceptual hashing + pair comparison
├── requirements.txt         Python dependencies
├── setup.bat                One-time installer (creates venv, installs deps)
├── run.bat                  Launcher (activates venv, runs the app)
├── .gitignore
└── README.md
```

## Tuning the similarity threshold

The threshold lives at the top of `duplicate_finder.py`:

```python
SIMILARITY_THRESHOLD_PERCENT = 90.0
```

- Higher (e.g. 95) → fewer, more-confident matches.
- Lower (e.g. 80) → more matches, including some loose visual similarities.

## Supported image formats

`.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.png`, `.bmp`, `.gif`, `.webp`, `.tif`, `.tiff`

## Safety notes

- Deletions go to the **Recycle Bin** via `send2trash`. They are not immediately permanent.
- The app never modifies images; it only reads them and (on confirmation) sends one of a pair to the Recycle Bin.
