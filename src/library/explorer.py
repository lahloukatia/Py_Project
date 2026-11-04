"""Exploration récursive d'un dossier (version minimale --- je l ai fait juste pour tester le CLI).
"""
from __future__ import annotations

import os
from typing import List

from .metadata import is_supported_file


def scan_directory(directory: str) -> List[str]:
  
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Dossier introuvable : {directory}")
    found = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            full = os.path.join(root, name)
            if is_supported_file(full):
                found.append(full)
    return sorted(found)
