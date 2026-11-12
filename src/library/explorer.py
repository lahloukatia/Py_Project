"""Exploration récursive d'un dossier et filtrage des fichiers MP3 / FLAC.

Un fichier est retenu seulement si ses trois contrôles concordent :
    1. l'extension est .mp3 ou .flac ;
    2. le type MIME déduit du nom (module mimetypes) est un type audio MP3/FLAC ;
    3. le type MIME réel, lu dans les premiers octets du fichier (signature),
       correspond bien à l'extension. Un .txt renommé en .mp3 est donc rejeté.
"""
from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .metadata import ACCEPTED_MIMES, SUPPORTED_EXTENSIONS

MIME_MP3 = "audio/mpeg"
MIME_FLAC = "audio/flac"

# Type MIME réel attendu pour chaque extension
EXPECTED_MIME = {".mp3": MIME_MP3, ".flac": MIME_FLAC}


@dataclass
class ScanResult:
    """Résultat d'une exploration : fichiers retenus, fichiers écartés et erreurs."""
    directory: str
    files: List[str] = field(default_factory=list)
    rejected: List[Tuple[str, str]] = field(default_factory=list)   # (chemin, raison)
    errors: List[str] = field(default_factory=list)                 # dossiers illisibles...
    scanned: int = 0                                                # fichiers examinés

    @property
    def mp3_count(self) -> int:
        """Nombre de MP3 retenus."""
        return sum(1 for f in self.files if f.lower().endswith(".mp3"))

    @property
    def flac_count(self) -> int:
        """Nombre de FLAC retenus."""
        return sum(1 for f in self.files if f.lower().endswith(".flac"))


def _id3v2_size(header: bytes) -> int:
    """Taille totale d'un en-tête ID3v2 (10 octets d'en-tête + données + éventuel pied)."""
    # La taille est codée sur 4 octets « synchsafe » : 7 bits utiles par octet
    size = 0
    for byte in header[6:10]:
        size = (size << 7) | (byte & 0x7F)
    footer = 10 if header[5] & 0x10 else 0
    return 10 + size + footer


def _is_mpeg_audio_frame(data: bytes) -> bool:
    """Vrai si data commence par une trame MPEG audio Layer III (synchro 11 bits à 1)."""
    if len(data) < 2:
        return False
    if data[0] != 0xFF or (data[1] & 0xE0) != 0xE0:
        return False
    version = (data[1] >> 3) & 0x03   # 01 = réservé
    layer = (data[1] >> 1) & 0x03     # 01 = Layer III
    return version != 0x01 and layer == 0x01


def detect_mime(path: str) -> Optional[str]:
    """Détermine le type MIME réel d'un fichier à partir de son contenu.

    Renvoie "audio/mpeg" pour un MP3, "audio/flac" pour un FLAC, None sinon
    (ou si le fichier est illisible).
    """
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            offset = 0
            # Un MP3 (et parfois un FLAC) peut commencer par un tag ID3v2
            if len(head) == 10 and head[:3] == b"ID3":
                offset = _id3v2_size(head)
                f.seek(offset)
                head = f.read(4)
            if head[:4] == b"fLaC":
                return MIME_FLAC
            if _is_mpeg_audio_frame(head):
                return MIME_MP3
            # Certains encodeurs laissent des octets nuls après le tag ID3 :
            # on cherche la première trame dans les 4 premiers Ko qui suivent
            if offset:
                f.seek(offset)
                block = f.read(4096)
                start = len(block) - len(block.lstrip(b"\x00"))
                if _is_mpeg_audio_frame(block[start:start + 2]):
                    return MIME_MP3
    except OSError:
        return None
    return None


def check_file(path: str) -> Tuple[bool, str]:
    """Applique les trois contrôles à un fichier. Renvoie (retenu, raison du rejet)."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, "extension non prise en charge"
    guessed, _ = mimetypes.guess_type(path)
    if guessed is not None and guessed not in ACCEPTED_MIMES:
        return False, f"type MIME déduit du nom incorrect ({guessed})"
    real = detect_mime(path)
    if real is None:
        return False, "contenu qui n'est ni du MP3 ni du FLAC"
    if real != EXPECTED_MIME[ext]:
        return False, f"extension {ext} mais contenu de type {real}"
    return True, ""


def explore(directory: str, include_hidden: bool = False) -> ScanResult:
    """Parcourt récursivement directory et tous ses sous-dossiers.

    include_hidden : si False, les fichiers et dossiers cachés (nom commençant par « . »)
    sont ignorés. Les liens symboliques vers des dossiers ne sont pas suivis, ce qui évite
    de boucler à l'infini.
    Lève NotADirectoryError si le dossier n'existe pas.
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Dossier introuvable : {directory}")

    result = ScanResult(directory=directory)

    def on_error(exc: OSError) -> None:
        """Appelée par os.walk quand un dossier ne peut pas être lu : on note et on continue."""
        result.errors.append(f"Dossier illisible : {exc.filename} ({exc.strerror})")

    for root, dirs, files in os.walk(directory, onerror=on_error, followlinks=False):
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
        dirs.sort()   # ordre de parcours stable d'une exécution à l'autre
        for name in sorted(files):
            if not include_hidden and name.startswith("."):
                continue
            full = os.path.join(root, name)
            if not os.path.isfile(full):
                continue
            result.scanned += 1
            ok, reason = check_file(full)
            if ok:
                result.files.append(full)
            elif os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                # On ne signale que les faux MP3/FLAC, pas les .jpg, .txt, etc.
                result.rejected.append((full, reason))
    result.files.sort()
    return result


def scan_directory(directory: str) -> List[str]:
    """Liste triée des fichiers MP3/FLAC valides de l'arborescence (utilisée par le CLI)."""
    return explore(directory).files
