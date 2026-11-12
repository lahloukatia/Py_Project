"""Mode console du projet : métadonnés d un fichier ou playlist d un dossier.

Exemples :
    python3 cli.py -h
    python3 cli.py -f music.mp3
    python3 cli.py -d ./music/
    python3 cli.py -d ./music/ -o playlist.xspf
    python3 cli.py -e music.mp3 -s titre="Mon titre" -s genre=Rock
    python3 cli.py -e music.mp3            (édition interactive)
    python3 cli.py -a music.mp3            (infos de l'album + paroles via API Web)
    python3 cli.py -p music.mp3            (écouter un morceau)
    python3 cli.py -p playlist.xspf        (écouter une playlist enregistrée)
"""
from __future__ import annotations

import argparse
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from library.explorer import explore  # noqa: E402
from library.metadata import MetadataError, extract_metadata  # noqa: E402
from library.tags import TAG_LABELS, TagError, current_tags, parse_assignments, write_tags  # noqa: E402
from library.webapi import WebApiError, fetch_album_info  # noqa: E402
from library.playlist import DEFAULT_PLAYLIST_NAME, save_playlist, tracks_from_paths  # noqa: E402
from library.player import PlayerError, play_file, play_playlist  # noqa: E402


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
    source.add_argument("-e", "--edit", metavar="FICHIER",
                        help="modifier les tags d'un fichier MP3 ou FLAC "
                             "(avec -s, ou en mode interactif sans -s)")
    source.add_argument("-a", "--album", metavar="FICHIER",
                        help="chercher les infos complètes de l'album du fichier "
                             "(pistes, paroles) via une API Web")
    source.add_argument("-p", "--play", metavar="FICHIER",
                        help="écouter un fichier MP3/FLAC ou une playlist .xspf enregistrée")
    parser.add_argument("-s", "--set", metavar="CLE=VALEUR", action="append",
                        help="tag à modifier avec -e (répétable). Clés : titre, artiste, album, "
                             "artiste_album, date, genre, piste. Valeur vide = suppression")
    parser.add_argument("--no-lyrics", action="store_true",
                        help="avec -a : ne pas télécharger les paroles")
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
    """Option -d : explore le dossier, affiche les morceaux retenus et rejetés,
    puis enregistre la playlist XSPF (default_playlist.xspf ou le fichier donné par -o)."""
    try:
        scan = explore(directory)
    except NotADirectoryError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    tracks, errors = tracks_from_paths(scan.files)
    print(f"{scan.scanned} fichier(s) examiné(s), {len(tracks)} fichier(s) MP3/FLAC retenu(s) "
          f"({scan.mp3_count} MP3, {scan.flac_count} FLAC) dans {directory}\n")
    for i, meta in enumerate(tracks, 1):
        print(f"{i:>3}. {meta.artist or '?'} - {meta.title or os.path.basename(meta.path)} "
              f"[{meta.duration_str}] ({meta.format})")
    for path, reason in scan.rejected:
        print(f"Ignoré : {path} ({reason})", file=sys.stderr)
    for err in scan.errors + errors:
        print(f"Avertissement : {err}", file=sys.stderr)

    if output is not None or tracks:
        out = output or DEFAULT_PLAYLIST_NAME
        save_playlist(tracks, out, title=os.path.basename(os.path.abspath(directory)))
        print(f"\nPlaylist enregistrée : {out}")
    return 0


def ask_tags_interactively(path: str) -> dict:
    """Demande chaque tag à l'utilisateur. Entrée = garder, « - » = supprimer."""
    meta = extract_metadata(path)
    print(f"Édition des tags de {path}")
    print("(Entrée = garder la valeur actuelle, « - » = supprimer le tag)\n")
    changes = {}
    for key, value in current_tags(meta).items():
        answer = input(f"{TAG_LABELS[key]:<14}[{value}] : ").strip()
        if answer == "-":
            changes[key] = ""
        elif answer and answer != value:
            changes[key] = answer
    return changes


def run_edit(path: str, assignments: list[str] | None) -> int:
    """Option -e : modifie les tags avec les valeurs de -s, ou en mode interactif sans -s.

    Renvoie 0 si tout s'est bien passé, 1 en cas d'erreur ou d'annulation.
    """
    try:
        changes = parse_assignments(assignments) if assignments else ask_tags_interactively(path)
        if not changes:
            print("Aucune modification.")
            return 0
        meta = write_tags(path, changes)
    except (TagError, MetadataError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nÉdition annulée, fichier inchangé.")
        return 1
    print("\nTags enregistrés :\n")
    print(meta)
    return 0


def run_album(path: str, with_lyrics: bool) -> int:
    """Option -a : lit l'artiste et l'album dans les tags du fichier, interroge les API Web
    et affiche les informations de l'album puis les paroles de chaque morceau.

    Renvoie 0 si tout s'est bien passé, 1 en cas d'erreur (tag album absent, réseau...).
    """
    try:
        meta = extract_metadata(path)
        if not meta.album:
            print("Erreur : ce fichier n'a pas de tag « album ». "
                  "Ajoutez-le avec : python3 cli.py -e FICHIER -s album=\"...\"", file=sys.stderr)
            return 1
        print(f"Recherche de « {meta.album} » ({meta.artist or 'artiste inconnu'})...\n")
        info = fetch_album_info(meta.album_artist or meta.artist, meta.album, with_lyrics)
    except (MetadataError, WebApiError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    print(info)
    if with_lyrics:
        for track in info.tracks:
            print(f"\n--- {track.position}. {track.title} ---")
            print(track.lyrics or "(paroles introuvables)")
    return 0


def run_play(path: str) -> int:
    """Option -p : joue un morceau MP3/FLAC ou une playlist XSPF.

    Renvoie 0 si tout s'est bien passé, 1 en cas d'erreur (fichier, son, pygame...).
    Ctrl+C arrête la lecture proprement.
    """
    try:
        if path.lower().endswith(".xspf"):
            if not os.path.isfile(path):
                print(f"Erreur : playlist introuvable : {path}", file=sys.stderr)
                return 1
            count = play_playlist(path)
            print(f"\nFin de la playlist ({count} morceau(x) joué(s)).")
        else:
            play_file(path)
            print("Fin du morceau.")
    except (MetadataError, PlayerError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nLecture arrêtée.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not any((args.file, args.directory, args.edit, args.album, args.play)):
        print("Erreur : aucun paramètre fourni (utiliser -f FICHIER, -d DOSSIER, "
              "-e FICHIER, -a FICHIER ou -p FICHIER).\n"
              "Tapez « python3 cli.py -h » pour obtenir de l'aide.", file=sys.stderr)
        return 2
    if args.output and not args.directory:
        print("Erreur : -o ne s'utilise qu'avec -d.", file=sys.stderr)
        return 2
    if args.set and not args.edit:
        print("Erreur : -s ne s'utilise qu'avec -e.", file=sys.stderr)
        return 2

    if args.file:
        return run_file(args.file)
    if args.edit:
        return run_edit(args.edit, args.set)
    if args.play:
        return run_play(args.play)
    if args.album:
        return run_album(args.album, not args.no_lyrics)
    return run_directory(args.directory, args.output)


if __name__ == "__main__":
    sys.exit(main())