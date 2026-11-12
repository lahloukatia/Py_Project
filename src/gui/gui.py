import os
import sys
import tkinter as tk
from tkinter import messagebox

# Accès aux modules du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from library.explorer import scan_directory
from library.metadata import extract_metadata, is_supported_file, MetadataError
from library.playlist import (
    DEFAULT_PLAYLIST_NAME,
    load_playlist,
    save_playlist,
    tracks_from_paths,
)

# Couleurs de l'interface
CREME = "#F5EBDD"
BEIGE = "#E8D5BE"
CARAMEL = "#C7A98B"
MARRON = "#8B6248"
CHOCOLAT = "#4E3528"
BLANC = "#FFF9F1"


def contient_audio_directement(directory):
    """Vérifie si un dossier contient directement un MP3 ou un FLAC."""
    try:
        with os.scandir(directory) as elements:
            return any(
                element.is_file(follow_symlinks=False)
                and is_supported_file(element.path)
                for element in elements
            )
    except OSError:
        return False


class FolderSelector:
    """Fenêtre de navigation dans les dossiers."""

    def __init__(self, parent, on_select, initial_directory=None):
        self.on_select = on_select
        self.current_directory = initial_directory or os.path.expanduser("~")
        self.folders = []

        self.window = tk.Toplevel(parent)
        self.window.title("Choisir un dossier")
        self.window.geometry("600x520")
        self.window.minsize(450, 400)
        self.window.configure(bg=CREME)
        self.window.transient(parent)
        self.window.grab_set()

        tk.Label(
            self.window, text="Choisir un dossier", font=("Georgia", 19, "bold"),
            bg=CREME, fg=CHOCOLAT
        ).pack(pady=(25, 15))

        # Navigation
        navigation = tk.Frame(self.window, bg=BEIGE, padx=12, pady=12)
        navigation.pack(fill="x", padx=25)

        tk.Button(
            navigation, text="← Retour", command=self.go_back,
            bg=CARAMEL, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=12, pady=6
        ).pack(side="left")

        self.path_label = tk.Label(
            navigation, text="", bg=BEIGE, fg=CHOCOLAT,
            font=("Arial", 10), anchor="w", wraplength=340
        )
        self.path_label.pack(side="left", padx=12, fill="x", expand=True)

        # Liste des dossiers
        content = tk.Frame(self.window, bg=BLANC, padx=12, pady=12)
        content.pack(fill="both", expand=True, padx=25, pady=15)

        scrollbar = tk.Scrollbar(content)
        scrollbar.pack(side="right", fill="y")

        self.folder_list = tk.Listbox(
            content, font=("Arial", 12), bg=BLANC, fg=CHOCOLAT,
            selectbackground=MARRON, selectforeground=BLANC,
            relief="flat", highlightthickness=0, activestyle="none",
            yscrollcommand=scrollbar.set
        )
        self.folder_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.folder_list.yview)
        self.folder_list.bind("<Double-Button-1>", self.open_folder)

        tk.Label(
            self.window, text="Caramel : contient directement des MP3 ou FLAC",
            bg=CREME, fg=MARRON, font=("Arial", 10)
        ).pack(pady=(0, 8))

        buttons = tk.Frame(self.window, bg=CREME)
        buttons.pack(pady=(0, 20))
        tk.Button(
            buttons, text="Annuler", command=self.window.destroy,
            bg=BEIGE, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=22, pady=10
        ).pack(side="left", padx=8)
        tk.Button(
            buttons, text="Sélectionner", command=self.select_folder,
            bg=MARRON, fg=BLANC, relief="flat", cursor="hand2",
            padx=22, pady=10
        ).pack(side="left", padx=8)

        self.refresh_folders()

    def refresh_folders(self):
        """Affiche les sous-dossiers et repère ceux contenant des musiques."""
        self.folder_list.delete(0, tk.END)
        self.path_label.config(text=self.current_directory)
        try:
            self.folders = sorted(
                [
                    name for name in os.listdir(self.current_directory)
                    if os.path.isdir(os.path.join(self.current_directory, name))
                ],
                key=str.lower
            )
        except OSError as error:
            self.folders = []
            messagebox.showerror("Erreur", str(error), parent=self.window)
            return

        for index, folder in enumerate(self.folders):
            path = os.path.join(self.current_directory, folder)
            has_audio = contient_audio_directement(path)
            self.folder_list.insert(tk.END, "  ›   " + folder)
            if has_audio:
                self.folder_list.itemconfig(index, bg=CARAMEL, fg=CHOCOLAT)

    def open_folder(self, event=None):
        """Ouvre le sous-dossier sélectionné."""
        selection = self.folder_list.curselection()
        if not selection:
            return
        self.current_directory = os.path.join(
            self.current_directory, self.folders[selection[0]]
        )
        self.refresh_folders()

    def go_back(self):
        """Revient au dossier parent."""
        parent_directory = os.path.dirname(self.current_directory)
        if parent_directory != self.current_directory:
            self.current_directory = parent_directory
            self.refresh_folders()

    def select_folder(self):
        """Valide le dossier courant."""
        directory = self.current_directory
        self.window.destroy()
        self.on_select(directory)


