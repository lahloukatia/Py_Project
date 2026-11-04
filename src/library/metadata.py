"""Extraction des métadonnées des fichiers MP3 (ID3) et FLAC (Vorbis comment).

Dépendance : mutagen  (pip install mutagen)
"""
from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

SUPPORTED_EXTENSIONS = {".mp3": "audio/mpeg", ".flac": "audio/flac"}

ACCEPTED_MIMES = {
    "audio/mpeg", "audio/mp3", "audio/x-mp3",
    "audio/flac", "audio/x-flac",
}


class MetadataError(Exception):
    """Erreur lors de la lecture d'un fichier audio."""


@dataclass
class AudioMetadata:
    path: str
    format: str = ""            
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    date: str = ""
    genre: str = ""
    track_number: str = ""
    duration: float = 0.0       
    bitrate: int = 0            
    sample_rate: int = 0        
    channels: int = 0
    has_cover: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def duration_str(self) -> str:
        minutes, seconds = divmod(int(round(self.duration)), 60)
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        lines = [
            f"Fichier      : {self.path}",
            f"Format       : {self.format}",
            f"Titre        : {self.title or '-'}",
            f"Artiste      : {self.artist or '-'}",
            f"Album        : {self.album or '-'}",
            f"Artiste album: {self.album_artist or '-'}",
            f"Date         : {self.date or '-'}",
            f"Genre        : {self.genre or '-'}",
            f"Piste n°     : {self.track_number or '-'}",
            f"Durée        : {self.duration_str}",
            f"Débit        : {self.bitrate // 1000} kbit/s",
            f"Fréquence    : {self.sample_rate} Hz",
            f"Canaux       : {self.channels}",
            f"Pochette     : {'oui' if self.has_cover else 'non'}",
        ]
        return "\n".join(lines)


def is_supported_file(path: str) -> bool:
    """Vrai si l'extension ET le type MIME correspondent à un MP3 ou un FLAC."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False
    mime, _ = mimetypes.guess_type(path)
    
    return mime is None or mime in ACCEPTED_MIMES


def _first(tags, *keys) -> str:
    """Première valeur non vide parmi plusieurs clés d'un dictionnaire de tags."""
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value[0]) if isinstance(value, (list, tuple)) else str(value)
    return ""


def _from_mp3(path: str) -> AudioMetadata:
    audio = MP3(path)
    meta = AudioMetadata(path=path, format="MP3")
    meta.duration = audio.info.length
    meta.bitrate = int(audio.info.bitrate)
    meta.sample_rate = audio.info.sample_rate
    meta.channels = audio.info.channels

    tags = audio.tags 
    if tags:
        def frame(name: str) -> str:
            f = tags.get(name)
            return str(f.text[0]) if f is not None and getattr(f, "text", None) else ""

        meta.title = frame("TIT2")
        meta.artist = frame("TPE1")
        meta.album = frame("TALB")
        meta.album_artist = frame("TPE2")
        meta.date = frame("TDRC") or frame("TYER")
        meta.genre = frame("TCON")
        meta.track_number = frame("TRCK")
        meta.has_cover = any(k.startswith("APIC") for k in tags.keys())
    return meta


def _from_flac(path: str) -> AudioMetadata:
    audio = FLAC(path)
    meta = AudioMetadata(path=path, format="FLAC")
    meta.duration = audio.info.length
    meta.bitrate = int(getattr(audio.info, "bitrate", 0) or 0)
    meta.sample_rate = audio.info.sample_rate
    meta.channels = audio.info.channels

    tags = {k.lower(): v for k, v in (audio.tags or {})}
    meta.title = _first(tags, "title")
    meta.artist = _first(tags, "artist")
    meta.album = _first(tags, "album")
    meta.album_artist = _first(tags, "albumartist", "album artist")
    meta.date = _first(tags, "date", "year")
    meta.genre = _first(tags, "genre")
    meta.track_number = _first(tags, "tracknumber")
    meta.has_cover = bool(audio.pictures)
    return meta


def extract_metadata(path: str) -> AudioMetadata:
    """Extrait les métadonnées d'un fichier MP3 ou FLAC.

    Leve MetadataError si le fichier n' existe pas, n'est pas un MP3 /FLAC
    ou est corrompu
    """
    if not os.path.isfile(path):
        raise MetadataError(f"Fichier introuvable : {path}")
    if not is_supported_file(path):
        raise MetadataError(f"Format non supporté (MP3 ou FLAC attendu) : {path}")

    ext = os.path.splitext(path)[1].lower()
    try:
        return _from_mp3(path) if ext == ".mp3" else _from_flac(path)
    except Exception as exc:  
        raise MetadataError(f"Lecture impossible de {path} : {exc}") from exc
