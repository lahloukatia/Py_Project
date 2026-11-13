"""Interface graphique du projet MP3/FLAC.

Lancement depuis la racine du dépôt : python3 src/gui/gui.py
Dépendances : mutagen, pygame ; Pillow facultatif pour afficher les pochettes.
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library import explorer
from library.metadata import MetadataError, extract_metadata
from library.playlist import load_playlist, save_playlist, tracks_from_paths
from library.tags import TAG_LABELS, TagError, current_tags, write_tags
from library.webapi import fetch_album_info
from library.player import AudioPlayer, PlayerError

CREME = "#F5EBDD"
BEIGE = "#E8D5BE"
CARAMEL = "#C7A98B"
MARRON = "#8B6248"
CHOCOLAT = "#4E3528"
BLANC = "#FFF9F1"


def friendly_error(error):
    return str(error) or type(error).__name__


class MusicGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bibliothèque musicale MP3 / FLAC")
        self.root.geometry("1170x760")
        self.root.minsize(950, 620)
        self.root.configure(bg=CREME)
        self.paths = []
        self.directory = None
        self.player = None
        self.playing_index = None
        self.paused = False
        self.track_meta = {}
        self.album_info = None
        self.cover_photo = None
        self.request_serial = 0
        self.status_var = tk.StringVar(value="Choisissez un dossier ou ouvrez une playlist XSPF.")
        self.now_var = tk.StringVar(value="Aucune lecture en cours")
        self._configure_style()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(500, self._poll_player)

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=CREME)
        style.configure("TLabel", background=CREME, foreground=CHOCOLAT, font=("Arial", 10))
        style.configure("Title.TLabel", font=("Arial", 20, "bold"), background=CREME, foreground=CHOCOLAT)
        style.configure("TButton", font=("Arial", 10, "bold"), padding=(10, 8), background=CARAMEL, foreground=CHOCOLAT)
        style.map("TButton", background=[("active", BEIGE), ("disabled", BEIGE)])
        style.configure("TNotebook", background=CREME)
        style.configure("TNotebook.Tab", background=BEIGE, foreground=CHOCOLAT, padding=(12, 8))
        style.map("TNotebook.Tab",
                  background=[("selected", CARAMEL)],
                  padding=[("selected", (12, 8))])

    def _build(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=18, pady=(15, 8))
        ttk.Label(header, text="Ma bibliothèque musicale", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="MP3 • FLAC • Playlists XSPF • Tags • Albums et paroles").pack(anchor="w", pady=(3, 0))

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=18, pady=8)
        ttk.Button(actions, text="Choisir un dossier", command=self.choose_folder).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Ouvrir une playlist", command=self.open_playlist_dialog).pack(side="left", padx=7)
        ttk.Button(actions, text="Enregistrer en XSPF", command=self.save_playlist_dialog).pack(side="left", padx=7)
        ttk.Button(actions, text="Actualiser", command=self.refresh).pack(side="left", padx=7)

        content = ttk.Panedwindow(self.root, orient="horizontal")
        content.pack(fill="both", expand=True, padx=18, pady=8)
        left = ttk.Frame(content)
        right = ttk.Frame(content)
        content.add(left, weight=2)
        content.add(right, weight=3)

        ttk.Label(left, text="Morceaux", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 6))
        listframe = ttk.Frame(left)
        listframe.pack(fill="both", expand=True, padx=(0, 10))
        self.listbox = tk.Listbox(listframe, bg=BLANC, fg=CHOCOLAT, selectbackground=MARRON,
                                  selectforeground="white", font=("Arial", 10), relief="flat",
                                  highlightthickness=1, highlightbackground=CARAMEL, exportselection=False)
        scrollbar = ttk.Scrollbar(listframe, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.show_selected)
        self.listbox.bind("<Double-Button-1>", lambda event: self.play_selected())

        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=10)

        for label, fn in (("Lecture", self.play_selected), ("Pause", self.pause),
                          ("Reprendre", self.resume), ("Stop", self.stop)):
            ttk.Button(
                controls,
                text=label,
                command=fn,
                width=9
            ).pack(side="left", padx=(0, 5))

        ttk.Label(left, textvariable=self.now_var, wraplength=370).pack(anchor="w", pady=(0, 5))

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)
        meta_tab = ttk.Frame(self.notebook)
        album_tab = ttk.Frame(self.notebook)
        self.notebook.add(meta_tab, text="Métadonnées")
        self.notebook.add(album_tab, text="Album et paroles")

        meta_toolbar = ttk.Frame(meta_tab)
        meta_toolbar.pack(fill="x", pady=(8, 5), padx=8)
        ttk.Button(meta_toolbar, text="Modifier les tags", command=self.edit_tags).pack(side="left")
        self.meta_text = self._text_area(meta_tab)
        self._set_text(self.meta_text, "Sélectionnez un morceau pour afficher ses métadonnées.")

        album_toolbar = ttk.Frame(album_tab)
        album_toolbar.pack(fill="x", pady=(8, 5), padx=8)
        self.album_btn = ttk.Button(album_toolbar, text="Rechercher l'album", command=self.search_album)
        self.album_btn.pack(side="left", padx=(0, 8))
        ttk.Button(album_toolbar, text="Ouvrir la pochette", command=self.open_cover).pack(side="left")
        self.album_text = self._text_area(album_tab)
        self._set_text(self.album_text, "Sélectionnez un morceau, puis cliquez sur « Rechercher l'album ».\nLa recherche des paroles peut prendre du temps.")

        status = tk.Label(self.root, textvariable=self.status_var, bg=BEIGE, fg=CHOCOLAT,
                          anchor="w", padx=14, pady=9)
        status.pack(fill="x", side="bottom")

    def _text_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        widget = tk.Text(frame, wrap="word", bg=BLANC, fg=CHOCOLAT, relief="flat",
                         font=("Arial", 10), padx=12, pady=12, state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        widget.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return widget

    @staticmethod
    def _set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def selected_index(self):
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def selected_path(self):
        index = self.selected_index()
        return self.paths[index] if index is not None and index < len(self.paths) else None

    def _set_files(self, paths, description):
        self.stop()
        self.paths = list(paths)
        self.track_meta.clear()
        self.album_info = None
        self.cover_photo = None
        self.request_serial += 1
        self.listbox.delete(0, "end")
        for path in self.paths:
            self.listbox.insert("end", os.path.basename(path))
        self._set_text(self.meta_text, "Sélectionnez un morceau pour afficher ses métadonnées.")
        self._set_text(self.album_text, "Sélectionnez un morceau pour rechercher son album.")
        self.status_var.set(f"{description} — {len(self.paths)} morceau(x)")
        if self.paths:
            self.listbox.selection_set(0)
            self.show_selected()

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Choisir un dossier de musique", initialdir=self.directory or str(Path.home()))
        if folder:
            self.load_directory(folder)

    def load_directory(self, folder):
        try:
            if hasattr(explorer, "explore"):
                result = explorer.explore(folder)
                paths = result.files
                rejected = getattr(result, "rejected", [])
                errors = getattr(result, "errors", [])
            else:
                paths = explorer.scan_directory(folder)
                rejected = []
                errors = []
        except (OSError, ValueError) as exc:
            messagebox.showerror("Exploration impossible", friendly_error(exc), parent=self.root)
            return
        self.directory = folder
        self._set_files(paths, f"Dossier : {folder}")
        if errors or rejected:
            self.status_var.set(f"{len(paths)} morceau(x) • {len(rejected)} fichier(s) rejeté(s) • {len(errors)} erreur(s) de parcours")
        if not paths:
            messagebox.showinfo("Aucun fichier audio", "Aucun MP3/FLAC valide trouvé dans ce dossier.", parent=self.root)

    def refresh(self):
        if self.directory:
            self.load_directory(self.directory)
        else:
            self.status_var.set("Ouvrez un dossier pour actualiser son contenu.")

    def open_playlist_dialog(self):
        path = filedialog.askopenfilename(parent=self.root, title="Ouvrir une playlist XSPF",
                                          filetypes=[("Playlists XSPF", "*.xspf"), ("Tous les fichiers", "*.*")])
        if path:
            self.open_playlist(path)

    def open_playlist(self, path):
        try:
            raw_paths = load_playlist(path)
        except Exception as exc:
            messagebox.showerror("Playlist invalide", friendly_error(exc), parent=self.root)
            return
        # Résout les chemins relatifs, sans changer le module playlist.py du groupe.
        base = os.path.dirname(os.path.abspath(path))
        paths = []
        for item in raw_paths:
            if item.startswith("file://"):
                from urllib.parse import unquote, urlparse
                item = unquote(urlparse(item).path)
            if not os.path.isabs(item):
                item = os.path.join(base, item)
            paths.append(os.path.normpath(item))
        available = [p for p in paths if os.path.isfile(p)]
        missing = len(paths) - len(available)
        self.directory = None
        self._set_files(available, f"Playlist : {os.path.basename(path)}")
        if missing:
            messagebox.showwarning("Fichiers manquants", f"{missing} morceau(x) de cette playlist sont introuvables.\n\nLes chemins enregistrés peuvent provenir d'un autre ordinateur ou système (Windows / WSL).", parent=self.root)
        if not paths:
            messagebox.showinfo("Playlist vide", "Ce fichier XSPF ne contient aucune piste.", parent=self.root)

    def save_playlist_dialog(self):
        if not self.paths:
            messagebox.showinfo("Playlist vide", "Chargez d'abord des morceaux.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Enregistrer la playlist",
                                             defaultextension=".xspf", initialfile="ma_playlist.xspf",
                                             filetypes=[("Playlists XSPF", "*.xspf")])
        if not path:
            return
        tracks, errors = tracks_from_paths(self.paths)
        if not tracks:
            messagebox.showerror("Enregistrement impossible", "Aucun morceau lisible à enregistrer.", parent=self.root)
            return
        try:
            save_playlist(tracks, path, title=Path(path).stem)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Enregistrement impossible", friendly_error(exc), parent=self.root)
            return
        self.status_var.set(f"Playlist enregistrée : {path} ({len(tracks)} piste(s))")
        if errors:
            messagebox.showwarning("Morceaux ignorés", f"{len(errors)} fichier(s) illisible(s) n'ont pas été ajoutés.", parent=self.root)

    def _metadata_for(self, path):
        if path not in self.track_meta:
            self.track_meta[path] = extract_metadata(path)
        return self.track_meta[path]

    def show_selected(self, event=None):
        path = self.selected_path()
        if not path:
            return
        try:
            meta = self._metadata_for(path)
        except MetadataError as exc:
            self._set_text(self.meta_text, friendly_error(exc))
            return
        self._set_text(self.meta_text, str(meta) + f"\nChemin complet : {meta.path}")

    def _ensure_player(self):
        if self.player is None:
            self.player = AudioPlayer()
        return self.player

    def play_selected(self):
        path = self.selected_path()
        if not path:
            messagebox.showinfo("Lecture", "Sélectionnez d'abord un morceau.", parent=self.root)
            return
        try:
            extract_metadata(path)
            self._ensure_player().play(path)
        except (PlayerError, MetadataError, OSError) as exc:
            messagebox.showerror("Lecture impossible", friendly_error(exc), parent=self.root)
            return
        self.playing_index = self.selected_index()
        self.paused = False
        self.now_var.set(f"Lecture : {os.path.basename(path)}")

    def pause(self):
        if self.player and self.playing_index is not None and not self.paused:
            self.player.pause()
            self.paused = True
            self.now_var.set("Lecture en pause")

    def resume(self):
        if self.player and self.playing_index is not None and self.paused:
            self.player.resume()
            self.paused = False
            self.now_var.set(f"Lecture : {os.path.basename(self.paths[self.playing_index])}")

    def stop(self):
        if self.player:
            self.player.stop()
        self.playing_index = None
        self.paused = False
        self.now_var.set("Aucune lecture en cours")

    def _poll_player(self):
        # Enchaîne les morceaux sans bloquer l'interface Tkinter.
        try:
            if self.player and self.playing_index is not None and not self.paused and not self.player.is_playing():
                next_index = self.playing_index + 1
                if next_index < len(self.paths):
                    self.listbox.selection_clear(0, "end")
                    self.listbox.selection_set(next_index)
                    self.listbox.see(next_index)
                    self.show_selected()
                    self.play_selected()
                else:
                    self.stop()
        except Exception as exc:
            self.stop()
            self.status_var.set(f"Erreur de lecture : {friendly_error(exc)}")
        finally:
            self.root.after(500, self._poll_player)

    def edit_tags(self):
        path = self.selected_path()
        if not path:
            messagebox.showinfo("Tags", "Sélectionnez d'abord un morceau.", parent=self.root)
            return
        try:
            meta = self._metadata_for(path)
        except MetadataError as exc:
            messagebox.showerror("Tags", friendly_error(exc), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier les métadonnées")
        dialog.configure(bg=CREME)
        dialog.geometry("540x490")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=os.path.basename(path), font=("Arial", 12, "bold"), wraplength=480).pack(pady=14)
        form = ttk.Frame(dialog)
        form.pack(fill="both", expand=True, padx=22)
        entries = {}
        for row, (key, value) in enumerate(current_tags(meta).items()):
            ttk.Label(form, text=TAG_LABELS.get(key, key)).grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(form, width=45)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=6)
            entries[key] = entry
        form.columnconfigure(1, weight=1)

        def save():
            old = current_tags(meta)
            changes = {key: widget.get().strip() for key, widget in entries.items()
                       if widget.get().strip() != old[key]}
            if not changes:
                dialog.destroy()
                return
            if self.playing_index is not None and self.paths[self.playing_index] == path:
                self.stop()
            try:
                updated = write_tags(path, changes)
            except (TagError, MetadataError, OSError) as exc:
                messagebox.showerror("Écriture impossible", friendly_error(exc), parent=dialog)
                return
            self.track_meta[path] = updated
            self.show_selected()
            self.status_var.set(f"Tags enregistrés : {os.path.basename(path)}")
            dialog.destroy()
        ttk.Button(dialog, text="Enregistrer les modifications", command=save).pack(pady=14)

    def search_album(self):
        path = self.selected_path()
        if not path:
            messagebox.showinfo("Album", "Sélectionnez d'abord un morceau.", parent=self.root)
            return
        try:
            meta = self._metadata_for(path)
        except MetadataError as exc:
            messagebox.showerror("Album", friendly_error(exc), parent=self.root)
            return
        if not meta.album:
            messagebox.showwarning("Album inconnu", "Le morceau ne possède pas de tag album. Vous pouvez le renseigner avec « Modifier les tags ».", parent=self.root)
            return
        self.request_serial += 1
        serial = self.request_serial
        self.album_btn.configure(state="disabled")
        self._set_text(self.album_text, f"Recherche de « {meta.album} »…\nTéléchargement des informations et des paroles, veuillez patienter.")

        def worker():
            try:
                info = fetch_album_info(meta.album_artist or meta.artist, meta.album, with_lyrics=True)
                result = (info, None)
            except Exception as exc:
                result = (None, exc)
            self.root.after(0, lambda: self._album_result(serial, *result))

        threading.Thread(target=worker, daemon=True).start()

    def _album_result(self, serial, info, error):
        if serial != self.request_serial:
            return
        self.album_btn.configure(state="normal")
        if error:
            self._set_text(self.album_text, f"Recherche impossible : {friendly_error(error)}")
            return
        self.album_info = info
        lines = [str(info), "", "PAROLES", "=" * 35]
        for track in info.tracks:
            lines.extend(["", f"{track.position}. {track.title}", "-" * 30,
                          track.lyrics or "(Paroles introuvables)"])
        self._set_text(self.album_text, "\n".join(lines))
        self.status_var.set(f"Album trouvé : {info.title} — {len(info.tracks)} piste(s)")

    def open_cover(self):
        if not self.album_info or not self.album_info.cover_url:
            messagebox.showinfo("Pochette", "Aucune pochette disponible. Recherchez d'abord un album.", parent=self.root)
            return
        webbrowser.open(self.album_info.cover_url)

    def close(self):
        self.request_serial += 1
        if self.player:
            try:
                self.player.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    MusicGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
