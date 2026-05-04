"""Entry point for PhotoDuplicatorApp."""

import sys

from PySide6.QtWidgets import QApplication

from gui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PhotoDuplicatorApp")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