class PlaylistSaveDialog:
    """Fenêtre personnalisée d'enregistrement XSPF."""

    def __init__(self, parent, on_save):
        self.on_save = on_save
        self.current_directory = os.getcwd()

        self.window = tk.Toplevel(parent)
        self.window.title("Enregistrer la playlist")
        self.window.geometry("560x440")
        self.window.minsize(480, 420)
        self.window.configure(bg=CREME)
        self.window.transient(parent)
        self.window.grab_set()

        tk.Label(
            self.window, text="Enregistrer la playlist", font=("Georgia", 19, "bold"),
            bg=CREME, fg=CHOCOLAT
        ).pack(pady=(25, 20))

        frame = tk.Frame(self.window, bg=BEIGE, padx=20, pady=20)
        frame.pack(fill="x", padx=30)
        tk.Label(
            frame, text="Dossier de destination", font=("Arial", 11, "bold"),
            bg=BEIGE, fg=CHOCOLAT
        ).pack(anchor="w")

        self.path_label = tk.Label(
            frame, text=self.current_directory, font=("Arial", 10),
            bg=BLANC, fg=CHOCOLAT, anchor="w", padx=10, pady=8,
            wraplength=430
        )
        self.path_label.pack(fill="x", pady=(8, 12))

        tk.Button(
            frame, text="Changer de dossier", command=self.choose_directory,
            bg=CARAMEL, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=12, pady=6
        ).pack(anchor="w")

        tk.Label(
            self.window, text="Nom de la playlist", font=("Arial", 11, "bold"),
            bg=CREME, fg=CHOCOLAT
        ).pack(anchor="w", padx=30, pady=(18, 5))

        self.filename_entry = tk.Entry(
            self.window, font=("Arial", 11), bg=BLANC,
            fg=CHOCOLAT, relief="flat"
        )
        self.filename_entry.pack(fill="x", padx=30, ipady=8)
        self.filename_entry.insert(0, DEFAULT_PLAYLIST_NAME)

        buttons = tk.Frame(self.window, bg=CREME)
        buttons.pack(pady=20)
        tk.Button(
            buttons, text="Annuler", command=self.window.destroy,
            bg=BEIGE, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=25, pady=9
        ).pack(side="left", padx=8)
        tk.Button(
            buttons, text="Enregistrer", command=self.save,
            bg=MARRON, fg=BLANC, relief="flat", cursor="hand2",
            padx=25, pady=9
        ).pack(side="left", padx=8)

    def choose_directory(self):
        """Sélectionne le dossier de destination."""
        FolderSelector(self.window, self.set_directory, self.current_directory)

    def set_directory(self, directory):
        """Actualise le chemin de destination."""
        self.current_directory = directory
        self.path_label.config(text=directory)

    def save(self):
        """Valide le nom et l'emplacement du fichier."""
        filename = self.filename_entry.get().strip()
        if not filename or filename in (".", ".."):
            messagebox.showwarning(
                "Nom invalide", "Saisissez un nom de fichier valide.", parent=self.window
            )
            return
        if os.path.basename(filename) != filename or "\\" in filename or "/" in filename:
            messagebox.showwarning(
                "Nom invalide", "Saisissez un nom sans chemin de dossier.", parent=self.window
            )
            return
        if not filename.lower().endswith(".xspf"):
            filename += ".xspf"

        output_path = os.path.join(self.current_directory, filename)
        if os.path.exists(output_path):
            if not os.path.isfile(output_path):
                messagebox.showerror(
                    "Erreur", "Ce nom correspond déjà à un dossier.", parent=self.window
                )
                return
            if not messagebox.askyesno(
                "Fichier existant", "Cette playlist existe déjà. La remplacer ?",
                parent=self.window
            ):
                return

        self.window.destroy()
        self.on_save(output_path)


