"""PySide6 GUI for PhotoDuplicatorApp: pick a folder, scan, review pairs, delete to Recycle Bin."""

from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash

from duplicate_finder import ScanWorker, SIMILARITY_THRESHOLD_PERCENT


PREVIEW_SIZE = QSize(420, 420)


def _forbidden_roots() -> list[str]:
    """System paths the app refuses to scan (case-insensitive prefix match)."""
    candidates = [
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        r"C:\System Volume Information",
        r"C:\$Recycle.Bin",
        r"C:\Recovery",
        r"C:\PerfLogs",
        r"C:\Boot",
    ]
    return [os.path.normpath(p).lower() for p in candidates if p]


def is_forbidden_folder(path: str) -> tuple[bool, str]:
    """Return (forbidden, reason). Refuses drive roots and system locations."""
    norm = os.path.normpath(path).lower()
    if re.fullmatch(r"[a-z]:\\?", norm):
        return True, "Scanning a whole drive root is not allowed. Pick a specific subfolder."
    for forbidden in _forbidden_roots():
        if norm == forbidden or norm.startswith(forbidden + os.sep):
            return True, f"This is a Windows system location and is not allowed:\n{forbidden}"
    return False, ""


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


class PhotoColumn(QFrame):
    """One side of the comparison view: preview + path + name + size + delete button."""

    def __init__(self, on_delete):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(1)
        self._path: str | None = None

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(PREVIEW_SIZE)
        self.preview.setStyleSheet("background-color: #1e1e1e; color: #888;")
        self.preview.setText("(no image)")

        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        self.name_label.setFont(name_font)

        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #555;")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.size_label = QLabel()
        self.size_label.setStyleSheet("color: #555;")

        self.delete_btn = QPushButton("Delete this one")
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; padding: 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:disabled { background-color: #888; }"
        )
        self.delete_btn.clicked.connect(lambda: on_delete(self._path))

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.name_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.size_label)
        layout.addWidget(self.delete_btn)

    def set_image(self, path: str) -> None:
        self._path = path
        self.name_label.setText(os.path.basename(path))
        self.path_label.setText(path)
        try:
            size_text = human_size(os.path.getsize(path))
        except OSError:
            size_text = "(size unavailable)"
        self.size_label.setText(f"Size: {size_text}")

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText("(cannot preview)")
        else:
            scaled = pixmap.scaled(
                PREVIEW_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview.setPixmap(scaled)

    def clear(self) -> None:
        self._path = None
        self.preview.clear()
        self.preview.setText("(no image)")
        self.name_label.clear()
        self.path_label.clear()
        self.size_label.clear()


class WelcomePage(QWidget):
    def __init__(self, on_pick):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("PhotoDuplicatorApp")
        title.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            f"Find duplicate or near-identical photos (≥ {SIMILARITY_THRESHOLD_PERCENT:.0f}% similarity)\n"
            "in any folder, including subfolders."
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #555;")

        pick_btn = QPushButton("Choose Folder to Scan…")
        pick_btn.setMinimumHeight(50)
        pick_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; padding: 12px 24px; font-size: 14pt; }"
            "QPushButton:hover { background-color: #3498db; }"
        )
        pick_btn.clicked.connect(on_pick)

        layout.addStretch()
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addWidget(pick_btn, 0, Qt.AlignCenter)
        layout.addStretch()


class ScanPage(QWidget):
    def __init__(self, on_cancel):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.heading = QLabel("Scanning…")
        self.heading.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        self.heading.setFont(f)

        self.status = QLabel("Starting…")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(600)

        self.bar = QProgressBar()
        self.bar.setMinimumWidth(600)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(on_cancel)

        layout.addStretch()
        layout.addWidget(self.heading)
        layout.addSpacing(16)
        layout.addWidget(self.status)
        layout.addSpacing(8)
        layout.addWidget(self.bar)
        layout.addSpacing(16)
        layout.addWidget(cancel_btn, 0, Qt.AlignCenter)
        layout.addStretch()

    def update_progress(self, current: int, total: int, message: str) -> None:
        self.bar.setMaximum(max(total, 1))
        self.bar.setValue(current)
        self.status.setText(message)


class ReviewPage(QWidget):
    def __init__(self, on_skip, on_done, on_delete):
        super().__init__()
        self._on_skip = on_skip
        self._on_done = on_done

        outer = QVBoxLayout(self)

        self.header = QLabel()
        self.header.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        self.header.setFont(f)
        outer.addWidget(self.header)

        cols = QHBoxLayout()
        self.left = PhotoColumn(on_delete)
        self.right = PhotoColumn(on_delete)
        cols.addWidget(self.left)
        cols.addWidget(self.right)
        outer.addLayout(cols, 1)

        controls = QHBoxLayout()
        self.skip_btn = QPushButton("Keep Both / Skip →")
        self.skip_btn.setMinimumHeight(40)
        self.skip_btn.clicked.connect(on_skip)
        self.done_btn = QPushButton("Stop Reviewing")
        self.done_btn.setMinimumHeight(40)
        self.done_btn.clicked.connect(on_done)
        controls.addStretch()
        controls.addWidget(self.skip_btn)
        controls.addSpacing(20)
        controls.addWidget(self.done_btn)
        controls.addStretch()
        outer.addLayout(controls)

    def show_pair(self, index: int, total: int, path_a: str, path_b: str, similarity: float) -> None:
        self.header.setText(
            f"Pair {index + 1} of {total}   ·   Similarity: {similarity:.1f}%"
        )
        self.left.set_image(path_a)
        self.right.set_image(path_b)


