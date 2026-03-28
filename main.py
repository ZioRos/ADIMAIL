"""
ADIMAIL — Launcher principale  IZ8GCH
=====================================
Interfaccia raffinata con:
  - Immagine di sfondo adattiva (ridimensionamento automatico)
  - Menu a tendina al posto dei bottoni
  - Pannello info con licenza GPL e autore
  - Overlay semitrasparente per leggibilità
  - Design curato con tipografia e colori coerenti
"""

import os
import sys
import subprocess
import configparser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageFilter, ImageDraw

# ══════════════════════════════════════════════════════════════════════════════
# CARICAMENTO CONFIGURAZIONE
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")

def carica_percorsi_moduli():
    """Carica i percorsi dei moduli dal file config.ini"""
    config = configparser.ConfigParser()
    percorsi = {}
    
    # Valori di default
    default_modules = {
        "creatore": "creatore_tema.py",
        "records": "qsl_records_tema.py",
        "editor": "qsl_editor2_tema.py",
        "config": "config_editor.py"
    }
    
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "MODULES" in config:
            for chiave in default_modules:
                percorsi[chiave] = config["MODULES"].get(chiave, default_modules[chiave])
        else:
            percorsi = default_modules.copy()
    else:
        percorsi = default_modules.copy()
    
    # Converte i percorsi relativi in assoluti
    for chiave, filename in percorsi.items():
        percorsi[chiave] = os.path.join(BASE_DIR, filename)
    
    return percorsi

# Carica i percorsi all'avvio
MODULI_PATHS = carica_percorsi_moduli()
SCRIPT_CREATORE  = MODULI_PATHS["creatore"]
SCRIPT_RECORDS   = MODULI_PATHS["records"]
SCRIPT_EDITOR    = MODULI_PATHS["editor"]
SCRIPT_CONFIG    = MODULI_PATHS["config"]

# Immagine di sfondo predefinita (opzionale — lasciare "" per sfondo gradiente)
BG_IMAGE_DEFAULT = os.path.join(BASE_DIR, "bg.png")

# ══════════════════════════════════════════════════════════════════════════════
# TESTO GPL
# ══════════════════════════════════════════════════════════════════════════════
GPL_TEXT = """ADIMAIL — Amateur Digital Image Mail
Copyright (C) 2024  IZ8GCH

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

──────────────────────────────────────────
  Autore  :  IZ8GCH
  Versione:  4.1
  Licenza :  GNU GPL v3
  Contatti:  https://iz8gch.jimdofree.com/
──────────────────────────────────────────
"""

ABOUT_TEXT = """ADIMAIL  v4.1
Amateur Digital Image Mail

Sistema integrato per la gestione delle
QSL card digitali via email.

Moduli inclusi:
  • Importazione ADIF e generazione PNG
  • Gestione record e invio email
  • Editor visuale modelli QSL
  • Configurazione (config.ini)

Analista progettuale: IZ8GCH
Sviluppatori: IZ8GCH & ClaudIA
con Python · Tkinter · Pillow

https://iz8gch.jimdofree.com/
"""