class PlaylistOpenDialog:
    """Fenêtre personnalisée pour ouvrir une playlist XSPF."""

    def __init__(self, parent, on_open):
        self.on_open = on_open
        self.current_directory = os.getcwd()
        self.folders = []
        self.playlists = []

        self.window = tk.Toplevel(parent)
        self.window.title("Ouvrir une playlist")
        self.window.geometry("620x550")
        self.window.minsize(480, 420)
        self.window.configure(bg=CREME)
        self.window.transient(parent)
        self.window.grab_set()

        tk.Label(
            self.window, text="Ouvrir une playlist XSPF",
            font=("Georgia", 19, "bold"), bg=CREME, fg=CHOCOLAT
        ).pack(pady=(22, 14))

        navigation = tk.Frame(self.window, bg=BEIGE, padx=12, pady=12)
        navigation.pack(fill="x", padx=25)
        tk.Button(
            navigation, text="← Retour", command=self.go_back,
            bg=CARAMEL, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=12, pady=6
        ).pack(side="left")
        self.path_label = tk.Label(
            navigation, text="", bg=BEIGE, fg=CHOCOLAT,
            font=("Arial", 10), anchor="w", wraplength=380
        )
        self.path_label.pack(side="left", padx=12, fill="x", expand=True)

        content = tk.Frame(self.window, bg=BLANC, padx=12, pady=12)
        content.pack(fill="both", expand=True, padx=25, pady=15)
        scrollbar = tk.Scrollbar(content)
        scrollbar.pack(side="right", fill="y")
        self.items_list = tk.Listbox(
            content, font=("Arial", 11), bg=BLANC, fg=CHOCOLAT,
            selectbackground=CARAMEL, selectforeground=CHOCOLAT,
            relief="flat", highlightthickness=0, activestyle="none",
            yscrollcommand=scrollbar.set
        )
        self.items_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.items_list.yview)
        self.items_list.bind("<Double-Button-1>", self.open_selected)

        tk.Label(
            self.window, text="Double-cliquez sur un dossier ou une playlist.",
            bg=CREME, fg=MARRON, font=("Arial", 10)
        ).pack(pady=(0, 8))

        buttons = tk.Frame(self.window, bg=CREME)
        buttons.pack(pady=(0, 20))
        tk.Button(
            buttons, text="Annuler", command=self.window.destroy,
            bg=BEIGE, fg=CHOCOLAT, relief="flat", cursor="hand2",
            padx=22, pady=10
        ).pack(side="left", padx=8)
        tk.Button(
            buttons, text="Ouvrir", command=self.open_selected,
            bg=MARRON, fg=BLANC, relief="flat", cursor="hand2",
            padx=22, pady=10
        ).pack(side="left", padx=8)
        self.refresh_items()

    def refresh_items(self):
        """Affiche les sous-dossiers et les fichiers XSPF."""
        self.items_list.delete(0, tk.END)
        self.path_label.config(text=self.current_directory)
        try:
            names = os.listdir(self.current_directory)
            self.folders = sorted(
                [n for n in names if os.path.isdir(os.path.join(self.current_directory, n))],
                key=str.lower
            )
            self.playlists = sorted(
                [n for n in names if n.lower().endswith(".xspf")
                 and os.path.isfile(os.path.join(self.current_directory, n))],
                key=str.lower
            )
        except OSError as error:
            self.folders, self.playlists = [], []
            messagebox.showerror("Erreur", str(error), parent=self.window)
            return

        for folder in self.folders:
            self.items_list.insert(tk.END, "  ›   " + folder)
        for playlist in self.playlists:
            index = self.items_list.size()
            self.items_list.insert(tk.END, "  -   " + playlist)
            self.items_list.itemconfig(index, bg=BEIGE, fg=CHOCOLAT)

    def go_back(self):
        """Revient au dossier parent."""
        parent_directory = os.path.dirname(self.current_directory)
        if parent_directory != self.current_directory:
            self.current_directory = parent_directory
            self.refresh_items()

    def open_selected(self, event=None):
        """Ouvre le dossier ou la playlist sélectionnée."""
        selection = self.items_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index < len(self.folders):
            self.current_directory = os.path.join(
                self.current_directory, self.folders[index]
            )
            self.refresh_items()
            return

        playlist_name = self.playlists[index - len(self.folders)]
        playlist_path = os.path.join(self.current_directory, playlist_name)
        self.window.destroy()
        self.on_open(playlist_path)


