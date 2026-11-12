"""Modification et sauvegarde des TAGS d'un fichier MP3 (ID3) ou FLAC (Vorbis comment).

On manipule les tags avec des noms communs aux deux formats (title, artist, ...),
puis on les traduit vers les frames ID3 pour les MP3 et vers les clés Vorbis pour les FLAC.

Dépendance : mutagen  (pip install mutagen)
"""
from __future__ import annotations

import os
import re
from typing import Dict, Iterable, Mapping

from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK
from mutagen.mp3 import MP3

from .metadata import AudioMetadata, MetadataError, extract_metadata, is_supported_file

# Nom commun -> (classe de frame ID3, clé Vorbis comment)
EDITABLE_TAGS: Dict[str, tuple] = {
    "title": (TIT2, "title"),
    "artist": (TPE1, "artist"),
    "album": (TALB, "album"),
    "album_artist": (TPE2, "albumartist"),
    "date": (TDRC, "date"),
    "genre": (TCON, "genre"),
    "track_number": (TRCK, "tracknumber"),
}

# Libellés affichés en mode console (édition interactive)
TAG_LABELS: Dict[str, str] = {
    "title": "Titre",
    "artist": "Artiste",
    "album": "Album",
    "album_artist": "Artiste album",
    "date": "Date",
    "genre": "Genre",
    "track_number": "Piste n°",
}

# Alias acceptés en ligne de commande (ex. -s titre="...")
TAG_ALIASES: Dict[str, str] = {
    "titre": "title",
    "artiste": "artist",
    "artiste_album": "album_artist",
    "albumartist": "album_artist",
    "annee": "date",
    "année": "date",
    "year": "date",
    "piste": "track_number",
    "track": "track_number",
    "tracknumber": "track_number",
}


class TagError(MetadataError):
    """Erreur lors de la modification des tags."""


# Formats acceptés : date AAAA, AAAA-MM ou AAAA-MM-JJ ; piste N ou N/total
_DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")
_TRACK_RE = re.compile(r"^[1-9]\d*(/[1-9]\d*)?$")


def validate_value(key: str, value: str) -> None:
    """Vérifie le format de la date et du numéro de piste (valeur vide = suppression, acceptée).

    Sans ce contrôle, une date invalide serait effacée silencieusement dans un MP3
    (la frame ID3 TDRC n'accepte que des dates), alors qu'elle serait gardée dans un FLAC.
    """
    if not value:
        return
    if key == "date" and not _DATE_RE.match(value):
        raise TagError(f"Date invalide : « {value} » (formats acceptés : AAAA, AAAA-MM, AAAA-MM-JJ)")
    if key == "track_number" and not _TRACK_RE.match(value):
        raise TagError(f"Numéro de piste invalide : « {value} » (formats acceptés : 3 ou 3/12)")


def normalize_tag_name(name: str) -> str:
    """Renvoie le nom commun d'un tag (accepte les alias français) ou lève TagError."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    key = TAG_ALIASES.get(key, key)
    if key not in EDITABLE_TAGS:
        valides = ", ".join(EDITABLE_TAGS)
        raise TagError(f"Tag inconnu : « {name} » (tags modifiables : {valides})")
    return key


def current_tags(meta: AudioMetadata) -> Dict[str, str]:
    """Valeurs actuelles des tags modifiables, à partir des métadonnées extraites."""
    return {key: getattr(meta, key) or "" for key in EDITABLE_TAGS}


def _write_mp3(path: str, changes: Mapping[str, str]) -> None:
    """Écrit les tags d'un MP3 sous forme de frames ID3 (crée l'en-tête ID3 s'il manque)."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        # Le MP3 n'a encore aucun tag : on en crée un
        tags = ID3()
    for key, value in changes.items():
        frame_cls, _ = EDITABLE_TAGS[key]
        frame_id = frame_cls.__name__
        if value:
            tags.setall(frame_id, [frame_cls(encoding=3, text=[value])])  # 3 = UTF-8
        else:
            tags.delall(frame_id)
    tags.save(path)


def _write_flac(path: str, changes: Mapping[str, str]) -> None:
    """Écrit les tags d'un FLAC sous forme de commentaires Vorbis (clé=valeur)."""
    audio = FLAC(path)
    if audio.tags is None:
        audio.add_tags()
    for key, value in changes.items():
        _, vorbis_key = EDITABLE_TAGS[key]
        if value:
            audio[vorbis_key] = [value]
        elif vorbis_key in audio:
            del audio[vorbis_key]
    audio.save()


def write_tags(path: str, changes: Mapping[str, str]) -> AudioMetadata:
    """Modifie les tags d'un fichier MP3 ou FLAC et les sauvegarde dans le fichier.

    changes : dictionnaire {nom du tag: nouvelle valeur}. Une valeur vide supprime le tag.
    Les noms peuvent être en anglais (title, artist...) ou en français (titre, artiste...).
    Renvoie les métadonnées relues après sauvegarde.
    Lève TagError si le fichier est invalide, si un tag est inconnu, si une date ou un
    numéro de piste est mal formé, ou si l'écriture échoue. Dans ces cas, le fichier
    n'est pas modifié.
    """
    if not os.path.isfile(path):
        raise TagError(f"Fichier introuvable : {path}")
    if not is_supported_file(path):
        raise TagError(f"Format non supporté (MP3 ou FLAC attendu) : {path}")
    if not os.access(path, os.W_OK):
        raise TagError(f"Fichier en lecture seule : {path}")

    normalized = {normalize_tag_name(k): ("" if v is None else str(v).strip())
                  for k, v in changes.items()}
    for key, value in normalized.items():
        validate_value(key, value)
    if not normalized:
        return extract_metadata(path)

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".mp3":
            MP3(path)  # vérifie que c'est bien un MP3 lisible avant d'écrire
            _write_mp3(path, normalized)
        else:
            _write_flac(path, normalized)
    except Exception as exc:
        raise TagError(f"Écriture des tags impossible pour {path} : {exc}") from exc
    return extract_metadata(path)


def parse_assignments(assignments: Iterable[str] | None) -> Dict[str, str]:
    """Transforme une liste ["titre=Mon titre", "genre=Rock"] en dictionnaire de tags."""
    result: Dict[str, str] = {}
    for item in assignments or []:
        if "=" not in item:
            raise TagError(f"Format attendu CLE=VALEUR, reçu : « {item} »")
        key, value = item.split("=", 1)
        result[normalize_tag_name(key)] = value
    return result