# ══════════════════════════════════════════════════════════════════════════════
# FINESTRA INFO / LICENZA
# ══════════════════════════════════════════════════════════════════════════════
class DialogoInfo(tk.Toplevel):
    """Finestra modale con informazioni sul programma e testo GPL."""

    BG   = "#0d1f2d"
    FG   = "#c8d8e8"
    ACC  = "#4a9eca"
    FONT_TITLE  = ("Georgia", 15, "bold")
    FONT_BODY   = ("Courier", 9)
    FONT_LABEL  = ("Georgia", 10)

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Informazioni — ADIMAIL IZ8GCH")
        self.geometry("620x520")
        self.minsize(500, 420)
        self.resizable(True, True)
        self.configure(bg=self.BG)
        self.transient(parent)
        self.grab_set()

        self._costruisci()

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window(self)

    def _costruisci(self):
        # Intestazione
        hdr = tk.Frame(self, bg=self.ACC, height=4)
        hdr.pack(fill=tk.X)

        tk.Label(self, text="ADIMAIL", bg=self.BG, fg=self.ACC,
                 font=("Georgia", 22, "bold")).pack(pady=(18, 2))
        tk.Label(self, text="Amateur Digital Image Mail  —  IZ8GCH",
                 bg=self.BG, fg=self.FG,
                 font=self.FONT_LABEL).pack(pady=(0, 14))

        # Notebook: About | Licenza
        style = ttk.Style()
        style.configure("Dark.TNotebook",          background=self.BG)
        style.configure("Dark.TNotebook.Tab",      background="#1a3a5c",
                        foreground=self.FG,         padding=[12, 4])
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", self.ACC)],
                  foreground=[("selected", "#ffffff")])

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # — Tab About —
        tab_about = tk.Frame(nb, bg="#0d1f2d")
        nb.add(tab_about, text="  ℹ  About  ")
        tk.Label(tab_about, text=ABOUT_TEXT, bg=self.BG, fg=self.FG,
                 font=self.FONT_LABEL, justify=tk.LEFT,
                 anchor=tk.NW).pack(fill=tk.BOTH, expand=True,
                                    padx=20, pady=16)

        # — Tab Licenza —
        tab_lic = tk.Frame(nb, bg="#0d1f2d")
        nb.add(tab_lic, text="  📜  Licenza GPL v3  ")

        frm = tk.Frame(tab_lic, bg=self.BG)
        frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        txt = tk.Text(frm, bg="#0a1520", fg=self.FG, font=self.FONT_BODY,
                      relief=tk.FLAT, wrap=tk.WORD,
                      insertbackground=self.FG, padx=10, pady=8)
        sb  = tk.Scrollbar(frm, command=txt.yview, bg=self.BG,
                           troughcolor="#1a3a5c", activebackground=self.ACC)
        txt.configure(yscrollcommand=sb.set)
        txt.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0,  column=1, sticky="ns")
        txt.insert("1.0", GPL_TEXT)
        txt.configure(state="disabled")

        # Pulsante chiudi
        tk.Button(self, text="  Chiudi  ",
                  bg=self.ACC, fg="#ffffff",
                  activebackground="#2e6da4", activeforeground="#ffffff",
                  relief=tk.FLAT, font=("Georgia", 10),
                  cursor="hand2", padx=14, pady=4,
                  command=self.destroy).pack(pady=(0, 16))


