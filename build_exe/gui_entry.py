"""PyInstaller entry point for Talabiya.exe."""
import sys

from talabiya.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
