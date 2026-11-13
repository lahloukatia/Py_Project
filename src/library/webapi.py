"""Recherche d'informations sur un album avec des API Web gratuites (sans clé).

    - MusicBrainz : infos de l'album et liste des pistes
    - LRCLIB : paroles des morceaux

On utilise seulement la bibliothèque standard : urllib pour les requêtes, json pour lire les réponses.
MusicBrainz demande un User-Agent qui identifie le programme et au plus une requête par seconde.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "L3I-PythonProjet/1.0 (CY Cergy Paris Universite, projet etudiant)"


class WebApiError(Exception):
    """Erreur réseau ou album introuvable."""


def get_json(url, parametres):
    """Envoie une requête GET et renvoie la réponse JSON (ou None si la page n'existe pas)."""
    url = url + "?" + urllib.parse.urlencode(parametres)
    requete = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    # MusicBrainz répond parfois 503 quand il est surchargé, ou met trop de temps à répondre :
    # dans ces deux cas on attend 2 secondes et on réessaie, jusqu'à 5 fois
    for essai in range(5):
        try:
            with urllib.request.urlopen(requete, timeout=10) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 503 and essai < 4:
                time.sleep(2)
                continue
            raise WebApiError(f"Erreur HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError):
            if essai < 4:
                time.sleep(2)
                continue
            raise WebApiError("Connexion impossible ou serveur trop lent, vérifiez votre accès Internet.")


def chercher_album(artiste, album):
    """Cherche l'album sur MusicBrainz et renvoie un dictionnaire avec ses infos et ses pistes."""
    # on enlève les guillemets, qui ont un sens spécial dans la recherche MusicBrainz
    album = album.replace('"', "")
    artiste = (artiste or "").replace('"', "")

    # "Daft Punk feat. Pharrell Williams" -> "Daft Punk" : on garde l'artiste principal
    for mot in (" feat", " ft."):
        position = artiste.lower().find(mot)
        if position != -1:
            artiste = artiste[:position]

    # 1) recherche de l'album : on récupère l'identifiant du meilleur résultat
    requete = f'release:"{album}"'
    if artiste:
        requete += f' AND artist:"{artiste}"'
    resultats = get_json("https://musicbrainz.org/ws/2/release/",
                         {"query": requete, "limit": 1, "fmt": "json"})
    if not resultats or not resultats.get("releases"):
        raise WebApiError(f"Aucun album trouvé pour {album} ({artiste or 'artiste inconnu'})")
    identifiant = resultats["releases"][0]["id"]

    time.sleep(1)  # règle de MusicBrainz : une requête par seconde maximum

    # 2) détail de l'album avec la liste des pistes
    data = get_json(f"https://musicbrainz.org/ws/2/release/{identifiant}",
                    {"inc": "recordings+artist-credits+labels", "fmt": "json"})
    if data is None:
        raise WebApiError("Album introuvable sur MusicBrainz")

    infos = {
        "titre": data.get("title", ""),
        "artiste": data["artist-credit"][0]["name"] if data.get("artist-credit") else artiste,
        "date": data.get("date", ""),
        "pays": data.get("country", ""),
        "label": "",
        "pochette": f"https://coverartarchive.org/release/{identifiant}/front-500",
        "pistes": [],
    }
    if data.get("label-info") and data["label-info"][0].get("label"):
        infos["label"] = data["label-info"][0]["label"]["name"]

    numero = 0
    for disque in data.get("media", []):          # un album peut avoir plusieurs CD
        for piste in disque.get("tracks", []):
            numero += 1
            duree = (piste.get("length") or 0) // 1000   # millisecondes -> secondes
            infos["pistes"].append({"numero": numero, "titre": piste["title"], "duree": duree})
    return infos


def chercher_paroles(artiste, titre):
    """Renvoie les paroles d'un morceau trouvées sur LRCLIB, ou None."""
    try:
        data = get_json("https://lrclib.net/api/get",
                        {"artist_name": artiste, "track_name": titre})
    except WebApiError:
        return None
    if data is None:
        return None
    if data.get("instrumental"):
        return "[Instrumental]"
    return data.get("plainLyrics")


# ----- Version objet, utilisée par l'interface graphique -----

class Piste:
    """Une piste de l'album."""

    def __init__(self, piste):
        self.position = piste["numero"]
        self.title = piste["titre"]
        self.duration = piste["duree"]
        self.lyrics = None


class InfosAlbum:
    """Les infos d'un album : mêmes données que le dictionnaire de chercher_album."""

    def __init__(self, infos):
        self.title = infos["titre"]
        self.artist = infos["artiste"]
        self.date = infos["date"]
        self.country = infos["pays"]
        self.label = infos["label"]
        self.cover_url = infos["pochette"]
        self.tracks = [Piste(p) for p in infos["pistes"]]

    def __str__(self):
        lignes = [
            f"Album    : {self.title}",
            f"Artiste  : {self.artist}",
            f"Date     : {self.date or '-'}",
            f"Pays     : {self.country or '-'}",
            f"Label    : {self.label or '-'}",
            f"Pochette : {self.cover_url}",
            f"Pistes   : {len(self.tracks)}",
        ]
        for piste in self.tracks:
            minutes, secondes = divmod(piste.duration, 60)
            lignes.append(f"  {piste.position:>2}. {piste.title} [{minutes}:{secondes:02d}]")
        return "\n".join(lignes)


def fetch_album_info(artiste, album, with_lyrics=True):
    """Cherche l'album et renvoie un objet InfosAlbum (avec les paroles si demandé)."""
    info = InfosAlbum(chercher_album(artiste, album))
    if with_lyrics:
        for piste in info.tracks:
            piste.lyrics = chercher_paroles(info.artist, piste.title)
    return info
