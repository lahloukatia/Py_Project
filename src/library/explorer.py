"""Exploration récursive d'un dossier pour trouver les fichiers MP3 et FLAC.

Un fichier est gardé seulement si :
    1. son extension est .mp3 ou .flac
    2. le type MIME deviné à partir du nom (module mimetypes) est bien un type audio
    3. le contenu du fichier correspond au format annoncé par l'extension
       (un fichier texte renommé en .mp3 est donc refusé)

Dépendance : mutagen  (pip install mutagen)
"""
import mimetypes
import os

from mutagen.flac import FLAC
from mutagen.mp3 import MP3

TYPES_MIME_ACCEPTES = ["audio/mpeg", "audio/mp3", "audio/flac", "audio/x-flac"]


class ScanResult:
    """Résultat de l'exploration d'un dossier."""

    def __init__(self, directory):
        self.directory = directory
        self.files = []       # fichiers MP3/FLAC valides
        self.rejected = []    # liste de (chemin, raison) pour les faux MP3/FLAC
        self.errors = []      # messages d'erreur (dossier illisible...)
        self.scanned = 0      # nombre de fichiers examinés
        self.mp3_count = 0
        self.flac_count = 0


def format_reel(path):
    """Renvoie "flac", "mp3" ou None selon le contenu réel du fichier.

    On ne se fie pas à l'extension : on demande à mutagen d'ouvrir le fichier
    comme un FLAC, puis comme un MP3. S'il n'y arrive pas, le contenu n'est pas bon.
    """
    try:
        FLAC(path)
        return "flac"
    except Exception:
        pass
    try:
        MP3(path)
        return "mp3"
    except Exception:
        return None


def verifier_fichier(path):
    """Renvoie (True, "") si le fichier est un vrai MP3/FLAC, sinon (False, raison)."""
    extension = os.path.splitext(path)[1].lower()
    if extension not in (".mp3", ".flac"):
        return False, "extension non prise en charge"

    mime, _ = mimetypes.guess_type(path)
    if mime is not None and mime not in TYPES_MIME_ACCEPTES:
        return False, f"type MIME incorrect ({mime})"

    reel = format_reel(path)
    if reel is None:
        return False, "contenu qui n'est ni du MP3 ni du FLAC"
    if "." + reel != extension:
        return False, f"extension {extension} mais le contenu est du {reel.upper()}"
    return True, ""


def explore(directory):
    """Parcourt directory et tous ses sous-dossiers avec os.walk.

    Les fichiers et dossiers cachés (nom commençant par un point) sont ignorés.
    Lève NotADirectoryError si le dossier n'existe pas.
    """
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Dossier introuvable : {directory}")

    resultat = ScanResult(directory)

    for dossier, sous_dossiers, fichiers in os.walk(directory):
        # on retire les dossiers cachés pour que os.walk n'y descende pas
        sous_dossiers[:] = [d for d in sous_dossiers if not d.startswith(".")]

        for nom in fichiers:
            if nom.startswith("."):
                continue
            chemin = os.path.join(dossier, nom)
            resultat.scanned += 1

            ok, raison = verifier_fichier(chemin)
            if ok:
                resultat.files.append(chemin)
                if chemin.lower().endswith(".mp3"):
                    resultat.mp3_count += 1
                else:
                    resultat.flac_count += 1
            elif nom.lower().endswith((".mp3", ".flac")):
                # on ne signale que les faux MP3/FLAC, pas les .txt ou .jpg
                resultat.rejected.append((chemin, raison))

    resultat.files.sort()
    return resultat


def scan_directory(directory):
    """Liste triée des fichiers MP3/FLAC valides (utilisée par la GUI)."""
    return explore(directory).files
