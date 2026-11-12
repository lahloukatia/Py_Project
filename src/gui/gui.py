
import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from library.explorer import scan_directory


# Palette de couleurs
CREME = "#F5EBDD"
BEIGE = "#E8D5BE"
CARAMEL = "#C7A98B"
MARRON = "#8B6248"
CHOCOLAT = "#4E3528"
BLANC = "#FFF9F1"



class FolderSelector:
    """Fenêtre personnalisée pour choisir un dossier."""

    def __init__(self, parent, on_select):
        self.on_select = on_select
        self.current_directory = os.path.expanduser("~")
        self.folders = []

        self.window = tk.Toplevel(parent)
        self.window.title("Choisir un dossier")
        self.window.geometry("560x500")
        self.window.configure(bg=CREME)
        self.window.transient(parent)
        self.window.grab_set()

        # Titre
        tk.Label(
            self.window,
            text="Choisir un dossier",
            font=("Georgia", 19, "bold"),
            bg=CREME,
            fg=CHOCOLAT
        ).pack(pady=(25, 15))

        # Barre de navigation
        navigation = tk.Frame(self.window, bg=BEIGE, padx=12, pady=12)
        navigation.pack(fill="x", padx=25)

        tk.Button(
            navigation,
            text="← Retour",
            command=self.go_back,
            bg=CARAMEL,
            fg=CHOCOLAT,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=5
        ).pack(side="left")

        self.path_label = tk.Label(
            navigation,
            text="",
            bg=BEIGE,
            fg=CHOCOLAT,
            font=("Arial", 10),
            anchor="w"
        )
        self.path_label.pack(side="left", padx=12, fill="x", expand=True)

        # Zone de navigation
        content = tk.Frame(self.window, bg=BLANC, padx=12, pady=12)
        content.pack(fill="both", expand=True, padx=25, pady=15)

        scrollbar = tk.Scrollbar(content)
        scrollbar.pack(side="right", fill="y")

        self.folder_list = tk.Listbox(
            content,
            font=("Arial", 12),
            bg=BLANC,
            fg=CHOCOLAT,
            selectbackground=CARAMEL,
            selectforeground=CHOCOLAT,
            relief="flat",
            highlightthickness=0,
            activestyle="none",
            yscrollcommand=scrollbar.set
        )
        self.folder_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.folder_list.yview)

        self.folder_list.bind("<Double-Button-1>", self.open_folder)

        # Boutons du bas
        buttons = tk.Frame(self.window, bg=CREME)
        buttons.pack(pady=(0, 25))

        tk.Button(
            buttons,
            text="Annuler",
            command=self.window.destroy,
            bg=BEIGE,
            fg=CHOCOLAT,
            relief="flat",
            cursor="hand2",
            padx=22,
            pady=10
        ).pack(side="left", padx=8)

        tk.Button(
            buttons,
            text="Sélectionner",
            command=self.select_folder,
            bg=MARRON,
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=22,
            pady=10
        ).pack(side="left", padx=8)

        self.refresh_folders()

    def refresh_folders(self):
        self.folder_list.delete(0, tk.END)
        self.path_label.config(text=self.current_directory)

        try:
            self.folders = sorted(
                [
                    name for name in os.listdir(self.current_directory)
                    if os.path.isdir(
                        os.path.join(self.current_directory, name)
                    )
                ],
                key=str.lower
            )

            for folder in self.folders:
                self.folder_list.insert(tk.END, "  ›   " + folder)

        except OSError as error:
            messagebox.showerror(
                "Erreur",
                str(error),
                parent=self.window
            )
            self.folders = []

    def open_folder(self, event):
        selection = self.folder_list.curselection()

        if not selection:
            return

        folder = self.folders[selection[0]]
        new_directory = os.path.join(self.current_directory, folder)

        self.current_directory = new_directory
        self.refresh_folders()

    def go_back(self):
        parent_directory = os.path.dirname(self.current_directory)

        if parent_directory != self.current_directory:
            self.current_directory = parent_directory
            self.refresh_folders()

    def select_folder(self):
        directory = self.current_directory
        self.window.destroy()
        self.on_select(directory)


class MusicGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ma bibliothèque musicale")
        self.root.geometry("750x550")
        self.root.configure(bg=CREME)

        tk.Label(
            root,
            text="Ma bibliothèque musicale",
            font=("Georgia", 23, "bold"),
            bg=CREME,
            fg=CHOCOLAT
        ).pack(pady=(30, 20))

        tk.Button(
            root,
            text="Choisir un dossier",
            command=self.choose_directory,
            font=("Arial", 12, "bold"),
            bg=MARRON,
            fg="white",
            activebackground=CHOCOLAT,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=10
        ).pack(pady=10)

        frame = tk.Frame(
            root,
            bg=BEIGE,
            padx=20,
            pady=20
        )
        frame.pack(padx=45, pady=20, fill="both", expand=True)

        tk.Label(
            frame,
            text="Mes morceaux",
            font=("Georgia", 16, "bold"),
            bg=BEIGE,
            fg=CHOCOLAT
        ).pack(anchor="w", pady=(0, 12))

        self.file_list = tk.Listbox(
            frame,
            bg=CREME,
            fg=CHOCOLAT,
            selectbackground=CARAMEL,
            selectforeground=CHOCOLAT,
            font=("Arial", 11),
            relief="flat",
            highlightthickness=0,
            activestyle="none"
        )
        self.file_list.pack(fill="both", expand=True)

        self.status = tk.Label(
            root,
            text="Aucun dossier sélectionné",
            font=("Arial", 10),
            bg=CREME,
            fg=MARRON
        )
        self.status.pack(pady=(0, 20))

    def choose_directory(self):
        FolderSelector(self.root, self.load_directory)

    def load_directory(self, directory):
        try:
            files = scan_directory(directory)
            self.file_list.delete(0, tk.END)

            for file in files:
                self.file_list.insert(
                    tk.END,
                    "  ♪  " + os.path.basename(file)
                )

            self.status.config(
                text=f"{len(files)} morceau(x) trouvé(s)"
            )

        except Exception as error:
            messagebox.showerror("Erreur", str(error))


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicGUI(root)
    root.mainloop()
