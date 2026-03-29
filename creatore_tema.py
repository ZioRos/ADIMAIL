import os
import re
import sqlite3
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import configparser
import qrcode
import threading
import queue
from tkinter import Tk, filedialog, messagebox
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont

# ==============================
# CONFIGURAZIONE
# ==============================

TEMPLATE_IMAGE = "qsl_template.png"
OUTPUT_DIR     = "qsl_output"
DB_FILE        = "qsl_records.db"
CONFIG_FILE    = "config.ini"

BASE_FONT_SIZE = 10
CALL_FONT_SIZE = 14

QR_POSITION_PERCENT = (0.83, 0.03)
QR_SIZE_PERCENT     = 0.12

TEXT_AREAS_PERCENT = {
    "CALL": (0.63, 0.33, 0.97, 0.22),
    "NAME": (0.63, 0.38, 0.97, 0.31),
    "DATE": (0.63, 0.42, 0.97, 0.43),
    "TIME": (0.63, 0.45, 0.97, 0.52),
    "MODE": (0.63, 0.48, 0.97, 0.61),
    "BAND": (0.63, 0.51, 0.97, 0.70),
    "RST":  (0.63, 0.54, 0.97, 0.79),
}

QR_URL = "https://iz8gch.jimdofree.com/"

# ══════════════════════════════════════════════════════════════════════════════
# PROGRAMMI SUPPORTATI (nome → chiave config)
# ══════════════════════════════════════════════════════════════════════════════
PROGRAMMI_SUPPORTATI = {
    "JTDX":     "JTDX",
    "WSJT-X":   "WSJTX",
    "MHSV":     "MHSV",
    "Decodium": "DECODIUM",
}

