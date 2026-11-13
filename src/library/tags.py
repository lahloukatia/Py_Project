"""Modification des tags d'un fichier MP3 ou FLAC.

On utilise mutagen avec l'option easy=True : les tags ont alors les mêmes noms
pour un MP3 (ID3) et pour un FLAC (Vorbis comment), par exemple "title" ou "artist".
On n'a donc pas besoin de traiter les deux formats séparément.

Dépendance : mutagen  (pip install mutagen)
"""
import os

import mutagen

# Nom utilisé en ligne de commande -> nom du tag dans mutagen
TAGS = {
    "titre": "title",
    "artiste": "artist",
    "album": "album",
    "artiste_album": "albumartist",
    "date": "date",
    "genre": "genre",
    "piste": "tracknumber",
}


class TagError(Exception):
    """Erreur lors de la modification des tags."""


def lire_tags(path):
    """Renvoie un dictionnaire {nom: valeur actuelle} pour les tags modifiables."""
    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise TagError(f"Format non reconnu : {path}")
    valeurs = {}
    for nom, cle in TAGS.items():
        if audio.tags is not None and cle in audio.tags:
            valeurs[nom] = audio.tags[cle][0]
        else:
            valeurs[nom] = ""
    return valeurs


def verifier_valeur(nom, valeur):
    """Vérifie le format de la date et du numéro de piste. Une valeur vide est acceptée."""
    if valeur == "":
        return
    if nom == "date":
        # on accepte une année (2013) ou une date complète (2013-05-17)
        morceaux = valeur.split("-")
        if not all(m.isdigit() for m in morceaux) or len(morceaux[0]) != 4 or len(morceaux) > 3:
            raise TagError(f"Date invalide : {valeur} (exemples : 2013 ou 2013-05-17)")
    if nom == "piste":
        # on accepte 3 ou 3/12
        morceaux = valeur.split("/")
        if not all(m.isdigit() for m in morceaux) or len(morceaux) > 2:
            raise TagError(f"Numéro de piste invalide : {valeur} (exemples : 3 ou 3/12)")


def modifier_tags(path, changements):
    """Modifie les tags du fichier puis l'enregistre.

    changements : dictionnaire {nom: nouvelle valeur}, par exemple {"titre": "Get Lucky"}.
    Une valeur vide supprime le tag.
    """
    if not os.path.isfile(path):
        raise TagError(f"Fichier introuvable : {path}")
    if not path.lower().endswith((".mp3", ".flac")):
        raise TagError(f"Format non supporté (MP3 ou FLAC attendu) : {path}")

    # on vérifie tout avant d'écrire, pour ne pas modifier le fichier à moitié
    for nom, valeur in changements.items():
        if nom not in TAGS:
            raise TagError(f"Tag inconnu : {nom} (tags possibles : {', '.join(TAGS)})")
        verifier_valeur(nom, valeur)

    try:
        audio = mutagen.File(path, easy=True)
        if audio is None:
            raise TagError(f"Format non reconnu : {path}")
        if audio.tags is None:
            audio.add_tags()       # le fichier n'avait encore aucun tag

        for nom, valeur in changements.items():
            cle = TAGS[nom]
            if valeur == "":
                if cle in audio.tags:
                    del audio.tags[cle]
            else:
                audio.tags[cle] = valeur

        audio.save()
    except TagError:
        raise
    except Exception as e:
        raise TagError(f"Impossible de modifier {path} : {e}")


def lire_options_s(liste):
    """Transforme ["titre=Get Lucky", "genre=Rock"] en {"titre": "Get Lucky", "genre": "Rock"}."""
    changements = {}
    for element in liste:
        if "=" not in element:
            raise TagError(f"Format attendu : CLE=VALEUR (reçu : {element})")
        nom, valeur = element.split("=", 1)
        changements[nom.strip().lower()] = valeur.strip()
    return changements
