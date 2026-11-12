"""Lecture audio de fichiers MP3 / FLAC et de playlists XSPF.

Module commun au CLI (option -p) et à la GUI : la classe AudioPlayer ne bloque pas
(utilisable depuis une interface graphique), les fonctions play_file / play_playlist
bloquent jusqu'à la fin du morceau (utilisables depuis la console).

Dépendance : pygame  (pip install pygame)
"""
from __future__ import annotations

import os
import time
from typing import Callable, List, Optional

from .metadata import MetadataError, extract_metadata
from .playlist import load_playlist


class PlayerError(Exception):
    """Erreur de lecture audio (pygame absent, fichier illisible, pas de carte son...)."""


class AudioPlayer:
    """Lecteur audio non bloquant basé sur pygame.mixer."""

    def __init__(self) -> None:
        try:
            import pygame
        except ImportError as exc:
            raise PlayerError("pygame n'est pas installé (pip install pygame)") from exc
        self._pygame = pygame
        try:
            pygame.mixer.init()
        except pygame.error as exc:
            raise PlayerError(f"Impossible d'initialiser la sortie audio : {exc}") from exc
        self._paused = False

    def play(self, path: str) -> None:
        """Charge et lance la lecture d'un fichier (remplace le morceau en cours)."""
        if not os.path.isfile(path):
            raise PlayerError(f"Fichier introuvable : {path}")
        try:
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.play()
        except self._pygame.error as exc:
            raise PlayerError(f"Lecture impossible de {path} : {exc}") from exc
        self._paused = False

    def pause(self) -> None:
        self._pygame.mixer.music.pause()
        self._paused = True

    def resume(self) -> None:
        self._pygame.mixer.music.unpause()
        self._paused = False

    def stop(self) -> None:
        self._pygame.mixer.music.stop()
        self._paused = False

    def is_playing(self) -> bool:
        """Vrai tant qu'un morceau est en cours (une pause compte comme « en cours »)."""
        return self._paused or bool(self._pygame.mixer.music.get_busy())

    def close(self) -> None:
        self.stop()
        self._pygame.mixer.quit()


def _wait_end(player: AudioPlayer) -> None:
    """Attend la fin du morceau courant."""
    while player.is_playing():
        time.sleep(0.2)


def play_file(path: str, announce: Optional[Callable[[str], None]] = print) -> None:
    """Joue un fichier MP3/FLAC en bloquant jusqu'à la fin (Ctrl+C pour arrêter).

    Lève PlayerError ou MetadataError si le fichier n'est pas lisible.
    """
    meta = extract_metadata(path)   # vérifie aussi l'existence et le format
    player = AudioPlayer()
    try:
        if announce:
            announce(f"Lecture : {meta.artist or '?'} - {meta.title or os.path.basename(path)} "
                     f"[{meta.duration_str}] (Ctrl+C pour arrêter)")
        player.play(path)
        _wait_end(player)
    finally:
        player.close()


def play_playlist(xspf_path: str, announce: Optional[Callable[[str], None]] = print) -> int:
    """Joue tous les morceaux d'une playlist XSPF à la suite.

    Les morceaux illisibles sont signalés puis ignorés. Renvoie le nombre de morceaux joués.
    """
    paths: List[str] = load_playlist(xspf_path)
    if not paths:
        raise PlayerError(f"Playlist vide : {xspf_path}")
    player = AudioPlayer()
    played = 0
    try:
        for i, path in enumerate(paths, 1):
            try:
                meta = extract_metadata(path)
                player.play(path)
            except (MetadataError, PlayerError) as exc:
                if announce:
                    announce(f"Ignoré : {exc}")
                continue
            played += 1
            if announce:
                announce(f"[{i}/{len(paths)}] {meta.artist or '?'} - "
                         f"{meta.title or os.path.basename(path)} [{meta.duration_str}]")
            _wait_end(player)
    finally:
        player.close()
    return played