# ══════════════════════════════════════════════════════════════════════════════
# APPLICAZIONE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
class ADIMAILLauncher:

    # Palette
    OVERLAY_COLOR  = "#0d1f2d"
    OVERLAY_ALPHA  = 178
    TITLE_COLOR    = "#e8f4fd"
    SUBTITLE_COLOR = "#90bcd4"
    ACCENT         = "#4a9eca"
    MENU_BG        = "#0d1f2d"
    MENU_FG        = "#c8d8e8"
    MENU_ACTIVE_BG = "#1a3a5c"
    MENU_ACTIVE_FG = "#4a9eca"
    WIN_W, WIN_H   = 820, 500    # leggermente più largo per 4 badge

    def __init__(self, root: tk.Tk):
        self.root        = root
        self.bg_pil      = None
        self.bg_photo    = None
        self.overlay_pil = None
        self._resize_job = None
        self._moduli_extra_cache = {}  # Cache per moduli extra
        self._tema_corrente = 'scuro'  # Tema corrente predefinito

        self._configura_finestra()
        self._costruisci_menu()
        self._costruisci_canvas()
        self._carica_sfondo_default()

    # ── Setup finestra ────────────────────────────────────────────────────────
    def _configura_finestra(self):
        self.root.title("ADIMAIL — IZ8GCH")
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.root.minsize(560, 360)
        self.root.configure(bg=self.MENU_BG)
        try:
            self.root.iconbitmap(os.path.join(BASE_DIR, "icon.ico"))
        except Exception:
            pass

    # ── Menu a tendina ────────────────────────────────────────────────────────
    def _costruisci_menu(self):
        barra = tk.Menu(self.root,
                        bg=self.MENU_BG, fg=self.MENU_FG,
                        activebackground=self.MENU_ACTIVE_BG,
                        activeforeground=self.MENU_ACTIVE_FG,
                        relief=tk.FLAT, bd=0)
        self.root.config(menu=barra)

        def menu(label):
            m = tk.Menu(barra, tearoff=0,
                        bg=self.MENU_BG, fg=self.MENU_FG,
                        activebackground=self.MENU_ACTIVE_BG,
                        activeforeground=self.MENU_ACTIVE_FG,
                        relief=tk.FLAT, bd=1,
                        font=("Georgia", 10))
            barra.add_cascade(label=label, menu=m)
            return m

        # ── Moduli ────────────────────────────────────────────────────────────
        m_mod = menu("  Moduli  ")
        
        # Carica moduli dinamici dal config o dalla cache
        if hasattr(self, '_moduli_extra_cache') and self._moduli_extra_cache:
            moduli_extra = self._moduli_extra_cache
        else:
            moduli_extra = self._carica_moduli_extra()
            self._moduli_extra_cache = moduli_extra
        
        # Moduli standard
        m_mod.add_command(
            label="📥  Import ADIF  →  PNG  →  Database",
            command=lambda: self._avvia(SCRIPT_CREATORE))
        m_mod.add_separator()
        m_mod.add_command(
            label="📧  Gestione email e record QSL",
            command=lambda: self._avvia(SCRIPT_RECORDS))
        m_mod.add_separator()
        m_mod.add_command(
            label="🎨  Editor visuale modelli QSL",
            command=lambda: self._avvia(SCRIPT_EDITOR))
        m_mod.add_separator()
        
        # Moduli extra dinamici
        for chiave, (nome_file, descrizione) in moduli_extra.items():
            if chiave not in ["creatore", "records", "editor", "config"]:
                m_mod.add_command(
                    label=f"{descrizione}",
                    command=lambda f=nome_file: self._avvia_modulo_extra(f))
                m_mod.add_separator()
        
        # ── NUOVO ─────────────────────────────────────────────────────────────
        m_mod.add_command(
            label="⚙  Configurazione  (config.ini)",
            command=lambda: self._avvia(SCRIPT_CONFIG))

        # ── Sfondo ────────────────────────────────────────────────────────────
        m_sfondo = menu("  Sfondo  ")
        m_sfondo.add_command(
            label="📂  Carica immagine di sfondo…",
            command=self._scegli_sfondo)
        m_sfondo.add_command(
            label="🔄  Ripristina sfondo predefinito",
            command=self._carica_sfondo_default)
        m_sfondo.add_separator()
        m_sfondo.add_command(
            label="✖  Rimuovi sfondo  (gradiente)",
            command=self._rimuovi_sfondo)

        # ── Info ──────────────────────────────────────────────────────────────
        m_info = menu("  Info  ")
        m_info.add_command(
            label="ℹ  Informazioni e versione",
            command=self._mostra_info)
        m_info.add_command(
            label="📜  Licenza GNU GPL v3",
            command=lambda: DialogoInfo(self.root))
        m_info.add_separator()
        m_info.add_command(
            label="🌐  Sito web IZ8GCH",
            command=self._apri_sito)
        m_info.add_separator()
        m_info.add_command(label="Esci", command=self.root.quit)

    # ── Canvas principale ─────────────────────────────────────────────────────
    def _costruisci_canvas(self):
        self.canvas = tk.Canvas(self.root, highlightthickness=0,
                                bd=0, bg=self.MENU_BG)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        # Clic sui badge del canvas
        self.canvas.bind("<Button-1>", self._canvas_click)

    # ── Sfondo ────────────────────────────────────────────────────────────────
    def _carica_sfondo_default(self):
        if os.path.exists(BG_IMAGE_DEFAULT):
            self._carica_immagine(BG_IMAGE_DEFAULT)
        else:
            self._rimuovi_sfondo()

    def _scegli_sfondo(self):
        path = filedialog.askopenfilename(
            title="Seleziona immagine di sfondo",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("Tutti", "*.*")])
        if path:
            self._carica_immagine(path)

    def _carica_immagine(self, path: str):
        try:
            self.bg_pil = Image.open(path).convert("RGBA")
            self._ridisegna()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare l'immagine:\n{e}")

    def _rimuovi_sfondo(self):
        self.bg_pil = None
        self._ridisegna()

    # ── Ridimensionamento (debounced) ─────────────────────────────────────────
    def _on_resize(self, _event=None):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._ridisegna)

    def _ridisegna(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            self.root.after(80, self._ridisegna)
            return

        self.canvas.delete("all")
        self._badge_rects = []   # lista di (x0,y0,x1,y1, script) per hit-test

        if self.bg_pil:
            orig_w, orig_h = self.bg_pil.size
            scale = max(w / orig_w, h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img_r = self.bg_pil.resize((new_w, new_h), Image.LANCZOS)
            x0 = (new_w - w) // 2
            y0 = (new_h - h) // 2
            img_r = img_r.crop((x0, y0, x0 + w, y0 + h))
            overlay   = Image.new("RGBA", (w, h),
                                  (13, 31, 45, self.OVERLAY_ALPHA))
            composita = Image.alpha_composite(img_r, overlay).convert("RGB")
        else:
            composita = self._gradiente(w, h)

        self.bg_photo = ImageTk.PhotoImage(composita)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)
        self._disegna_testi(w, h)

    def _gradiente(self, w: int, h: int) -> Image.Image:
        img  = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        top  = (13, 31, 45)
        bot  = (5,  15, 28)
        for y in range(h):
            t = y / max(h - 1, 1)
            r = int(top[0] + (bot[0] - top[0]) * t)
            g = int(top[1] + (bot[1] - top[1]) * t)
            b = int(top[2] + (bot[2] - top[2]) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        return img

    def _disegna_testi(self, w: int, h: int):
        cx = w // 2

        # Linee decorative
        self.canvas.create_line(cx - 130, h // 2 - 68,
                                cx + 130, h // 2 - 68,
                                fill=self.ACCENT, width=1)

        # Titolo
        self.canvas.create_text(
            cx, h // 2 - 46,
            text="ADIMAIL",
            font=("Georgia", 38, "bold"),
            fill=self.TITLE_COLOR,
            anchor="center")

        # Sottotitolo
        self.canvas.create_text(
            cx, h // 2 + 6,
            text="Amateur Digital Image Mail",
            font=("Georgia", 13, "italic"),
            fill=self.SUBTITLE_COLOR,
            anchor="center")

        # Callsign
        self.canvas.create_text(
            cx, h // 2 + 30,
            text="IZ8GCH",
            font=("Courier", 11, "bold"),
            fill=self.ACCENT,
            anchor="center")

        self.canvas.create_line(cx - 130, h // 2 + 50,
                                cx + 130, h // 2 + 50,
                                fill=self.ACCENT, width=1)

        # Suggerimento menu
        self.canvas.create_text(
            cx, h - 22,
            text="Usa il menu in alto per accedere ai moduli  •  IZ8GCH",
            font=("Courier", 8),
            fill="#405870",
            anchor="center")

        # ── Badge moduli (dinamici, cliccabili) ─────────────────────────────────
        # Posizioni orizzontali simmetriche per i badge
        badge_y  = h // 2 + 95
        badge_w  = 90    # semi-larghezza area cliccabile
        badge_h  = 44    # semi-altezza area cliccabile

        # Moduli standard (sempre presenti)
        moduli_standard = [
            ("📥", "Import ADIF",   SCRIPT_CREATORE),
            ("📧", "Email & Record", SCRIPT_RECORDS),
            ("🎨", "Editor QSL",    SCRIPT_EDITOR),
            ("⚙",  "Config",        SCRIPT_CONFIG),
        ]
        
        # Carica moduli extra dalla cache o dal config
        if hasattr(self, '_moduli_extra_cache') and self._moduli_extra_cache:
            moduli_extra_dict = self._moduli_extra_cache
        else:
            moduli_extra_dict = self._carica_moduli_extra()
            self._moduli_extra_cache = moduli_extra_dict
        
        # Converti moduli extra in lista per badge
        moduli_extra = []
        for chiave, (nome_file, descrizione) in moduli_extra_dict.items():
            # Estrai icona dalla descrizione o usa default
            if "🔧" in descrizione:
                icona = "🔧"
            elif "📊" in descrizione:
                icona = "📊"
            elif "🗺️" in descrizione:
                icona = "🗺️"
            elif "📏" in descrizione:
                icona = "📏"
            else:
                icona = "🔧"
            
            # Nome breve per il badge
            nome_breve = chiave.replace("_", " ").title()
            if len(nome_breve) > 12:
                nome_breve = nome_breve[:10] + "..."
            
            moduli_extra.append((icona, nome_breve, nome_file))
        
        # Combina tutti i moduli
        tutti_moduli = moduli_standard + moduli_extra
        
        # Limita a massimo 8 badge per motivi di spazio
        if len(tutti_moduli) > 8:
            tutti_moduli = tutti_moduli[:8]
        
        n      = len(tutti_moduli)
        
        # Adatta lo spread in base al numero di badge
        if n <= 4:
            spread = min(220, w // 2 - 60)
        else:
            # Per più di 4 badge, riduci lo spread e usa 2 righe
            spread = min(300, w // 2 - 80)
        
        # Calcola posizioni X
        if n <= 4:
            # Una singola riga
            xs = [cx + int(spread * (i - (n-1)/2) / ((n-1)/2) if n > 1 else cx)
                  for i in range(n)]
            badge_positions = [(xs[i], badge_y) for i in range(n)]
        else:
            # Due righe per più di 4 badge
            prima_riga = n // 2
            seconda_riga = n - prima_riga
            
            # Prima riga
            xs1 = [cx + int(spread * (i - (prima_riga-1)/2) / ((prima_riga-1)/2) if prima_riga > 1 else cx)
                   for i in range(prima_riga)]
            
            # Seconda riga
            xs2 = [cx + int(spread * (i - (seconda_riga-1)/2) / ((seconda_riga-1)/2) if seconda_riga > 1 else cx)
                   for i in range(seconda_riga)]
            
            badge_positions = [(xs1[i], badge_y) for i in range(prima_riga)]
            badge_positions += [(xs2[i], badge_y + 70) for i in range(seconda_riga)]

        self._badge_rects = []

        for (ico, lbl, script), (bx, by) in zip(tutti_moduli, badge_positions):
            # Verifica esistenza file
            if os.path.isabs(script):
                esiste = os.path.exists(script)
            else:
                esiste = os.path.exists(os.path.join(BASE_DIR, script))
            
            colore = self.ACCENT if esiste else "#3a4a5a"
            col_bg = "#0d2535" if esiste else "#0a1520"

            # Sfondo rettangolo badge
            rect = self.canvas.create_rectangle(
                bx - badge_w, by - badge_h,
                bx + badge_w, by + badge_h,
                fill=col_bg, outline=colore if esiste else "#1a2a3a",
                width=1)

            self.canvas.create_text(
                bx, by - 16,
                text=ico,
                font=("", 18),
                fill=colore,
                anchor="center")

            self.canvas.create_text(
                bx, by + 8,
                text=lbl,
                font=("Courier", 7, "bold" if esiste else "normal"),
                fill=colore,
                anchor="center")

            stato = "▶ clicca" if esiste else "non trovato"
            self.canvas.create_text(
                bx, by + 24,
                text=stato,
                font=("Courier", 7),
                fill="#4a6a80" if esiste else "#5a2222",
                anchor="center")

            # Registra area per hit-test
            self._badge_rects.append((
                bx - badge_w, by - badge_h,
                bx + badge_w, by + badge_h,
                script))

    # ── Click sui badge canvas ────────────────────────────────────────────────
    def _canvas_click(self, event):
        for x0, y0, x1, y1, script in getattr(self, "_badge_rects", []):
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self._avvia(script)
                return

    # ── Avvio script ─────────────────────────────────────────────────────────
    def _carica_moduli_extra(self):
        """Carica moduli extra dal config.ini"""
        config = configparser.ConfigParser()
        moduli_extra = {}
        
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if "MODULES" in config:
                for chiave, nome_file in config["MODULES"].items():
                    if chiave not in ["creatore", "records", "editor", "config"]:
                        # Descrizione generica per moduli extra
                        descrizione = f"🔧  {chiave.title()}"
                        moduli_extra[chiave] = (nome_file, descrizione)
        
        return moduli_extra
    
    def _avvia_modulo_extra(self, nome_file):
        """Avvia un modulo extra Python"""
        # Se è un percorso completo, usalo direttamente
        if os.path.isabs(nome_file):
            script_path = nome_file
        else:
            # Altrimenti, cerca nella directory base
            script_path = os.path.join(BASE_DIR, nome_file)
        
        if os.path.exists(script_path):
            try:
                subprocess.Popen([sys.executable, script_path])
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile avviare {nome_file}: {e}")
        else:
            messagebox.showerror("Errore", f"File {script_path} non trovato")
    
    def _avvia(self, script: str):
        if not os.path.exists(script):
            messagebox.showerror(
                "Script non trovato",
                f"Il file non è stato trovato:\n\n{script}\n\n"
                "Verifica il percorso nella sezione PERCORSI SCRIPT del sorgente.")
            return
        try:
            process = subprocess.Popen([sys.executable, script])
            
            # Se è config_editor, abilita il refresh automatico del config
            if "config_editor" in script:
                self._monitor_config_editor(process)
                
        except Exception as e:
            messagebox.showerror("Errore avvio", str(e))
    
    def _monitor_config_editor(self, process):
        """Monitora il processo config_editor per rileggere config.ini alla chiusura"""
        def check_process():
            # Controlla se il processo è ancora attivo ogni 2 secondi
            if process.poll() is not None:
                # Il processo è terminato, ricarica i moduli extra
                self._ricarica_moduli_dopo_config()
            else:
                # Processo ancora attivo, continua a monitorare
                self.root.after(2000, check_process)
        
        # Inizia il monitoraggio
        self.root.after(2000, check_process)
    
    def _ricarica_moduli_dopo_config(self):
        """Ricarica i moduli extra dopo la modifica del config.ini"""
        try:
            # Forza la rilettura completa del config.ini
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            
            # Controlla se il tema è cambiato
            tema_cambiato = False
            if "UI" in config and "tema" in config["UI"]:
                nuovo_tema = config["UI"]["tema"].lower()
                # Carica il tema corrente per confronto
                tema_corrente = getattr(self, '_tema_corrente', 'scuro')
                if nuovo_tema != tema_corrente:
                    tema_cambiato = True
                    self._tema_corrente = nuovo_tema
                    print(f"[DEBUG] Tema cambiato da '{tema_corrente}' a '{nuovo_tema}'")
            
            # Resetta la cache e ricarica da zero
            self._moduli_extra_cache = {}
            
            # Ricarica i moduli extra dal config aggiornato
            moduli_extra = {}
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
                if "MODULES" in config:
                    for chiave, nome_file in config["MODULES"].items():
                        if chiave not in ["creatore", "records", "editor", "config"]:
                            # Descrizione generica per moduli extra
                            descrizione = f"🔧  {chiave.title()}"
                            moduli_extra[chiave] = (nome_file, descrizione)
            
            # Aggiorna la cache con i nuovi dati
            self._moduli_extra_cache = moduli_extra
            
            # Ricostruisci completamente il menu per includere/rimuovere moduli
            self._ricostruisci_menu()
            
            # Forza il ridisegno completo dell'interfaccia grafica
            self._ridisegna()
            
            # Mostra messaggio dettagliato
            messaggio = f"Il file config.ini è stato modificato.\n"
            messaggio += f"Moduli extra trovati: {len(moduli_extra)}\n"
            
            if tema_cambiato:
                messaggio += f"\n⚠️ Tema cambiato in '{self._tema_corrente}'.\n"
                messaggio += "Riavvia l'applicazione per applicare il nuovo tema."
            else:
                messaggio += "Menu e badge sono stati aggiornati automaticamente."
            
            # Mostra il messaggio solo se non ci sono errori critici
            if not tema_cambiato:
                messagebox.showinfo("Configurazione Aggiornata", messaggio)
            else:
                # Per cambi tema, mostra un avviso più prominente
                messagebox.showwarning("Tema Modificato", messaggio)
            
        except Exception as e:
            messagebox.showwarning(
                "Attenzione", 
                f"Impossibile ricaricare completamente i moduli:\n{e}\n\n"
                "Riavvia l'applicazione per vedere tutte le modifiche."
            )
    
    def _ricostruisci_menu(self):
        """Ricostruisci completamente il menu dei moduli"""
        try:
            # Distruggi il menu esistente e ricrealo completamente
            # Questo garantisce che i moduli rimossi spariscano dal menu
            self._costruisci_menu()
        except Exception as e:
            print(f"Errore ricostruendo menu: {e}")
            # Fallback: forza un ridisegno completo
            self._ridisegna()

    # ── Info ─────────────────────────────────────────────────────────────────
    def _mostra_info(self):
        DialogoInfo(self.root)

    def _apri_sito(self):
        import webbrowser
        webbrowser.open("https://iz8gch.jimdofree.com/")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    ADIMAILLauncher(root)
    root.mainloop()