class FinishedPage(QWidget):
    def __init__(self, on_restart):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.heading = QLabel()
        self.heading.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(18)
        f.setBold(True)
        self.heading.setFont(f)

        self.detail = QLabel()
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: #555;")

        restart_btn = QPushButton("Scan Another Folder")
        restart_btn.setMinimumHeight(45)
        restart_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; padding: 10px 20px; font-size: 12pt; }"
            "QPushButton:hover { background-color: #3498db; }"
        )
        restart_btn.clicked.connect(on_restart)

        layout.addStretch()
        layout.addWidget(self.heading)
        layout.addSpacing(8)
        layout.addWidget(self.detail)
        layout.addSpacing(24)
        layout.addWidget(restart_btn, 0, Qt.AlignCenter)
        layout.addStretch()

    def set_summary(self, deleted: int, skipped: int, total: int) -> None:
        if total == 0:
            self.heading.setText("No duplicates found")
            self.detail.setText("No image pairs at or above the similarity threshold were detected.")
        else:
            self.heading.setText("Review complete")
            self.detail.setText(
                f"Deleted: {deleted}   ·   Kept: {skipped}   ·   Total pairs reviewed: {total}\n"
                "Deleted files are in your Recycle Bin and can be restored from there."
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoDuplicatorApp")
        self.resize(1100, 780)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.welcome = WelcomePage(self.pick_folder)
        self.scan = ScanPage(self.cancel_scan)
        self.review = ReviewPage(self.skip_pair, self.finish_review, self.delete_path)
        self.finished_page = FinishedPage(self.restart)
        for page in (self.welcome, self.scan, self.review, self.finished_page):
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.welcome)

        self._worker: ScanWorker | None = None
        self._pairs: list[tuple[str, str, float]] = []
        self._index = 0
        self._deleted: set[str] = set()
        self._delete_count = 0
        self._skip_count = 0
        self._reviewed_total = 0

    def pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select a folder to scan for duplicate photos",
            os.path.expanduser("~"),
        )
        if not folder:
            return
        forbidden, reason = is_forbidden_folder(folder)
        if forbidden:
            QMessageBox.warning(self, "Folder not allowed", reason)
            return
        self.start_scan(folder)

    def start_scan(self, folder: str) -> None:
        self._pairs = []
        self._index = 0
        self._deleted.clear()
        self._delete_count = 0
        self._skip_count = 0
        self._reviewed_total = 0

        self.scan.update_progress(0, 1, f"Preparing to scan: {folder}")
        self.stack.setCurrentWidget(self.scan)

        self._worker = ScanWorker(folder)
        self._worker.progress.connect(self.scan.update_progress)
        self._worker.finished_ok.connect(self.on_scan_done)
        self._worker.failed.connect(self.on_scan_failed)
        self._worker.start()

    def cancel_scan(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker.wait(3000)
        self.stack.setCurrentWidget(self.welcome)

    def on_scan_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Scan failed", message)
        self.stack.setCurrentWidget(self.welcome)

    def on_scan_done(self, pairs: list) -> None:
        self._pairs = pairs
        self._index = 0
        if not pairs:
            self.finished_page.set_summary(0, 0, 0)
            self.stack.setCurrentWidget(self.finished_page)
            return
        self._show_current_pair()
        self.stack.setCurrentWidget(self.review)

    def _show_current_pair(self) -> None:
        while self._index < len(self._pairs):
            a, b, sim = self._pairs[self._index]
            if a in self._deleted or b in self._deleted:
                self._index += 1
                continue
            if not (os.path.exists(a) and os.path.exists(b)):
                self._index += 1
                continue
            self.review.show_pair(self._index, len(self._pairs), a, b, sim)
            return
        self.finish_review()

    def skip_pair(self) -> None:
        self._skip_count += 1
        self._reviewed_total += 1
        self._index += 1
        self._show_current_pair()

    def delete_path(self, path: str | None) -> None:
        if not path:
            return
        confirm = QMessageBox.question(
            self,
            "Delete to Recycle Bin?",
            f"Send this file to the Recycle Bin?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            send2trash(path)
            self._deleted.add(path)
            self._delete_count += 1
            self._reviewed_total += 1
            self._index += 1
            self._show_current_pair()
        except Exception as e:
            QMessageBox.warning(self, "Delete failed", f"Could not delete file:\n{e}")

    def finish_review(self) -> None:
        self.finished_page.set_summary(self._delete_count, self._skip_count, self._reviewed_total)
        self.stack.setCurrentWidget(self.finished_page)

    def restart(self) -> None:
        self.stack.setCurrentWidget(self.welcome)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        super().closeEvent(event)
