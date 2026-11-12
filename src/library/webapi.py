"""Recherche d'informations complètes sur un album via des API Web.

Services utilisés (gratuits, sans clé d'API) :
    - MusicBrainz (https://musicbrainz.org/doc/MusicBrainz_API) : album, date, label, pistes ;
    - LRCLIB (https://lrclib.net) : paroles des morceaux ;
    - Cover Art Archive (https://coverartarchive.org) : pochette de l'album.

Seule la bibliothèque standard est utilisée (urllib, json).
MusicBrainz demande un User-Agent identifiant l'application et au plus 1 requête par seconde.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

USER_AGENT = "L3I-PythonProjet/1.0 (CY Cergy Paris Universite, projet etudiant)"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"
LRCLIB_URL = "https://lrclib.net/api"
COVERART_URL = "https://coverartarchive.org"
TIMEOUT = 10  # secondes

_last_mb_request = 0.0


class WebApiError(Exception):
    """Erreur réseau ou réponse inexploitable d'une API Web."""


@dataclass
class TrackInfo:
    """Un morceau de l'album tel que décrit par MusicBrainz."""
    position: int
    title: str
    duration: float = 0.0           # en secondes
    lyrics: Optional[str] = None    # None = paroles non cherchées ou introuvables
    instrumental: bool = False

    @property
    def duration_str(self) -> str:
        """Durée au format m:ss."""
        minutes, seconds = divmod(int(round(self.duration)), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class AlbumInfo:
    """Informations complètes d'un album."""
    mbid: str                       # identifiant MusicBrainz de la « release »
    title: str
    artist: str
    date: str = ""
    country: str = ""
    label: str = ""
    tracks: List[TrackInfo] = field(default_factory=list)
    cover_url: str = ""

    def __str__(self) -> str:
        """Affichage lisible de l'album et de ses pistes (utilisé par le CLI)."""
        lines = [
            f"Album        : {self.title}",
            f"Artiste      : {self.artist}",
            f"Date         : {self.date or '-'}",
            f"Pays         : {self.country or '-'}",
            f"Label        : {self.label or '-'}",
            f"Pochette     : {self.cover_url or '-'}",
            f"Pistes       : {len(self.tracks)}",
        ]
        for t in self.tracks:
            lines.append(f"  {t.position:>2}. {t.title} [{t.duration_str}]")
        return "\n".join(lines)


def _get_json(url: str, params: dict) -> Optional[dict]:
    """Requête GET qui renvoie le JSON décodé, ou None si la ressource n'existe pas (404)."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    request = urllib.request.Request(full_url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise WebApiError(f"Erreur HTTP {exc.code} sur {url}") from exc
    except urllib.error.URLError as exc:
        raise WebApiError(f"Connexion impossible ({exc.reason}). Vérifiez votre accès Internet.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WebApiError(f"Réponse illisible de {url}") from exc


def _musicbrainz(path: str, params: dict) -> Optional[dict]:
    """Requête MusicBrainz en respectant la limite d'une requête par seconde."""
    global _last_mb_request
    wait = 1.0 - (time.monotonic() - _last_mb_request)
    if wait > 0:
        time.sleep(wait)
    _last_mb_request = time.monotonic()
    params = dict(params, fmt="json")
    return _get_json(f"{MUSICBRAINZ_URL}/{path}", params)


def _lucene_escape(text: str) -> str:
    """Échappe les guillemets pour la syntaxe de recherche de MusicBrainz."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _artist_credit(data: dict) -> str:
    """Reconstitue le nom d'artiste (ex. « Daft Punk feat. Pharrell Williams »)."""
    parts = []
    for credit in data.get("artist-credit", []):
        parts.append(credit.get("name", "") + credit.get("joinphrase", ""))
    return "".join(parts).strip()


def search_album(artist: str, album: str, limit: int = 5) -> List[dict]:
    """Cherche un album sur MusicBrainz.

    Renvoie une liste de résultats (dict avec id, title, artist, date, country, score),
    du plus pertinent au moins pertinent.
    """
    if not album:
        raise WebApiError("Le nom de l'album est nécessaire pour la recherche.")
    query = f'release:"{_lucene_escape(album)}"'
    if artist:
        query += f' AND artist:"{_lucene_escape(artist)}"'
    data = _musicbrainz("release/", {"query": query, "limit": limit}) or {}
    results = []
    for rel in data.get("releases", []):
        results.append({
            "id": rel.get("id", ""),
            "title": rel.get("title", ""),
            "artist": _artist_credit(rel),
            "date": rel.get("date", ""),
            "country": rel.get("country", ""),
            "score": int(rel.get("score", 0)),
        })
    return results


def cover_url(mbid: str) -> str:
    """URL de la pochette (face avant, 500 px) sur Cover Art Archive."""
    return f"{COVERART_URL}/release/{mbid}/front-500"


def download_cover(mbid: str) -> Optional[bytes]:
    """Télécharge la pochette d'un album. Renvoie None si elle n'existe pas."""
    request = urllib.request.Request(cover_url(mbid), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise WebApiError(f"Erreur HTTP {exc.code} sur la pochette") from exc
    except urllib.error.URLError as exc:
        raise WebApiError(f"Connexion impossible ({exc.reason}).") from exc


def get_album(mbid: str) -> AlbumInfo:
    """Récupère le détail d'un album MusicBrainz (label, pistes, durées)."""
    data = _musicbrainz(f"release/{mbid}", {"inc": "recordings+artist-credits+labels"})
    if data is None:
        raise WebApiError(f"Album introuvable sur MusicBrainz : {mbid}")

    labels = [li["label"]["name"] for li in data.get("label-info", [])
              if li.get("label") and li["label"].get("name")]
    info = AlbumInfo(
        mbid=mbid,
        title=data.get("title", ""),
        artist=_artist_credit(data),
        date=data.get("date", ""),
        country=data.get("country", ""),
        label=", ".join(dict.fromkeys(labels)),   # sans doublons, ordre conservé
        cover_url=cover_url(mbid) if data.get("cover-art-archive", {}).get("front") else "",
    )
    position = 0
    for medium in data.get("media", []):           # un album peut avoir plusieurs CD
        for track in medium.get("tracks", []):
            position += 1
            length = track.get("length") or track.get("recording", {}).get("length") or 0
            info.tracks.append(TrackInfo(
                position=position,
                title=track.get("title") or track.get("recording", {}).get("title", ""),
                duration=length / 1000,
            ))
    return info


def get_lyrics(artist: str, title: str, album: str = "", duration: float = 0) -> Optional[str]:
    """Cherche les paroles d'un morceau sur LRCLIB.

    Renvoie le texte des paroles, la chaîne "[Instrumental]" pour un morceau sans paroles,
    ou None si rien n'a été trouvé.
    """
    if not (artist and title):
        return None
    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    if duration:
        params["duration"] = int(round(duration))

    # 1) correspondance exacte (artiste + titre + album + durée)
    data = _get_json(f"{LRCLIB_URL}/get", params)
    # 2) sinon, recherche plus souple (artiste + titre seulement)
    if data is None:
        found = _get_json(f"{LRCLIB_URL}/search", {"artist_name": artist, "track_name": title})
        data = found[0] if found else None
    if not data:
        return None
    if data.get("instrumental"):
        return "[Instrumental]"
    return data.get("plainLyrics") or None


def fetch_album_info(artist: str, album: str, with_lyrics: bool = True) -> AlbumInfo:
    """Recherche un album puis récupère ses informations complètes (et les paroles).

    C'est la fonction à appeler depuis le CLI ou la GUI.
    Lève WebApiError si l'album est introuvable ou en cas de problème réseau.
    """
    results = search_album(artist, album)
    if not results:
        raise WebApiError(f"Aucun album trouvé pour « {album} » ({artist or 'artiste inconnu'}).")
    info = get_album(results[0]["id"])
    if with_lyrics:
        for track in info.tracks:
            try:
                track.lyrics = get_lyrics(info.artist or artist, track.title, info.title, track.duration)
            except WebApiError:
                track.lyrics = None   # on continue avec les autres morceaux
            track.instrumental = track.lyrics == "[Instrumental]"
    return info