# Percorsi predefiniti tipici per ciascun programma (Windows / Linux)
DEFAULT_PATHS = {
    "JTDX": [
        os.path.expanduser(r"~\AppData\Local\JTDX\log\wsjtx_log.adi"),
        os.path.expanduser("~/.jtdx/wsjtx_log.adi"),
    ],
    "WSJTX": [
        os.path.expanduser(r"~\AppData\Local\WSJT-X\log\wsjtx_log.adi"),
        os.path.expanduser("~/.local/share/WSJT-X/wsjtx_log.adi"),
    ],
    "MHSV": [
        os.path.expanduser(r"~\AppData\Roaming\MHSV\log.adi"),
        os.path.expanduser("~/.mhsv/log.adi"),
    ],
    "DECODIUM": [
        os.path.expanduser(r"~\AppData\Roaming\Decodium\log.adi"),
        os.path.expanduser("~/.decodium/log.adi"),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# PALETTE TEMI
# ══════════════════════════════════════════════════════════════════════════════
TEMI = {
    "scuro": {
        "win_bg":           "#1e2530",
        "win_bg_alt":       "#252d3a",
        "fg":               "#d0dce8",
        "fg_dim":           "#5a7090",
        "accent":           "#4a9eca",
        "accent_hover":     "#5bb0de",
        "counter_green":    "#5dbb7a",
        "counter_blue":     "#4a9eca",
        "counter_red":      "#e05555",
        "counter_frame_bg": "#0d1f2d",
        "counter_label_fg": "#7090a8",
        "log_bg":           "#151e28",
        "log_fg":           "#b0cce0",
        "scrollbar_bg":     "#1a2a3a",
        "progress_trough":  "#0d1f2d",
        "title_fg":         "#4a9eca",
        "status_fg":        "#8aaac4",
        "pct_fg":           "#c8dce8",
        "ttk_theme":        "clam",
        "entry_bg":         "#0d1f2d",
        "entry_fg":         "#d0dce8",
        "check_bg":         "#1e2530",
        "btn_bg":           "#2a3a4a",
        "btn_fg":           "#d0dce8",
        "btn_active_bg":    "#4a9eca",
        "btn_active_fg":    "#ffffff",
        "sep_color":        "#2a3a4a",
        "badge_bg":         "#0d3050",
        "badge_fg":         "#4a9eca",
    },
    "chiaro": {
        "win_bg":           "#f0f4f8",
        "win_bg_alt":       "#ffffff",
        "fg":               "#1a2a3a",
        "fg_dim":           "#6a7f96",
        "accent":           "#1a3a5c",
        "accent_hover":     "#2a5a8c",
        "counter_green":    "#2a7d2a",
        "counter_blue":     "#1a5fa8",
        "counter_red":      "#c0392b",
        "counter_frame_bg": "#e0eaf4",
        "counter_label_fg": "#555555",
        "log_bg":           "#f8f8f8",
        "log_fg":           "#333333",
        "scrollbar_bg":     "#dde8f4",
        "progress_trough":  "#dde8f4",
        "title_fg":         "#1a3a5c",
        "status_fg":        "#444444",
        "pct_fg":           "#1a2a3a",
        "ttk_theme":        "clam",
        "entry_bg":         "#ffffff",
        "entry_fg":         "#1a2a3a",
        "check_bg":         "#f0f4f8",
        "btn_bg":           "#d0dce8",
        "btn_fg":           "#1a2a3a",
        "btn_active_bg":    "#1a3a5c",
        "btn_active_fg":    "#ffffff",
        "sep_color":        "#c0ccd8",
        "badge_bg":         "#d0e8f8",
        "badge_fg":         "#1a3a5c",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENZA TEMA
# ══════════════════════════════════════════════════════════════════════════════
def _leggi_tema_config() -> str:
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "UI" in config:
            t = config["UI"].get("tema", "scuro").lower()
            return t if t in TEMI else "scuro"
    return "scuro"

def _salva_tema_config(tema: str):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    if "UI" not in config:
        config["UI"] = {}
    config["UI"]["tema"] = tema
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)
            f.flush()
            os.fsync(f.fileno())
        print(f"[DEBUG] Tema salvato: {tema}")
    except Exception as e:
        print(f"[ERRORE] Salvataggio tema: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENZA PERCORSI PROGRAMMI
# ══════════════════════════════════════════════════════════════════════════════
def load_program_paths() -> dict:
    """Carica i percorsi salvati per ciascun programma da config.ini."""
    config = configparser.ConfigParser()
    paths  = {}
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    section = "PROGRAM_PATHS"
    if section in config:
        for key in PROGRAMMI_SUPPORTATI.values():
            paths[key] = config[section].get(key, "")
    else:
        for key in PROGRAMMI_SUPPORTATI.values():
            paths[key] = ""
    # Suggerisci percorso predefinito se non configurato
    for key, defaults in DEFAULT_PATHS.items():
        if not paths.get(key):
            for dp in defaults:
                if os.path.exists(dp):
                    paths[key] = dp
                    break
    return paths

def save_program_paths(paths: dict):
    """Salva i percorsi dei programmi in config.ini."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    section = "PROGRAM_PATHS"
    if section not in config:
        config[section] = {}
    for key, value in paths.items():
        config[section][key] = value
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)
            f.flush()
            os.fsync(f.fileno())
        print(f"[DEBUG] Percorsi programmi salvati in {CONFIG_FILE}")
    except Exception as e:
        print(f"[ERRORE] Salvataggio percorsi programmi: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# FINESTRA CONFIGURAZIONE PERCORSI PROGRAMMI
# ══════════════════════════════════════════════════════════════════════════════
class ProgramPathsWindow:
    """
    Finestra di configurazione per i percorsi ADIF dei programmi supportati.
    Permette di sfogliare/modificare i percorsi e salvarli in config.ini.
    """

    def __init__(self, parent, on_save_callback=None):
        self._tema_nome = _leggi_tema_config()
        self._p         = TEMI[self._tema_nome]
        self._on_save   = on_save_callback
        self._paths     = load_program_paths()
        self._entries   = {}   # chiave → tk.Entry

        self.win = tk.Toplevel(parent)
        self.win.title("Configurazione Percorsi Programmi ADIF")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._costruisci_ui()
        self._applica_tema()
        self.win.update_idletasks()
        self._centra_finestra()

    def _centra_finestra(self):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _costruisci_ui(self):
        p = self._p

        # ── Intestazione ──────────────────────────────────────────
        hdr = tk.Frame(self.win)
        hdr.pack(fill="x", padx=0, pady=0)

        tk.Label(hdr,
                 text="⚙  Percorsi file ADIF / ADI",
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=14, pady=10)

        self._btn_tema = tk.Button(
            hdr, text=self._etichetta_tema(),
            command=self._toggle_tema,
            relief=tk.FLAT, cursor="hand2",
            font=("Arial", 8), padx=8, pady=2)
        self._btn_tema.pack(side="right", padx=10, pady=8)

        tk.Label(self.win,
                 text="Configura il percorso del file di log (.adi/.adif) per ogni programma.",
                 font=("Helvetica", 9), wraplength=520).pack(padx=14, pady=(0, 6))

        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # ── Griglia programmi ─────────────────────────────────────
        grid_frame = tk.Frame(self.win)
        grid_frame.pack(fill="x", padx=12, pady=6)

        for row_idx, (label, key) in enumerate(PROGRAMMI_SUPPORTATI.items()):
            # Icona / label programma
            lbl = tk.Label(grid_frame, text=f"  {label}",
                           font=("Helvetica", 10, "bold"), width=12, anchor="w")
            lbl.grid(row=row_idx, column=0, padx=(4, 8), pady=6, sticky="w")

            # Entry percorso
            var = tk.StringVar(value=self._paths.get(key, ""))
            entry = tk.Entry(grid_frame, textvariable=var, width=48,
                             font=("Courier", 9))
            entry.grid(row=row_idx, column=1, padx=4, pady=6, sticky="ew")
            self._entries[key] = (entry, var)

            # Pulsante Sfoglia
            btn = tk.Button(grid_frame, text="📂 Sfoglia",
                            command=lambda k=key, v=var: self._sfoglia(k, v),
                            relief=tk.FLAT, cursor="hand2",
                            font=("Arial", 9), padx=8)
            btn.grid(row=row_idx, column=2, padx=(4, 2), pady=6)

            # Pulsante Cancella
            btn_clr = tk.Button(grid_frame, text="✕",
                                command=lambda v=var: v.set(""),
                                relief=tk.FLAT, cursor="hand2",
                                font=("Arial", 9), padx=6)
            btn_clr.grid(row=row_idx, column=3, padx=(0, 4), pady=6)

        grid_frame.columnconfigure(1, weight=1)

        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # ── Pulsanti azione ───────────────────────────────────────
        btn_frame = tk.Frame(self.win)
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        tk.Button(btn_frame, text="✔  Salva",
                  command=self._salva,
                  font=("Helvetica", 10, "bold"),
                  relief=tk.FLAT, cursor="hand2",
                  padx=18, pady=6).pack(side="right", padx=6)

        tk.Button(btn_frame, text="Annulla",
                  command=self.win.destroy,
                  font=("Helvetica", 10),
                  relief=tk.FLAT, cursor="hand2",
                  padx=14, pady=6).pack(side="right")

    def _sfoglia(self, key, var):
        path = filedialog.askopenfilename(
            parent=self.win,
            title=f"Seleziona file ADIF per {key}",
            filetypes=[("ADIF files", "*.adi *.adif"), ("Tutti i file", "*.*")]
        )
        if path:
            var.set(path)

    def _salva(self):
        new_paths = {}
        for key, (entry, var) in self._entries.items():
            new_paths[key] = var.get().strip()
        save_program_paths(new_paths)
        self._paths = new_paths
        if self._on_save:
            self._on_save(new_paths)
        messagebox.showinfo("Salvato", "Percorsi salvati correttamente.", parent=self.win)
        self.win.destroy()

    # ── Tema ─────────────────────────────────────────────────────
    def _etichetta_tema(self) -> str:
        return "☀  Tema chiaro" if self._tema_nome == "scuro" else "🌙  Tema scuro"

    def _toggle_tema(self):
        self._tema_nome = "chiaro" if self._tema_nome == "scuro" else "scuro"
        self._p = TEMI[self._tema_nome]
        _salva_tema_config(self._tema_nome)
        self._applica_tema()

    def _applica_tema(self):
        p = self._p
        self.win.configure(bg=p["win_bg"])
        self._btn_tema.configure(
            text=self._etichetta_tema(),
            bg=p["win_bg_alt"], fg=p["fg"],
            activebackground=p["accent"], activeforeground="#ffffff")
        self._ricorsivo_applica_tema(self.win, p)

    def _ricorsivo_applica_tema(self, widget, p):
        cls = widget.__class__.__name__
        try:
            if cls in ("Frame",):
                widget.configure(bg=p["win_bg"])
            elif cls == "Label":
                widget.configure(bg=p["win_bg"], fg=p["fg"])
            elif cls == "Entry":
                widget.configure(bg=p["entry_bg"], fg=p["entry_fg"],
                                 insertbackground=p["fg"],
                                 relief=tk.FLAT, highlightthickness=1,
                                 highlightbackground=p["sep_color"],
                                 highlightcolor=p["accent"])
            elif cls == "Button":
                widget.configure(bg=p["btn_bg"], fg=p["btn_fg"],
                                 activebackground=p["btn_active_bg"],
                                 activeforeground=p["btn_active_fg"],
                                 bd=0)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._ricorsivo_applica_tema(child, p)


# ══════════════════════════════════════════════════════════════════════════════
# FINESTRA SELEZIONE SORGENTI
# ══════════════════════════════════════════════════════════════════════════════
class SourceSelectionWindow:
    """
    Finestra per selezionare uno o più programmi da importare.
    Mostra badge di stato (percorso trovato / non configurato) per ciascuno.
    Restituisce la lista di (label, filepath) da importare tramite callback.
    """

    def __init__(self, parent, on_import_callback):
        self._tema_nome    = _leggi_tema_config()
        self._p            = TEMI[self._tema_nome]
        self._on_import    = on_import_callback
        self._paths        = load_program_paths()
        self._check_vars   = {}   # key → tk.BooleanVar
        self._result       = []

        self.win = tk.Toplevel(parent)
        self.win.title("Selezione Sorgenti ADIF")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._costruisci_ui()
        self._applica_tema()
        self.win.update_idletasks()
        self._centra_finestra()

    def _centra_finestra(self):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _costruisci_ui(self):
        p = self._p

        # ── Intestazione ──────────────────────────────────────────
        hdr = tk.Frame(self.win)
        hdr.pack(fill="x", padx=0, pady=0)

        tk.Label(hdr,
                 text="📡  Importazione QSL da ADIF",
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=14, pady=10)

        self._btn_tema = tk.Button(
            hdr, text=self._etichetta_tema(),
            command=self._toggle_tema,
            relief=tk.FLAT, cursor="hand2",
            font=("Arial", 8), padx=8, pady=2)
        self._btn_tema.pack(side="right", padx=10, pady=8)

        tk.Label(self.win,
                 text="Seleziona i programmi da cui importare i dati QSO.",
                 font=("Helvetica", 9)).pack(padx=14, pady=(0, 4))

        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # ── Lista programmi con checkbox ──────────────────────────
        list_frame = tk.Frame(self.win)
        list_frame.pack(fill="x", padx=14, pady=8)

        self._row_frames   = {}
        self._path_labels  = {}
        self._status_labels = {}

        for label, key in PROGRAMMI_SUPPORTATI.items():
            path = self._paths.get(key, "")
            exists = os.path.isfile(path)

            var = tk.BooleanVar(value=exists)
            self._check_vars[key] = var

            row = tk.Frame(list_frame)
            row.pack(fill="x", pady=4)
            self._row_frames[key] = row

            # Checkbox + nome programma
            cb = tk.Checkbutton(row, text=f"  {label}",
                                variable=var,
                                font=("Helvetica", 11, "bold"),
                                cursor="hand2",
                                anchor="w")
            cb.pack(side="left")

            # Badge di stato
            if exists:
                badge_text = "✔ Trovato"
                badge_ok   = True
            elif path:
                badge_text = "⚠ File assente"
                badge_ok   = False
            else:
                badge_text = "○ Non configurato"
                badge_ok   = False

            status_lbl = tk.Label(row, text=badge_text,
                                  font=("Arial", 8, "bold"),
                                  padx=6, pady=2)
            status_lbl.pack(side="left", padx=8)
            self._status_labels[key] = (status_lbl, badge_ok)

            # Percorso / pulsante sfoglia inline
            path_var = tk.StringVar(value=path)

            path_lbl = tk.Label(row,
                                text=self._trunca_path(path) if path else "— nessun percorso —",
                                font=("Courier", 8),
                                anchor="w", cursor="hand2")
            path_lbl.pack(side="left", padx=4, fill="x", expand=True)
            self._path_labels[key] = (path_lbl, path_var)

            btn_browse = tk.Button(row, text="📂",
                                   command=lambda k=key: self._sfoglia_inline(k),
                                   relief=tk.FLAT, cursor="hand2",
                                   font=("Arial", 10), padx=4)
            btn_browse.pack(side="right", padx=4)

        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # ── Seleziona/deseleziona tutto + configura ───────────────
        ctrl_frame = tk.Frame(self.win)
        ctrl_frame.pack(fill="x", padx=14, pady=(0, 4))

        tk.Button(ctrl_frame, text="✔ Tutti",
                  command=self._seleziona_tutti,
                  relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9), padx=8).pack(side="left", padx=2)

        tk.Button(ctrl_frame, text="✕ Nessuno",
                  command=self._deseleziona_tutti,
                  relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9), padx=8).pack(side="left", padx=2)

        tk.Button(ctrl_frame, text="⚙ Configura percorsi...",
                  command=self._apri_configurazione,
                  relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9), padx=8).pack(side="left", padx=14)

        # Selettore file manuale
        tk.Button(ctrl_frame, text="📁 Altro file ADIF...",
                  command=self._sfoglia_manuale,
                  relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9), padx=8).pack(side="right", padx=2)

        ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=10, pady=6)

        # ── Pulsanti avvio ────────────────────────────────────────
        btn_frame = tk.Frame(self.win)
        btn_frame.pack(fill="x", padx=14, pady=(0, 14))

        self._lbl_selected = tk.Label(btn_frame, text="",
                                      font=("Arial", 9), anchor="w")
        self._lbl_selected.pack(side="left")

        tk.Button(btn_frame, text="Annulla",
                  command=self.win.destroy,
                  relief=tk.FLAT, cursor="hand2",
                  font=("Helvetica", 10),
                  padx=14, pady=6).pack(side="right", padx=4)

        self._btn_avvia = tk.Button(btn_frame, text="▶  Avvia Importazione",
                                    command=self._avvia,
                                    relief=tk.FLAT, cursor="hand2",
                                    font=("Helvetica", 10, "bold"),
                                    padx=18, pady=6)
        self._btn_avvia.pack(side="right", padx=4)

        # Aggiorna label contatore selezione
        for var in self._check_vars.values():
            var.trace_add("write", lambda *_: self._aggiorna_counter())
        self._aggiorna_counter()

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _trunca_path(path, max_len=55):
        if len(path) <= max_len:
            return path
        return "…" + path[-(max_len - 1):]

    def _aggiorna_counter(self):
        n = sum(1 for v in self._check_vars.values() if v.get())
        self._lbl_selected.configure(
            text=f"{n} sorgente/i selezionata/e")

    def _seleziona_tutti(self):
        for var in self._check_vars.values():
            var.set(True)

    def _deseleziona_tutti(self):
        for var in self._check_vars.values():
            var.set(False)

    def _sfoglia_inline(self, key):
        path = filedialog.askopenfilename(
            parent=self.win,
            title=f"Seleziona file ADIF",
            filetypes=[("ADIF files", "*.adi *.adif"), ("Tutti i file", "*.*")]
        )
        if path:
            lbl, var = self._path_labels[key]
            var.set(path)
            lbl.configure(text=self._trunca_path(path))
            self._paths[key] = path
            save_program_paths(self._paths)
            # Aggiorna badge
            status_lbl, _ = self._status_labels[key]
            status_lbl.configure(text="✔ Trovato")
            self._status_labels[key] = (status_lbl, True)
            self._check_vars[key].set(True)
            self._applica_tema()

    def _sfoglia_manuale(self):
        """Importa direttamente un file ADIF arbitrario senza associarlo a un programma."""
        path = filedialog.askopenfilename(
            parent=self.win,
            title="Seleziona file ADIF manuale",
            filetypes=[("ADIF files", "*.adi *.adif"), ("Tutti i file", "*.*")]
        )
        if path:
            self.win.destroy()
            self._on_import([("Manuale", path)])

    def _apri_configurazione(self):
        def on_save(new_paths):
            self._paths = new_paths
            self._aggiorna_badge_da_paths(new_paths)
            self._applica_tema()

        ProgramPathsWindow(self.win, on_save_callback=on_save)

    def _aggiorna_badge_da_paths(self, new_paths):
        for key, path in new_paths.items():
            exists = os.path.isfile(path)
            if key in self._path_labels:
                lbl, var = self._path_labels[key]
                var.set(path)
                lbl.configure(
                    text=self._trunca_path(path) if path else "— nessun percorso —")
            if key in self._status_labels:
                status_lbl, _ = self._status_labels[key]
                if exists:
                    status_lbl.configure(text="✔ Trovato")
                    self._status_labels[key] = (status_lbl, True)
                elif path:
                    status_lbl.configure(text="⚠ File assente")
                    self._status_labels[key] = (status_lbl, False)
                else:
                    status_lbl.configure(text="○ Non configurato")
                    self._status_labels[key] = (status_lbl, False)

    def _avvia(self):
        sorgenti = []
        for label, key in PROGRAMMI_SUPPORTATI.items():
            if self._check_vars[key].get():
                _, path_var = self._path_labels[key]
                path = path_var.get().strip()
                if not path:
                    messagebox.showwarning(
                        "Percorso mancante",
                        f"Il percorso per {label} non è configurato.\n"
                        f"Configuralo tramite '⚙ Configura percorsi' oppure deselezionalo.",
                        parent=self.win)
                    return
                if not os.path.isfile(path):
                    resp = messagebox.askyesno(
                        "File non trovato",
                        f"Il file per {label} non esiste:\n{path}\n\n"
                        f"Vuoi selezionarne un altro?",
                        parent=self.win)
                    if resp:
                        self._sfoglia_inline(key)
                    return
                sorgenti.append((label, path))

        if not sorgenti:
            messagebox.showwarning("Nessuna sorgente",
                                   "Seleziona almeno un programma da importare.",
                                   parent=self.win)
            return

        self.win.destroy()
        self._on_import(sorgenti)

    # ── Tema ─────────────────────────────────────────────────────
    def _etichetta_tema(self) -> str:
        return "☀  Tema chiaro" if self._tema_nome == "scuro" else "🌙  Tema scuro"

    def _toggle_tema(self):
        self._tema_nome = "chiaro" if self._tema_nome == "scuro" else "scuro"
        self._p = TEMI[self._tema_nome]
        _salva_tema_config(self._tema_nome)
        self._applica_tema()

    def _applica_tema(self):
        p = self._p
        self.win.configure(bg=p["win_bg"])
        self._btn_tema.configure(
            text=self._etichetta_tema(),
            bg=p["win_bg_alt"], fg=p["fg"],
            activebackground=p["accent"], activeforeground="#ffffff")
        self._btn_avvia.configure(
            bg=p["accent"], fg="#ffffff",
            activebackground=p["accent_hover"])
        self._lbl_selected.configure(bg=p["win_bg"], fg=p["fg_dim"])

        for key, (status_lbl, is_ok) in self._status_labels.items():
            if is_ok:
                status_lbl.configure(
                    bg=p["badge_bg"], fg=p["counter_green"])
            else:
                status_lbl.configure(
                    bg=p["win_bg"], fg=p["counter_red"])

        self._ricorsivo_applica_tema(self.win, p)

    def _ricorsivo_applica_tema(self, widget, p):
        cls = widget.__class__.__name__
        try:
            if cls == "Frame":
                widget.configure(bg=p["win_bg"])
            elif cls == "Label":
                # Non sovrascrivere i badge già colorati
                widget.configure(bg=p["win_bg"], fg=p["fg"])
            elif cls == "Checkbutton":
                widget.configure(bg=p["win_bg"], fg=p["fg"],
                                 selectcolor=p["win_bg_alt"],
                                 activebackground=p["win_bg"],
                                 activeforeground=p["accent"])
            elif cls == "Button":
                widget.configure(bg=p["btn_bg"], fg=p["btn_fg"],
                                 activebackground=p["btn_active_bg"],
                                 activeforeground=p["btn_active_fg"],
                                 bd=0)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._ricorsivo_applica_tema(child, p)


# ══════════════════════════════════════════════════════════════════════════════
# FINESTRA DI PROGRESSO (thread-safe via queue)
# ══════════════════════════════════════════════════════════════════════════════
class ProgressWindow:
    """
    Finestra di avanzamento thread-safe.
    Supporta importazione da più sorgenti con log separati per sorgente.
    """

    def __init__(self, parent):
        self._queue = queue.Queue()
        self._done  = False

        self._tema_nome = _leggi_tema_config()
        self._p         = TEMI[self._tema_nome]
        self._var_tema  = None

        self.win = tk.Toplevel(parent)
        self.win.title("Elaborazione QSL in corso...")
        self.win.geometry("560x480")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)

        self._costruisci_ui()
        self._var_tema = tk.StringVar(value=self._tema_nome)
        self._applica_tema()
        self.win.after(50, self._pump)

    def _costruisci_ui(self):
        p = self._p
        self.win.configure(bg=p["win_bg"])

        # Top bar
        top_bar = tk.Frame(self.win, bg=p["win_bg"])
        top_bar.pack(fill="x", padx=12, pady=(6, 0))

        self._btn_tema = tk.Button(
            top_bar, text=self._etichetta_tema(),
            command=self._toggle_tema,
            relief=tk.FLAT, cursor="hand2",
            font=("Arial", 8), padx=8, pady=2)
        self._btn_tema.pack(side="right")

        # Titolo
        self.lbl_title = tk.Label(
            self.win, text="Generazione QSL",
            font=("Helvetica", 13, "bold"))
        self.lbl_title.pack(pady=(4, 2))

        # Sorgente corrente
        self.source_var = tk.StringVar(value="")
        self.lbl_source = tk.Label(
            self.win, textvariable=self.source_var,
            font=("Helvetica", 9, "italic"))
        self.lbl_source.pack(pady=(0, 2))

        # Status
        self.status_var = tk.StringVar(value="Avvio in corso...")
        self.lbl_status = tk.Label(
            self.win, textvariable=self.status_var,
            font=("Helvetica", 10), wraplength=520)
        self.lbl_status.pack(padx=12, pady=2)

        # Barra progresso sorgente corrente
        self._style = ttk.Style(self.win)
        self._style.theme_use(p["ttk_theme"])
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.win, variable=self.progress_var,
            maximum=100, length=520, mode="determinate",
            style="QSL.Horizontal.TProgressbar")
        self.progress_bar.pack(padx=12, pady=4)

        self.pct_var = tk.StringVar(value="0%")
        self.lbl_pct = tk.Label(
            self.win, textvariable=self.pct_var,
            font=("Helvetica", 10, "bold"))
        self.lbl_pct.pack()

        # Barra progresso globale (multi-sorgente)
        tk.Label(self.win, text="Progresso globale:",
                 font=("Arial", 8)).pack(pady=(6, 0))
        self.global_progress_var = tk.DoubleVar(value=0)
        self.global_progress_bar = ttk.Progressbar(
            self.win, variable=self.global_progress_var,
            maximum=100, length=520, mode="determinate",
            style="QSL.Horizontal.TProgressbar")
        self.global_progress_bar.pack(padx=12, pady=2)
        self.global_pct_var = tk.StringVar(value="")
        tk.Label(self.win, textvariable=self.global_pct_var,
                 font=("Arial", 8)).pack()

        # Contatori
        self.cnt_frame = tk.Frame(self.win, bd=1, relief="groove")
        self.cnt_frame.pack(fill="x", padx=12, pady=6)

        self.total_var    = tk.StringVar(value="0")
        self.enriched_var = tk.StringVar(value="0")
        self.notfound_var = tk.StringVar(value="0")

        self._counter_labels = []
        for col, label, var in [
            (0, "QSL generate",        self.total_var),
            (1, "Arricchite HamQTH",   self.enriched_var),
            (2, "Callsign non trovati", self.notfound_var),
        ]:
            f = tk.Frame(self.cnt_frame)
            f.grid(row=0, column=col, padx=18, pady=6, sticky="nsew")
            big   = tk.Label(f, textvariable=var, font=("Helvetica", 20, "bold"))
            big.pack()
            small = tk.Label(f, text=label, font=("Helvetica", 8))
            small.pack()
            self._counter_labels.append((big, small, col))
        self.cnt_frame.columnconfigure((0, 1, 2), weight=1)

        # Log
        log_frame = tk.Frame(self.win)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.scrollbar = tk.Scrollbar(log_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            log_frame, height=5, font=("Courier", 8),
            state="disabled", yscrollcommand=self.scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.log_text.yview)

    # ── API pubblica ──────────────────────────────────────────────
    def set_source(self, name):
        self._queue.put(("source", name))

    def set_status(self, text):
        self._queue.put(("status", text))

    def set_progress(self, value, total):
        self._queue.put(("progress", value, total))

    def set_global_progress(self, done, total):
        self._queue.put(("global_progress", done, total))

    def set_counters(self, total=None, enriched=None, not_found=None):
        self._queue.put(("counters", total, enriched, not_found))

    def log(self, message):
        self._queue.put(("log", message))

    def close(self):
        self._queue.put(("close",))

    # ── Pump ─────────────────────────────────────────────────────
    def _pump(self):
        try:
            while True:
                cmd = self._queue.get_nowait()
                self._dispatch(cmd)
        except queue.Empty:
            pass
        if not self._done:
            self.win.after(50, self._pump)

    def _dispatch(self, cmd):
        action = cmd[0]
        if action == "source":
            self.source_var.set(f"Sorgente: {cmd[1]}")
        elif action == "status":
            self.status_var.set(cmd[1])
        elif action == "progress":
            value, total = cmd[1], cmd[2]
            pct = (value / total * 100) if total > 0 else 0
            self.progress_var.set(pct)
            self.pct_var.set(f"{int(pct)}%  ({value}/{total})")
        elif action == "global_progress":
            done, total = cmd[1], cmd[2]
            pct = (done / total * 100) if total > 0 else 0
            self.global_progress_var.set(pct)
            self.global_pct_var.set(f"File {done} di {total}")
        elif action == "counters":
            _, total, enriched, not_found = cmd
            if total     is not None: self.total_var.set(str(total))
            if enriched  is not None: self.enriched_var.set(str(enriched))
            if not_found is not None: self.notfound_var.set(str(not_found))
        elif action == "log":
            self.log_text.config(state="normal")
            self.log_text.insert("end", cmd[1] + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        elif action == "close":
            self._done = True
            self.win.grab_release()
            self.win.destroy()

    # ── Tema ─────────────────────────────────────────────────────
    def _etichetta_tema(self) -> str:
        return "☀  Tema chiaro" if self._tema_nome == "scuro" else "🌙  Tema scuro"

    def _toggle_tema(self):
        self._tema_nome = "chiaro" if self._tema_nome == "scuro" else "scuro"
        self._p = TEMI[self._tema_nome]
        _salva_tema_config(self._tema_nome)
        if self._var_tema:
            self._var_tema.set(self._tema_nome)
        self._applica_tema()

    def _applica_tema(self):
        p = self._p
        self._style.configure(
            "QSL.Horizontal.TProgressbar",
            troughcolor=p["progress_trough"],
            background=p["accent"],
            darkcolor=p["accent"],
            lightcolor=p["accent"],
            bordercolor=p["win_bg"])
        self.win.configure(bg=p["win_bg"])
        for w in self.win.winfo_children():
            if isinstance(w, tk.Frame) and w is not self.cnt_frame:
                w.configure(bg=p["win_bg"])
        self._btn_tema.configure(
            text=self._etichetta_tema(),
            bg=p["win_bg_alt"], fg=p["fg"],
            activebackground=p["accent"], activeforeground="#ffffff")
        self.lbl_title.configure(bg=p["win_bg"],  fg=p["title_fg"])
        self.lbl_source.configure(bg=p["win_bg"], fg=p["fg_dim"])
        self.lbl_status.configure(bg=p["win_bg"], fg=p["status_fg"])
        self.lbl_pct.configure(bg=p["win_bg"],    fg=p["pct_fg"])
        for lbl in self.win.winfo_children():
            if isinstance(lbl, tk.Label) and lbl not in (
                    self.lbl_title, self.lbl_source, self.lbl_status, self.lbl_pct):
                try:
                    lbl.configure(bg=p["win_bg"], fg=p["fg_dim"])
                except Exception:
                    pass
        self.cnt_frame.configure(bg=p["counter_frame_bg"])
        colori = [p["counter_green"], p["counter_blue"], p["counter_red"]]
        for big, small, col in self._counter_labels:
            big.master.configure(bg=p["counter_frame_bg"])
            big.configure(bg=p["counter_frame_bg"], fg=colori[col])
            small.configure(bg=p["counter_frame_bg"], fg=p["counter_label_fg"])
        log_frame = self.log_text.master
        log_frame.configure(bg=p["win_bg"])
        self.log_text.configure(bg=p["log_bg"], fg=p["log_fg"])
        self.scrollbar.configure(bg=p["scrollbar_bg"], troughcolor=p["win_bg_alt"])


# ══════════════════════════════════════════════════════════════════════════════
# CARICAMENTO CONFIGURAZIONE HAMQTH
# ══════════════════════════════════════════════════════════════════════════════
def load_hamqth_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        return None
    config.read(CONFIG_FILE)
    if "HAMQTH" in config:
        try:
            return {
                "user":     config["HAMQTH"]["User"],
                "password": config["HAMQTH"]["Password"],
            }
        except KeyError:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CLIENT API HAMQTH
# ══════════════════════════════════════════════════════════════════════════════
class HamQTHClient:
    BASE_URL = "https://www.hamqth.com/xml.php"
    APP_NAME = "QSLManager_IZ8GCH"

    def __init__(self, username, password):
        self.username     = username
        self.password     = password
        self.session_id   = None
        self.session_time = 0

    def _fetch_xml(self, url):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
            return ET.fromstring(data)
        except Exception as e:
            raise ConnectionError(f"Errore di rete HamQTH: {e}")

    def login(self):
        url  = (f"{self.BASE_URL}?u={urllib.parse.quote(self.username)}"
                f"&p={urllib.parse.quote(self.password)}")
        root = self._fetch_xml(url)
        ns   = {"h": "https://www.hamqth.com"}
        error = root.find(".//h:e", ns)
        if error is not None:
            raise ValueError(f"Login HamQTH fallito: {error.text}")
        session_id = root.find(".//h:session_id", ns)
        if session_id is None:
            raise ValueError("Session ID non ricevuto da HamQTH.")
        self.session_id   = session_id.text
        self.session_time = time.time()

    def _ensure_session(self):
        if self.session_id is None or (time.time() - self.session_time) > 3300:
            self.login()

    def search_callsign(self, callsign):
        self._ensure_session()
        url  = (f"{self.BASE_URL}?id={self.session_id}"
                f"&callsign={urllib.parse.quote(callsign.upper())}"
                f"&prg={self.APP_NAME}")
        root = self._fetch_xml(url)
        ns   = {"h": "https://www.hamqth.com"}
        error = root.find(".//h:e", ns)
        if error is not None:
            msg = (error.text or "").lower()
            if "expired" in msg or "does not exist" in msg:
                self.login()
                return self.search_callsign(callsign)
            elif "not found" in msg:
                return None
            else:
                raise ValueError(f"Errore HamQTH: {error.text}")
        search = root.find(".//h:search", ns)
        if search is None:
            return None
        fields_list = ["callsign", "nick", "qth", "country", "adif", "itu", "cq",
                       "grid", "adr_name", "adr_city", "adr_country",
                       "email", "lotw", "eqsl", "qsl", "qsldirect",
                       "latitude", "longitude", "continent", "utc_offset",
                       "iota", "qsl_via"]
        result = {}
        for field in fields_list:
            el = search.find(f"h:{field}", ns)
            if el is not None and el.text:
                result[field] = el.text.strip()
        return result


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    """Inizializza il database QSL Records con struttura completa"""
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    
    # Crea tabella base se non esiste
    c.execute('''
        CREATE TABLE IF NOT EXISTS qsl_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            call        TEXT,
            qso_date    TEXT,
            time_on     TEXT,
            mode        TEXT,
            band        TEXT,
            rst_sent    TEXT,
            email       TEXT,
            qsl_file    TEXT,
            sent        INTEGER DEFAULT 0,
            name        TEXT,
            qth         TEXT,
            grid        TEXT,
            source      TEXT
        )
    ''')
    
    # Verifica colonne esistenti
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(qsl_records)")]
    
    # Colonne base per compatibilità
    base_columns = [
        ("name",   "TEXT"),
        ("qth",    "TEXT"),
        ("grid",   "TEXT"),
        ("source", "TEXT"),
    ]
    
    # Colonne QSL moderne
    qsl_columns = [
        ("callsign", "TEXT"),
        ("qsl_date", "TEXT"),
        ("qsl_time", "TEXT"),
        ("operator_name", "TEXT"),
        ("qth", "TEXT"),
        ("grid_locator", "TEXT"),
        ("band", "TEXT"),
        ("mode", "TEXT"),
        ("comments", "TEXT"),
        ("qsl_status", "TEXT DEFAULT 'pending'"),
        ("stato", "TEXT DEFAULT 'non_inviata'"),
        ("data_invio", "TEXT"),
        ("rst_sent", "TEXT"),
        ("rst_received", "TEXT"),
        ("power", "REAL"),
        ("frequency_num", "REAL"),
        ("qsl_file", "TEXT"),
        ("sent", "TEXT"),
    ]
    
    # Colonne HamQTH
    hamqth_columns = [
        ("nick", "TEXT"),
        ("country", "TEXT"),
        ("adif", "TEXT"),
        ("itu", "TEXT"),
        ("cq", "TEXT"),
        ("adr_name", "TEXT"),
        ("adr_street1", "TEXT"),
        ("adr_city", "TEXT"),
        ("adr_zip", "TEXT"),
        ("adr_country", "TEXT"),
        ("email", "TEXT"),
        ("lotw", "TEXT"),
        ("eqsl", "TEXT"),
        ("qsldirect", "TEXT"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("continent", "TEXT"),
        ("utc_offset", "TEXT"),
        ("picture", "TEXT"),
        ("iota", "TEXT"),
        ("qsl_via", "TEXT"),
    ]
    
    # Colonne data/ora alternative
    datetime_columns = [
        ("datetime", "TEXT"),
        ("timestamp", "TEXT"),
        ("created", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("modified", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("date", "TEXT"),
        ("time", "TEXT"),
        ("contact_date", "TEXT"),
        ("contact_time", "TEXT"),
        ("qso_date", "TEXT"),
        ("qso_time", "TEXT"),
        ("hour", "TEXT"),
    ]
    
    # Colonne callsign alternativi
    callsign_columns = [
        ("call", "TEXT"),
        ("station", "TEXT"),
        ("station_call", "TEXT"),
        ("callsign_", "TEXT"),
    ]
    
    # Colonne operatore alternativi
    operator_columns = [
        ("name", "TEXT"),
        ("operator", "TEXT"),
        ("first_name", "TEXT"),
        ("op_name", "TEXT"),
    ]
    
    # Colonne posizione alternative
    location_columns = [
        ("location", "TEXT"),
        ("city", "TEXT"),
        ("address", "TEXT"),
        ("grid", "TEXT"),
        ("locator", "TEXT"),
        ("gridsquare", "TEXT"),
        ("maidenhead", "TEXT"),
    ]
    
    # Colonne banda/frequenza alternative
    band_columns = [
        ("frequency", "TEXT"),
        ("freq", "TEXT"),
        ("mhz", "TEXT"),
        ("khz", "TEXT"),
    ]
    
    # Colonne modalità alternative
    mode_columns = [
        ("modulation", "TEXT"),
        ("mod", "TEXT"),
    ]
    
    # Colonne commenti alternativi
    comment_columns = [
        ("comment", "TEXT"),
        ("notes", "TEXT"),
        ("remark", "TEXT"),
        ("description", "TEXT"),
        ("text", "TEXT"),
    ]
    
    # Colonne stato alternative
    status_columns = [
        ("status", "TEXT"),
        ("state", "TEXT"),
        ("received", "TEXT"),
        ("confirmed", "TEXT"),
    ]
    
    # Altri campi utili
    other_columns = [
        ("phone", "TEXT"),
        ("dxcc", "TEXT"),
        ("cq_zone", "TEXT"),
        ("itu_zone", "TEXT"),
        ("county", "TEXT"),
        ("province", "TEXT"),
        ("postal_code", "TEXT"),
        ("web", "TEXT"),
        ("url", "TEXT"),
    ]
    
    # Unisci tutte le colonne
    all_columns = (base_columns + qsl_columns + hamqth_columns + datetime_columns + 
                  callsign_columns + operator_columns + location_columns + 
                  band_columns + mode_columns + comment_columns + status_columns + 
                  other_columns)
    
    # Aggiungi colonne mancanti
    added_columns = []
    for col, col_type in all_columns:
        if col not in existing_cols:
            try:
                c.execute(f"ALTER TABLE qsl_records ADD COLUMN {col} {col_type}")
                added_columns.append(f"{col} ({col_type})")
                print(f"[DEBUG] Creatore: Aggiunta colonna {col} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"[DEBUG] Creatore: Colonna {col} già esistente")
                else:
                    print(f"[DEBUG] Creatore: Errore aggiunta colonna {col}: {e}")
    
    # Crea indici per performance
    if added_columns:
        print("[DEBUG] Creatore: Creazione indici...")
        try:
            # Indici principali
            if "callsign" not in existing_cols or any("callsign" in col for col in added_columns):
                c.execute("CREATE INDEX IF NOT EXISTS idx_callsign ON qsl_records(callsign)")
            if "qsl_date" not in existing_cols or any("qsl_date" in col for col in added_columns):
                c.execute("CREATE INDEX IF NOT EXISTS idx_qsl_date ON qsl_records(qsl_date)")
            if "stato" not in existing_cols or any("stato" in col for col in added_columns):
                c.execute("CREATE INDEX IF NOT EXISTS idx_stato ON qsl_records(stato)")
            if "data_invio" not in existing_cols or any("data_invio" in col for col in added_columns):
                c.execute("CREATE INDEX IF NOT EXISTS idx_data_invio ON qsl_records(data_invio)")
            
            # Indici compositi
            c.execute("CREATE INDEX IF NOT EXISTS idx_callsign_date ON qsl_records(callsign, qsl_date)")
            
            print("[DEBUG] Creatore: Indici creati con successo")
        except Exception as e:
            print(f"[DEBUG] Creatore: Errore creazione indici: {e}")
    
    conn.commit()
    conn.close()
    
    # Mostra notifica se ci sono state modifiche
    if added_columns:
        print(f"[DEBUG] Creatore: Database aggiornato con {len(added_columns)} nuove colonne")
        print(f"[DEBUG] Creatore: Colonne aggiunte: {', '.join(added_columns)}")

def ensure_adif_mappings_table():
    """Ensure adif_mappings table exists"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='adif_mappings'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            cursor.execute('''
                CREATE TABLE adif_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    mapping_date TEXT NOT NULL,
                    db_field TEXT NOT NULL,
                    adif_field TEXT NOT NULL,
                    UNIQUE(file_name, db_field)
                )
            ''')
            conn.commit()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error ensuring adif_mappings table: {e}")
        return False

def load_adif_mappings():
    """Carica le mappature dei campi ADIF dal database"""
    try:
        # Ensure table exists
        if not ensure_adif_mappings_table():
            print("Failed to create adif_mappings table")
            return {}
        
        # Try to get active mapping from database
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        if config.has_section('ADIF_SETTINGS') and config.has_option('ADIF_SETTINGS', 'active_mapping_file'):
            active_file = config.get('ADIF_SETTINGS', 'active_mapping_file')
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT db_field, adif_field 
                FROM adif_mappings 
                WHERE file_name = ?
            ''', (active_file,))
            
            mappings = cursor.fetchall()
            conn.close()
            
            return dict(mappings)
        else:
            # Fallback to config.ini
            config = configparser.ConfigParser()
            config.read('config.ini')
            mappings = {}
            if config.has_section('ADIF_MAPPINGS'):
                for option in config.options('ADIF_MAPPINGS'):
                    value = config.get('ADIF_MAPPINGS', option)
                    mappings[option] = value
            return mappings
            
    except Exception as e:
        print(f"Errore caricamento mappature ADIF: {e}")
        return {}

def insert_record(fields, qsl_file=None, hamqth_data=None, source=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Load custom mappings
    adif_mappings = load_adif_mappings()
    
    # Get CALL from ADIF (map to callsign in new db)
    call_field = adif_mappings.get('callsign', 'CALL')
    call = fields.get(call_field, "").upper().strip()
    if not call:
        print(f"[DEBUG] ERRORE: {call_field} mancante nei campi ADIF: {fields.keys()}")
        conn.close()
        return False
    
    # Map ADIF fields using custom mappings
    def get_field(db_field, default_adif):
        adif_field = adif_mappings.get(db_field, default_adif)
        return fields.get(adif_field, "")
    
    qso_date = get_field('qsl_date', 'QSO_DATE')
    time_on = get_field('time_on', 'TIME_ON')
    mode = get_field('mode', 'MODE')
    band = get_field('band', 'BAND')
    rst_sent = get_field('rst_sent', 'RST_SENT')
    email_adif = adif_mappings.get('email', 'EMAIL')
    
    # Get data from HamQTH if available
    email = fields.get(email_adif) or (hamqth_data.get("email") if hamqth_data else None)
    name = hamqth_data.get("nick") if hamqth_data else None
    qth = hamqth_data.get("qth") if hamqth_data else None
    grid = hamqth_data.get("grid") if hamqth_data else None
    
    # Build dynamic query with available columns
    columns = ['callsign', 'call', 'qsl_date', 'qso_date', 'qsl_time', 'time_on', 
               'operator_name', 'name', 'qth', 'grid_locator', 'grid', 'band', 'mode', 
               'comments', 'rst_sent', 'email', 'qsl_file', 'stato', 'qsl_status', 'source']
    
    values = [
        call,                    # callsign (NOT NULL)
        call,                    # call (legacy)
        qso_date,                # qsl_date
        qso_date,                # qso_date (legacy)
        time_on,                 # qsl_time
        time_on,                 # time_on (legacy)
        name or "",              # operator_name
        name or "",              # name (legacy)
        qth or "",               # qth
        grid or "",              # grid_locator
        grid or "",              # grid (legacy)
        band or "",              # band
        mode or "",              # mode
        "",                      # comments
        rst_sent or "",          # rst_sent
        email or "",             # email
        qsl_file or "",          # qsl_file
        'non_inviata',           # stato
        'pending',               # qsl_status
        source or ""             # source
    ]
    
    placeholders = ', '.join(['?' for _ in columns])
    query = f"INSERT INTO qsl_records ({', '.join(columns)}) VALUES ({placeholders})"
    
    try:
        c.execute(query, values)
        conn.commit()
        print(f"[DEBUG] Record inserito: {call}")
        conn.close()
        return True
    except sqlite3.IntegrityError as e:
        print(f"[DEBUG] ERRORE INSERT: {call} - {e}")
        conn.close()
        return False
    except Exception as e:
        print(f"[DEBUG] ERRORE GENERICO: {call} - {e}")
        conn.close()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# FONT
# ══════════════════════════════════════════════════════════════════════════════
def find_system_font():
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

FONT_PATH = find_system_font()

def load_font(size):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════════════════
# ADIF PARSER
# ══════════════════════════════════════════════════════════════════════════════
def parse_adif_record(record):
    fields  = {}
    matches = re.findall(r'<(\w+):(\d+)[^>]*>([^<]*)', record, re.IGNORECASE)
    for field, length, value in matches:
        fields[field.upper()] = value.strip()
    return fields

def format_date(date):
    if len(date) == 8:
        return f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    return date

def format_time(t):
    if len(t) >= 4:
        return f"{t[0:2]}:{t[2:4]}"
    return t


# ══════════════════════════════════════════════════════════════════════════════
# UTIL GRAFICHE
# ══════════════════════════════════════════════════════════════════════════════
def percent_to_pixels(box, w, h):
    return (int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h))

def draw_text_centered(draw, text, box, font):
    bbox   = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = box[0] + (box[2] - box[0] - text_w) // 2
    y = box[1] + (box[3] - box[1] - text_h) // 2
    draw.text((x, y), text, fill="black", font=font)

def generate_qr(data, img_width):
    qr = qrcode.QRCode(box_size=3, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    size   = int(img_width * QR_SIZE_PERCENT)
    return img_qr.resize((size, size))


# ══════════════════════════════════════════════════════════════════════════════
# GENERAZIONE QSL
# ══════════════════════════════════════════════════════════════════════════════
def generate_qsl(fields, index, name=None):
    if not os.path.exists(TEMPLATE_IMAGE):
        return None

    img   = Image.open(TEMPLATE_IMAGE).convert("RGB")
    # Forza dimensione massima 900x600
    img = img.resize((900, 600), Image.LANCZOS)
    draw  = ImageDraw.Draw(img)
    width, height = img.size

    call     = fields.get("CALL", "")
    date     = format_date(fields.get("QSO_DATE", ""))
    time_val = format_time(fields.get("TIME_ON", ""))
    mode     = fields.get("MODE", "")
    band     = fields.get("BAND", "")
    rst      = fields.get("RST_SENT", "")

    data_map = {
        "CALL": call,
        "NAME": name or "",
        "DATE": date,
        "TIME": time_val,
        "MODE": mode,
        "BAND": band,
        "RST":  rst,
    }

    for key, value in data_map.items():
        if key in TEXT_AREAS_PERCENT and value:
            pixel_box = percent_to_pixels(TEXT_AREAS_PERCENT[key], width, height)
            font      = load_font(CALL_FONT_SIZE if key == "CALL" else BASE_FONT_SIZE)
            draw_text_centered(draw, value, pixel_box, font)

    qr_img = generate_qr(QR_URL, width)
    qr_x   = int(QR_POSITION_PERCENT[0] * width)
    qr_y   = int(QR_POSITION_PERCENT[1] * height)
    img.paste(qr_img, (qr_x, qr_y))

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    safe_call = re.sub(r'[\\/:*?"<>|]', '_', call)
    filename  = f"{safe_call}_{date}_{index}.jpg"
    file_path = os.path.join(OUTPUT_DIR, filename)
    img.save(file_path, dpi=(300, 300), format="JPEG", quality=95)
    return file_path


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS SINGOLO FILE ADIF
# ══════════════════════════════════════════════════════════════════════════════
def process_single_adif(filepath, source_label, pw, hamqth,
                         hamqth_cache, global_counter):
    """
    Processa un singolo file ADIF.
    Restituisce (counter, enriched, not_found_list).
    global_counter è un dict condiviso {"total":0,"enriched":0,"not_found":0}
    per aggiornare i contatori UI cumulativi.
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    all_records   = re.split(r'<EOR>', content, flags=re.IGNORECASE)
    valid_records = [r for r in all_records if "<CALL:" in r.upper()]
    total         = len(valid_records)

    pw.log(f"{'─'*48}")
    pw.log(f"📂 [{source_label}] {os.path.basename(filepath)}")
    pw.log(f"📋 Record trovati: {total}")
    pw.set_progress(0, total)

    counter   = 0
    enriched  = 0
    not_found = []

    for i, record in enumerate(valid_records):
        fields = parse_adif_record(record)
        call   = fields.get("CALL", "").upper().strip()
        
        # Skip records without CALL
        if not call:
            pw.log(f"   ⚠️  Record {i+1} saltato: CALL mancante")
            continue

        pw.set_status(f"[{source_label}] {i+1}/{total} — {call}")
        pw.set_progress(i + 1, total)

        hamqth_data = None
        if hamqth and call:
            if call in hamqth_cache:
                hamqth_data = hamqth_cache[call]
                if hamqth_data:
                    enriched += 1
            else:
                try:
                    pw.log(f"🌐 HamQTH: {call}...")
                    hamqth_data = hamqth.search_callsign(call)
                    hamqth_cache[call] = hamqth_data
                    if hamqth_data:
                        enriched += 1
                        pw.log(f"   ✅ {call} → nick: {hamqth_data.get('nick','n/d')} | "
                               f"qth: {hamqth_data.get('qth','n/d')}")
                    else:
                        not_found.append(call)
                        pw.log(f"   ❓ {call} non trovato.")
                except Exception as e:
                    hamqth_cache[call] = None
                    not_found.append(call)
                    pw.log(f"   ⚠️  {call}: {e}")

        name = hamqth_data.get("nick") if hamqth_data else None

        email = fields.get("EMAIL")
        if not email and hamqth_data:
            email = hamqth_data.get("email")

        if email:
            qsl_path = generate_qsl(fields, i + 1, name=name)
            pw.log(f"   🖼️  {os.path.basename(qsl_path) if qsl_path else 'ERRORE'}")
            counter += 1
        else:
            qsl_path = None
            pw.log("   🚫 Nessuna email — QSL non generata.")

        # Insert record and check result
        inserted = insert_record(fields, qsl_file=qsl_path,
                      hamqth_data=hamqth_data, source=source_label)
        if not inserted:
            pw.log(f"   ❌ Errore inserimento record: {call}")

        # Aggiorna contatori cumulativi UI
        global_counter["total"]     += (1 if email else 0)
        global_counter["enriched"]  += (1 if hamqth_data else 0)
        global_counter["not_found"] += (1 if (call and not hamqth_data and hamqth) else 0)
        pw.set_counters(
            total=global_counter["total"],
            enriched=global_counter["enriched"],
            not_found=global_counter["not_found"])

    return counter, enriched, not_found


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS ADIF MULTI-SORGENTE — gira nel worker thread
# ══════════════════════════════════════════════════════════════════════════════
def process_adif_sources(sorgenti, pw):
    """
    sorgenti = lista di (label, filepath)
    pw       = ProgressWindow — thread-safe via queue
    """
    init_db()

    # Login HamQTH (condiviso tra tutte le sorgenti)
    hamqth_conf = load_hamqth_config()
    hamqth      = None
    if hamqth_conf:
        pw.set_status("Connessione a HamQTH...")
        pw.log("🔐 Login HamQTH in corso...")
        try:
            hamqth = HamQTHClient(hamqth_conf["user"], hamqth_conf["password"])
            hamqth.login()
            pw.log("✅ HamQTH: login effettuato.")
        except Exception as e:
            pw.log(f"⚠️  HamQTH non disponibile: {e}")
            hamqth = None
    else:
        pw.log("ℹ️  HamQTH non configurato — solo dati ADIF.")

    hamqth_cache   = {}
    global_counter = {"total": 0, "enriched": 0, "not_found": 0}
    n_sources      = len(sorgenti)
    summaries      = []

    for src_idx, (label, filepath) in enumerate(sorgenti):
        pw.set_source(label)
        pw.set_global_progress(src_idx, n_sources)
        pw.log(f"\n{'═'*48}")
        pw.log(f"🔄 Sorgente {src_idx+1}/{n_sources}: {label}")

        try:
            counter, enriched, not_found = process_single_adif(
                filepath, label, pw, hamqth, hamqth_cache, global_counter)
            summaries.append({
                "label":     label,
                "counter":   counter,
                "enriched":  enriched,
                "not_found": not_found,
                "error":     None,
            })
            pw.log(f"✅ [{label}] completato: {counter} QSL | "
                   f"{enriched} arricchite | {len(not_found)} non trovate")
        except Exception as e:
            pw.log(f"❌ [{label}] ERRORE: {e}")
            summaries.append({
                "label":   label,
                "error":   str(e),
                "counter": 0, "enriched": 0, "not_found": [],
            })

    pw.set_global_progress(n_sources, n_sources)
    pw.set_progress(100, 100)
    pw.set_status("✅ Elaborazione completata!")
    pw.log(f"\n{'═'*48}")
    pw.log("RIEPILOGO FINALE")

    # Costruisci riepilogo testuale
    lines = ["Import completato!\n"]
    for s in summaries:
        if s["error"]:
            lines.append(f"❌ {s['label']}: ERRORE — {s['error']}")
        else:
            lines.append(
                f"✅ {s['label']}: {s['counter']} QSL | "
                f"{s['enriched']} arricchite | "
                f"{len(s['not_found'])} non trovate")
            if s["not_found"]:
                lines.append(f"   Non trovati: {', '.join(s['not_found'])}")
        pw.log(lines[-1])

    lines.append(f"\n🔢 Totale globale: {global_counter['total']} QSL generate")

    pw.close()
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# GUI / MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    try:
        # Initialize adif_mappings table if needed
        ensure_adif_mappings_table()
        
        root = Tk()
        root.withdraw()

        def avvia_importazione(sorgenti):
            """Callback richiamato da SourceSelectionWindow con la lista sorgenti."""
            pw            = ProgressWindow(root)
            result_holder = {}

            def run():
                try:
                    summary = process_adif_sources(sorgenti, pw)
                    result_holder["summary"] = summary
                    result_holder["error"]   = None
                except Exception as e:
                    result_holder["summary"] = None
                    result_holder["error"]   = str(e)
                    pw.log(f"❌ Errore critico: {e}")
                    pw.close()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

            while thread.is_alive():
                root.update()
                time.sleep(0.05)

            root.update()

            if result_holder.get("error"):
                messagebox.showerror("Errore", result_holder["error"])
            elif result_holder.get("summary"):
                messagebox.showinfo("Completato", result_holder["summary"])

            root.destroy()

        def apri_mapper():
            """Apre il tool di mappatura campi ADIF"""
            try:
                import adif_mapping_manager
                mapper_root = tk.Toplevel(root)
                mapper_root.title("ADIF Mapping Manager")
                adif_mapping_manager.ADIFMappingManager(mapper_root)
            except ImportError:
                messagebox.showerror("Errore", "Modulo adif_mapping_manager.py non trovato")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aprire il mapping manager: {e}")

        # Pulsanti principali
        button_frame = ttk.Frame(root)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="📂 Importa ADIF", command=lambda: SourceSelectionWindow(root, on_import_callback=avvia_importazione)).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="🗺️ Mappa Campi ADIF", command=apri_mapper).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="❌ Esci", command=root.destroy).pack(side=tk.LEFT, padx=10)
        
        # Show the window
        root.deiconify()
        root.lift()
        root.focus_force()
        root.mainloop()
        
    except Exception as e:
        messagebox.showerror("Errore Critico", f"Impossibile avviare il programma: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
