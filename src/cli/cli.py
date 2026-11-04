"""Mode console du projet : métadonnés d un fichier ou playlist d un dossier.

Exemples :
    python3 cli.py -h
    python3 cli.py -f music.mp3
    python3 cli.py -d ./music/
    python3 cli.py -d ./music/ -o playlist.xspf
"""
from __future__ import annotations

import argparse
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from library.explorer import scan_directory  # noqa: E402
from library.metadata import MetadataError, extract_metadata  # noqa: E402
from library.playlist import DEFAULT_PLAYLIST_NAME, save_playlist, tracks_from_paths  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Analyse de fichiers musicaux MP3/FLAC et génération de playlists XSPF.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("-f", "--file", metavar="FICHIER",
                        help="fichier MP3 ou FLAC dont afficher les métadonnées")
    source.add_argument("-d", "--directory", metavar="DOSSIER",
                        help="dossier à explorer récursivement pour générer une playlist")
    parser.add_argument("-o", "--output", metavar="FICHIER.xspf",
                        help="fichier XSPF de sortie (avec -d ; défaut : "
                             f"{DEFAULT_PLAYLIST_NAME} si -o est omis)")
    return parser


def run_file(path: str) -> int:
    try:
        print(extract_metadata(path))
    except MetadataError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


def run_directory(directory: str, output: str | None) -> int:
    try:
        paths = scan_directory(directory)
    except NotADirectoryError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    tracks, errors = tracks_from_paths(paths)
    print(f"{len(tracks)} fichier(s) MP3/FLAC trouvé(s) dans {directory}\n")
    for i, meta in enumerate(tracks, 1):
        print(f"{i:>3}. {meta.artist or '?'} - {meta.title or os.path.basename(meta.path)} "
              f"[{meta.duration_str}] ({meta.format})")
    for err in errors:
        print(f"Avertissement : {err}", file=sys.stderr)

    if output is not None or tracks:
        out = output or DEFAULT_PLAYLIST_NAME
        save_playlist(tracks, out, title=os.path.basename(os.path.abspath(directory)))
        print(f"\nPlaylist enregistrée : {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.file is None and args.directory is None:
        print("Erreur : aucun paramètre fourni (utiliser -f FICHIER ou -d DOSSIER).\n"
              "Tapez « python3 cli.py -h » pour obtenir de l'aide.", file=sys.stderr)
        return 2
    if args.output and args.file:
        print("Erreur : -o ne s'utilise qu'avec -d.", file=sys.stderr)
        return 2

    if args.file:
        return run_file(args.file)
    return run_directory(args.directory, args.output)


if __name__ == "__main__":
    sys.exit(main())
