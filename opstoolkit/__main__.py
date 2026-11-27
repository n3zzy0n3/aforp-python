"""Permet « python -m opstoolkit » depuis la racine du projet."""
import sys

from .cli import main

sys.exit(main())
