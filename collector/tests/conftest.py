"""Put the collector/ dir on sys.path so tests can import its flat modules."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
