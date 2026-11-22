import os
import sys

PKG = os.path.dirname(os.path.abspath(__file__))
if PKG not in sys.path:
    sys.path.insert(0, PKG)
