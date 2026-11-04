"""Génération, sauvegarde et lecture de playlists au format XSPF.

Spécification : https://xspf.org/  -  Validateur : https://validator.xspf.org/
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List

from .metadata import AudioMetadata, MetadataError, extract_metadata

XSPF_NS = "http://xspf.org/ns/0/"
DEFAULT_PLAYLIST_NAME = "default_playlist.xspf"


def build_xspf(tracks: Iterable[AudioMetadata], title: str = "Playlist") -> ET.ElementTree:
    """Construit l'arbre XML XSPF à partir d'une liste de morceaux."""
    ET.register_namespace("", XSPF_NS)
    playlist = ET.Element(f"{{{XSPF_NS}}}playlist", {"version": "1"})
    ET.SubElement(playlist, f"{{{XSPF_NS}}}title").text = title
    track_list = ET.SubElement(playlist, f"{{{XSPF_NS}}}trackList")

    for meta in tracks:
        track = ET.SubElement(track_list, f"{{{XSPF_NS}}}track")
        # <location> doit être une URI : file:///chemin/absolu
        uri = Path(os.path.abspath(meta.path)).as_uri()
        ET.SubElement(track, f"{{{XSPF_NS}}}location").text = uri
        if meta.title:
            ET.SubElement(track, f"{{{XSPF_NS}}}title").text = meta.title
        if meta.artist:
            ET.SubElement(track, f"{{{XSPF_NS}}}creator").text = meta.artist
        if meta.album:
            ET.SubElement(track, f"{{{XSPF_NS}}}album").text = meta.album
        if meta.track_number:
            num = meta.track_number.split("/")[0].strip()
            if num.isdigit():
                ET.SubElement(track, f"{{{XSPF_NS}}}trackNum").text = num
        if meta.duration:
            # XSPF : durée en millisecondes
            ET.SubElement(track, f"{{{XSPF_NS}}}duration").text = str(int(meta.duration * 1000))

    tree = ET.ElementTree(playlist)
    ET.indent(tree, space="  ")
    return tree


def save_playlist(tracks: Iterable[AudioMetadata], output_path: str, title: str = "Playlist") -> str:
    """Écrit la playlist XSPF dans output_path et renvoie le chemin."""
    tree = build_xspf(tracks, title)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def tracks_from_paths(paths: Iterable[str]) -> tuple[List[AudioMetadata], List[str]]:
    """Extrait les métadonnées de chaque chemin.

    Renvoie (morceaux lus, messages d'erreur) pour ne pas planter sur un fichier abîmé.
    """
    tracks: List[AudioMetadata] = []
    errors: List[str] = []
    for p in paths:
        try:
            tracks.append(extract_metadata(p))
        except MetadataError as exc:
            errors.append(str(exc))
    return tracks, errors


def load_playlist(xspf_path: str) -> List[str]:
    """Relit une playlist XSPF et renvoie les chemins locaux des morceaux."""
    from urllib.parse import unquote, urlparse

    root = ET.parse(xspf_path).getroot()
    paths = []
    for loc in root.iter(f"{{{XSPF_NS}}}location"):
        if loc.text:
            parsed = urlparse(loc.text.strip())
            paths.append(unquote(parsed.path) if parsed.scheme == "file" else loc.text.strip())
    return paths