class MusicGUI:
    """Interface principale de la bibliothèque musicale."""

    def __init__(self, root):
        self.root = root
        self.files = []
        self.current_directory = None

        self.root.title("Ma bibliothèque musicale")
        self.root.geometry("1050x670")
        self.root.minsize(850, 520)
        self.root.configure(bg=CREME)

        tk.Label(
            root, text="Ma bibliothèque musicale", font=("Georgia", 23, "bold"),
            bg=CREME, fg=CHOCOLAT
        ).pack(pady=(25, 15))

        # Actions principales
        button_frame = tk.Frame(root, bg=CREME)
        button_frame.pack(pady=10)
        tk.Button(
            button_frame, text="Choisir un dossier", command=self.choose_directory,
            font=("Arial", 11, "bold"), bg=MARRON, fg=BLANC,
            activebackground=CHOCOLAT, activeforeground=BLANC,
            relief="flat", cursor="hand2", padx=14, pady=10
        ).pack(side="left", padx=6)
        self.export_button = tk.Button(
            button_frame, text="Enregistrer une playlist XSPF",
            command=self.export_playlist, font=("Arial", 11, "bold"),
            bg=CARAMEL, fg=CHOCOLAT, activebackground=MARRON,
            activeforeground=BLANC, relief="flat", cursor="hand2",
            padx=14, pady=10, state="disabled"
        )
        self.export_button.pack(side="left", padx=6)
        tk.Button(
            button_frame, text="Ouvrir une playlist XSPF",
            command=self.choose_playlist, font=("Arial", 11, "bold"),
            bg=BEIGE, fg=CHOCOLAT, activebackground=CARAMEL,
            relief="flat", cursor="hand2", padx=14, pady=10
        ).pack(side="left", padx=6)

        content = tk.Frame(root, bg=CREME)
        content.pack(padx=30, pady=20, fill="both", expand=True)

        # Liste des morceaux
        left_frame = tk.Frame(content, bg=BEIGE, padx=15, pady=15)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(
            left_frame, text="Mes morceaux", font=("Georgia", 16, "bold"),
            bg=BEIGE, fg=CHOCOLAT
        ).pack(anchor="w", pady=(0, 12))
        list_container = tk.Frame(left_frame, bg=BLANC)
        list_container.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side="right", fill="y")
        self.file_list = tk.Listbox(
            list_container, bg=BLANC, fg=CHOCOLAT,
            selectbackground=CARAMEL, selectforeground=CHOCOLAT,
            font=("Arial", 11), relief="flat", highlightthickness=0,
            activestyle="none", yscrollcommand=scrollbar.set
        )
        self.file_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.file_list.yview)
        self.file_list.bind("<<ListboxSelect>>", self.show_metadata)

        # Informations du morceau
        right_frame = tk.Frame(content, bg=BEIGE, padx=15, pady=15)
        right_frame.pack(side="right", fill="both", expand=True, padx=(8, 0))
        tk.Label(
            right_frame, text="Informations du morceau",
            font=("Georgia", 15, "bold"), bg=BEIGE, fg=CHOCOLAT
        ).pack(anchor="w", pady=(0, 12))
        metadata_container = tk.Frame(right_frame, bg=BLANC)
        metadata_container.pack(fill="both", expand=True)
        metadata_scrollbar = tk.Scrollbar(metadata_container)
        metadata_scrollbar.pack(side="right", fill="y")
        self.metadata_text = tk.Text(
            metadata_container, bg=BLANC, fg=CHOCOLAT,
            font=("Arial", 11), relief="flat", highlightthickness=0,
            wrap="word", padx=15, pady=15,
            yscrollcommand=metadata_scrollbar.set, state="disabled"
        )
        self.metadata_text.pack(side="left", fill="both", expand=True)
        metadata_scrollbar.config(command=self.metadata_text.yview)
        self.set_metadata_text("Sélectionnez un morceau")

        self.status = tk.Label(
            root, text="Aucun dossier sélectionné", font=("Arial", 10),
            bg=CREME, fg=MARRON
        )
        self.status.pack(pady=(0, 20))

    def set_metadata_text(self, text):
        """Actualise le panneau des métadonnées."""
        self.metadata_text.config(state="normal")
        self.metadata_text.delete("1.0", tk.END)
        self.metadata_text.insert("1.0", text)
        self.metadata_text.config(state="disabled")
        self.metadata_text.yview_moveto(0)

    def set_files(self, files):
        """Actualise la liste des morceaux affichés."""
        self.files = list(files)
        self.file_list.delete(0, tk.END)
        self.set_metadata_text("Sélectionnez un morceau")
        for path in self.files:
            self.file_list.insert(tk.END, "  -  " + os.path.basename(path))
        self.export_button.config(state="normal" if self.files else "disabled")

    def choose_directory(self):
        """Ouvre la fenêtre de sélection des dossiers."""
        FolderSelector(self.root, self.load_directory)

    def load_directory(self, directory):
        """Recherche les musiques dans un dossier."""
        try:
            files = scan_directory(directory)
        except Exception as error:
            messagebox.showerror("Erreur", str(error), parent=self.root)
            return
        self.current_directory = directory
        self.set_files(files)
        self.status.config(text=f"{len(files)} morceau(x) trouvé(s)")
        if not files:
            self.set_metadata_text("Aucun fichier MP3 ou FLAC trouvé.")

    def show_metadata(self, event=None):
        """Affiche les informations du morceau sélectionné."""
        selection = self.file_list.curselection()
        if not selection or selection[0] >= len(self.files):
            return
        try:
            metadata = extract_metadata(self.files[selection[0]])
            informations = (
                f"Titre : {metadata.title or '-'}\n\n"
                f"Artiste : {metadata.artist or '-'}\n\n"
                f"Album : {metadata.album or '-'}\n\n"
                f"Artiste album : {metadata.album_artist or '-'}\n\n"
                f"Date : {metadata.date or '-'}\n\n"
                f"Genre : {metadata.genre or '-'}\n\n"
                f"Piste n° : {metadata.track_number or '-'}\n\n"
                f"Durée : {metadata.duration_str}\n\n"
                f"Format : {metadata.format}\n\n"
                f"Débit : {metadata.bitrate // 1000} kbit/s\n\n"
                f"Fréquence : {metadata.sample_rate} Hz\n\n"
                f"Canaux : {metadata.channels}\n\n"
                f"Pochette : {'Oui' if metadata.has_cover else 'Non'}\n\n"
                f"Chemin : {metadata.path}"
            )
            self.set_metadata_text(informations)
        except MetadataError as error:
            self.set_metadata_text("Impossible de lire les métadonnées.")
            messagebox.showerror("Erreur de lecture", str(error), parent=self.root)

    def choose_playlist(self):
        """Ouvre le sélecteur de playlists."""
        PlaylistOpenDialog(self.root, self.open_playlist)

    def open_playlist(self, playlist_path):
        """Charge les morceaux référencés dans un fichier XSPF."""
        try:
            paths = load_playlist(playlist_path)
        except Exception as error:
            messagebox.showerror("Playlist invalide", str(error), parent=self.root)
            return

        available = [path for path in paths if os.path.isfile(path)]
        missing = len(paths) - len(available)
        self.current_directory = None
        self.set_files(available)
        self.status.config(
            text=f"Playlist : {os.path.basename(playlist_path)} — "
                 f"{len(available)} morceau(x) disponible(s)"
        )
        if not available:
            self.set_metadata_text("Aucun morceau accessible dans cette playlist.")
        if missing:
            messagebox.showwarning(
                "Fichiers introuvables",
                f"{missing} morceau(x) de la playlist sont introuvables.",
                parent=self.root
            )

    def export_playlist(self):
        """Ouvre la fenêtre d'enregistrement XSPF."""
        if not self.files:
            messagebox.showwarning(
                "Aucune musique", "Choisissez un dossier ou ouvrez une playlist.",
                parent=self.root
            )
            return
        PlaylistSaveDialog(self.root, self.save_xspf)

    def save_xspf(self, output_path):
        """Enregistre les morceaux affichés dans un fichier XSPF."""
        try:
            tracks, errors = tracks_from_paths(self.files)
            if not tracks:
                messagebox.showerror(
                    "Erreur", "Aucun morceau valide pour créer la playlist.",
                    parent=self.root
                )
                return
            save_playlist(tracks, output_path, title="Ma bibliothèque musicale")
            message = (
                f"Playlist enregistrée avec succès !\n\n"
                f"{len(tracks)} morceau(x) ajouté(s).\n\n"
                f"Fichier : {output_path}"
            )
            if errors:
                message += f"\n\n{len(errors)} fichier(s) n'ont pas pu être lus."
            messagebox.showinfo("Playlist enregistrée", message, parent=self.root)
            self.status.config(text=f"Playlist XSPF créée : {len(tracks)} morceau(x)")
        except (OSError, ValueError) as error:
            messagebox.showerror("Erreur d'export", str(error), parent=self.root)


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicGUI(root)
    root.mainloop()
