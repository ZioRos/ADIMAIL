# QSL Card Text Editor PRO — IZ8GCH
# v9 — rispetto esatto modello JSON + coerenza pixel PIL↔canvas Tk
#
# FIX rispetto v8:
#   [P1] Scala font PIL↔Tk: campo.dimensione = px sull'immagine finale.
#        Canvas mostra dim / dpi_ratio * zoom  (dpi_ratio = export_dpi / screen_dpi).
#        Usa size negativo Tk (pixel assoluti) per coerenza con PIL.
#   [P2] adatta_w: max_px coerente tra PIL (px immagine) e Tk (px canvas scalati).
#   [P3] hit_test_campo: bbox calcolato con lo stesso font usato per il disegno.
#   [P4/P7] genera_qsl accetta un'immagine PIL già pronta (self.bg ridimensionato)
#        invece di rileggere sempre il file originale dal disco.
#   [P5] Screen DPI rilevato a runtime con winfo_fpixels("1i").
#   [P6] adatta_w canvas: ricerca binaria invece di loop pixel-per-pixel.
#   [P8] _pannello_rett: usa metodo pubblico aggiorna_lista_pubblica().
#   [P9] _carica_modello: aggiorna correttamente self.bg ridimensionando se necessario.

import os
import re
import json
import math
import sqlite3
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
from PIL import Image, ImageDraw, ImageFont, ImageTk

DB_FILE     = "qsl_records.db"
OUTPUT_DIR  = "qsl_output"
MODELS_DIR  = "qsl_models"
CONFIG_FILE = "config.ini"

CANVAS_W          = 900
CANVAS_H          = 600
GRID_STEP_DEFAULT = 20
GRID_COLOR        = "#a0a0ff"
GRID_DASH         = (2, 4)
ADATTA_MAX_W_DEFAULT = 0.35

# ══════════════════════════════════════════════════════════════════════════════
# COSTANTI DIMENSIONI QSL  (IARU — A6 landscape 148×105 mm)
# ══════════════════════════════════════════════════════════════════════════════
QSL_MM_W        = 148
QSL_MM_H        = 105
QSL_DPI_PRINT   = 300
QSL_DPI_HOME    = 150
QSL_DPI_DIGITAL = 96
QSL_SIZE_TOL    = 10          # tolleranza px per "già ottimale"

def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / 25.4))

def dimensioni_qsl(dpi: int = QSL_DPI_PRINT, bleed_mm: float = 0.0):
    w = mm_to_px(QSL_MM_W + bleed_mm * 2, dpi)
    h = mm_to_px(QSL_MM_H + bleed_mm * 2, dpi)
    return w, h

QSL_TARGET_W, QSL_TARGET_H = dimensioni_qsl(QSL_DPI_PRINT)   # 1748 × 1240

# ── Costanti DB campi / stili ────────────────────────────────────────────────
CAMPI_DB = [
    ("call",     "Nominativo"), ("qso_date", "Data"),
    ("time_on",  "Ora"),        ("mode",     "Modo"),
    ("band",     "Banda"),      ("rst_sent", "RST"),
    ("name",     "Nome"),       ("qth",      "QTH"),
    ("grid",     "Locatore"),   ("email",    "Email"),
]

STILI_RETTANGOLO = [
    "Singolo", "Doppio", "Triplo",
    "Trattini", "Punti", "Tratto-Punto",
    "Onda", "Angoli decorativi",
]

# ══════════════════════════════════════════════════════════════════════════════
# PALETTE TEMI
# ══════════════════════════════════════════════════════════════════════════════
TEMI = {
    "scuro": {
        "bg":             "#1e2530", "bg_alt":         "#252d3a",
        "bg_input":       "#151e28", "fg":             "#d0dce8",
        "fg_dim":         "#5a7090", "accent":         "#4a9eca",
        "barra_btn_bg":   "#1a4a72", "barra_fg":       "#c8dce8",
        "listbox_bg":     "#151e28", "listbox_fg":     "#c8dce8",
        "listbox_sel_bg": "#2e5080", "listbox_sel_fg": "#ffffff",
        "canvas_bg":      "#3a3a4a", "entry_bg":       "#151e28",
        "entry_fg":       "#d0dce8", "entry_sel_bg":   "#2e5080",
        "sep":            "#2a3a4a", "ttk_theme":      "clam",
        "warn_bg":        "#3a2800", "warn_fg":        "#f0a030",
    },
    "chiaro": {
        "bg":             "#f0f4f8", "bg_alt":         "#ffffff",
        "bg_input":       "#ffffff", "fg":             "#1a2a3a",
        "fg_dim":         "#6a7f96", "accent":         "#1a3a5c",
        "barra_btn_bg":   "#2e6da4", "barra_fg":       "#ffffff",
        "listbox_bg":     "#ffffff", "listbox_fg":     "#1a2a3a",
        "listbox_sel_bg": "#b0ccee", "listbox_sel_fg": "#0d1f2d",
        "canvas_bg":      "#777777", "entry_bg":       "#ffffff",
        "entry_fg":       "#1a2a3a", "entry_sel_bg":   "#b0ccee",
        "sep":            "#c8d8e8", "ttk_theme":      "clam",
        "warn_bg":        "#fff3cd", "warn_fg":        "#856404",
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
        print(f"[DEBUG] Tema salvato in qsl_editor2: {tema}")
    except Exception as e:
        print(f"[ERRORE] Salvataggio tema qsl_editor2: {e}")

def _font_di_sistema() -> list:
    famiglie = sorted(set(tkfont.families()))
    return famiglie if famiglie else ["Arial"]

# ══════════════════════════════════════════════════════════════════════════════
# FORMATTAZIONE DATA / ORA
# ══════════════════════════════════════════════════════════════════════════════
def formatta_data(v: str) -> str:
    if not v: return v
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", v.strip())
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v.strip())
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return v

def formatta_ora(v: str) -> str:
    if not v: return v
    m = re.fullmatch(r"(\d{2})(\d{2})\d{2}", v.strip())
    if m: return f"{m.group(1)}:{m.group(2)}"
    m = re.fullmatch(r"(\d{2})(\d{2})", v.strip())
    if m: return f"{m.group(1)}:{m.group(2)}"
    m = re.fullmatch(r"(\d{2}):(\d{2}):\d{2}", v.strip())
    if m: return f"{m.group(1)}:{m.group(2)}"
    m = re.fullmatch(r"(\d{2}):(\d{2})", v.strip())
    if m: return v.strip()
    return v

# ══════════════════════════════════════════════════════════════════════════════
# SCALA FONT  [P1][P2][P5]
# ══════════════════════════════════════════════════════════════════════════════
# campo.dimensione  = pixel ASSOLUTI sull'immagine PIL finale (@ export_dpi)
# Sul canvas Tk con zoom Z e schermo a screen_dpi:
#   dim_canvas_px = dim_pil * zoom / dpi_ratio
#   dpi_ratio     = export_dpi / screen_dpi
#
# Con size=-N Tk tratta N come pixel logici dello schermo (non punti tipografici).
# Questo garantisce che 1px PIL ↔ 1px schermo quando zoom=1 e dpi_ratio=1.

_SCREEN_DPI: float = 96.0   # aggiornato a runtime in AppQSLEditor.__init__

def _dpi_ratio(export_dpi: int) -> float:
    """Rapporto pixel immagine / pixel schermo."""
    return export_dpi / max(1.0, _SCREEN_DPI)

def _dim_pil_to_canvas(dim_pil: int, zoom: float, export_dpi: int) -> int:
    """Converte dimensione font (px immagine PIL) → px canvas Tk."""
    return max(1, int(round(dim_pil * zoom / _dpi_ratio(export_dpi))))

def _dim_canvas_to_pil(dim_canvas: int, zoom: float, export_dpi: int) -> int:
    """Inverso: px canvas Tk → px immagine PIL."""
    return max(1, int(round(dim_canvas * _dpi_ratio(export_dpi) / zoom)))

# ══════════════════════════════════════════════════════════════════════════════
# DIALOG ESPORTAZIONE
# ══════════════════════════════════════════════════════════════════════════════
class DialogoEsportazione(tk.Toplevel):
    PRESET = [
        ("Standard QSL (900×600 @ 300 DPI)",           300, 0.0),
        ("Standard QSL + bleed 3 mm (900×600 @ 300 DPI)", 300, 3.0),
        ("Bassa qualità (900×600 @ 150 DPI)",            150, 0.0),
        ("Digitale/email (900×600 @ 96 DPI)",           96, 0.0),
        ("Personalizzato…",                              0, 0.0),
    ]

    def __init__(self, parent, palette=None):
        super().__init__(parent)
        self.title("Opzioni esportazione QSL")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        p = palette or TEMI["chiaro"]
        self.configure(bg=p["bg"])
        self._p          = p
        self._dpi        = tk.IntVar(value=300)
        self._bleed      = tk.DoubleVar(value=0.0)
        self._preset_v   = tk.IntVar(value=0)
        self._custom_w   = tk.IntVar(value=900)
        self._custom_h   = tk.IntVar(value=600)
        self._usa_custom = False
        self._confermato = False
        self._build()
        self._aggiorna_info()
        self.update_idletasks()
        px = parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py = parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}")
        self.wait_window(self)

    def _build(self):
        p = self._p
        hdr = tk.Frame(self, bg=p["accent"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📐  Dimensioni e qualità esportazione QSL",
                 bg=p["accent"], fg="#ffffff",
                 font=("Arial",10,"bold")).pack(padx=12, pady=7, anchor="w")
        body = tk.Frame(self, bg=p["bg"])
        body.pack(fill=tk.BOTH, padx=16, pady=10)
        info = tk.Frame(body, bg=p.get("warn_bg", p["bg_alt"]), relief=tk.FLAT, bd=1)
        info.pack(fill=tk.X, pady=(0,10))
        tk.Label(info,
                 text=f"Standard IARU:  {QSL_MM_W} × {QSL_MM_H} mm  (formato A6 landscape)",
                 bg=p.get("warn_bg", p["bg_alt"]),
                 fg=p.get("warn_fg", p["fg"]),
                 font=("Arial",8,"bold")).pack(padx=8, pady=4, anchor="w")
        tk.Label(body, text="Preset:", bg=p["bg"], fg=p["fg"],
                 font=("Arial",9,"bold")).pack(anchor="w", pady=(0,3))
        for i,(label,dpi,bleed) in enumerate(self.PRESET):
            tk.Radiobutton(body, text=label, variable=self._preset_v, value=i,
                           bg=p["bg"], fg=p["fg"], selectcolor=p["bg_alt"],
                           activebackground=p["bg"], activeforeground=p["accent"],
                           font=("Arial",9),
                           command=self._su_preset).pack(anchor="w", padx=8, pady=1)
        self._frm_custom = tk.Frame(body, bg=p["bg"])
        self._frm_custom.pack(fill=tk.X, padx=20, pady=(2,6))
        for label, var in [("DPI:", self._dpi),
                            ("Largh. px:", self._custom_w),
                            ("Alt. px:",   self._custom_h)]:
            r = tk.Frame(self._frm_custom, bg=p["bg"]); r.pack(side=tk.LEFT, padx=6)
            tk.Label(r, text=label, bg=p["bg"], fg=p["fg_dim"],
                     font=("Arial",8)).pack(anchor="w")
            tk.Spinbox(r, from_=50, to=9999, width=6, textvariable=var,
                       bg=p["entry_bg"], fg=p["entry_fg"], font=("Arial",9),
                       command=self._aggiorna_info).pack()
        self._frm_custom.pack_forget()
        fb = tk.Frame(body, bg=p["bg"]); fb.pack(fill=tk.X, pady=(2,6))
        tk.Label(fb, text="Bleed (mm per lato):", bg=p["bg"], fg=p["fg"],
                 font=("Arial",9)).pack(side=tk.LEFT)
        tk.Spinbox(fb, from_=0, to=10, increment=0.5, width=5,
                   textvariable=self._bleed, format="%.1f",
                   bg=p["entry_bg"], fg=p["entry_fg"],
                   command=self._aggiorna_info).pack(side=tk.LEFT, padx=6)
        tk.Label(fb, text="(3 mm consigliato per tipografie)",
                 bg=p["bg"], fg=p["fg_dim"], font=("Arial",8)).pack(side=tk.LEFT)
        ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=8)
        tk.Label(body, text="Dimensioni finali:", bg=p["bg"], fg=p["fg"],
                 font=("Arial",9,"bold")).pack(anchor="w")
        self._lbl_info = tk.Label(body, text="", bg=p["bg"],
                                   fg=p["accent"], font=("Courier",9))
        self._lbl_info.pack(anchor="w", padx=8, pady=(2,8))
        bf = tk.Frame(self, bg=p["bg"]); bf.pack(fill=tk.X, padx=16, pady=(0,14))
        tk.Button(bf, text="Annulla", command=self.destroy,
                  bg=p["bg_alt"], fg=p["fg"],
                  relief=tk.FLAT, padx=12, pady=5, cursor="hand2").pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text="✔  Genera QSL", command=self._conferma,
                  bg=p["accent"], fg="#ffffff",
                  relief=tk.FLAT, padx=12, pady=5,
                  font=("Arial",9,"bold"), cursor="hand2").pack(side=tk.RIGHT, padx=4)

    def _su_preset(self):
        idx = self._preset_v.get()
        _, dpi, bleed = self.PRESET[idx]
        self._usa_custom = (dpi == 0)
        if self._usa_custom:
            self._frm_custom.pack(fill=tk.X, padx=20, pady=(2,6))
        else:
            self._frm_custom.pack_forget()
            self._dpi.set(dpi); self._bleed.set(bleed)
        self._aggiorna_info()

    def _aggiorna_info(self):
        try:
            dpi   = self._dpi.get()
            bleed = self._bleed.get()
            # Forza sempre 900x600
            w, h = 900, 600
            self._custom_w.set(w); self._custom_h.set(h)
            bleed_px = mm_to_px(bleed, dpi) if not self._usa_custom else 0
            self._lbl_info.configure(
                text=f"{w} × {h} px   @{dpi} DPI"
                     + (f"   (bleed {bleed_px} px/lato)" if bleed > 0 else ""))
        except (ValueError, tk.TclError):
            pass

    def _conferma(self):
        self._confermato = True; self.destroy()

    @property
    def confermato(self) -> bool: return self._confermato
    @property
    def dpi(self) -> int: return max(50, self._dpi.get())
    @property
    def dimensioni(self) -> tuple:
        # Forza sempre 900x600
        return 900, 600
    @property
    def bleed_mm(self) -> float: return self._bleed.get()


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG DIMENSIONI SFONDO
# ══════════════════════════════════════════════════════════════════════════════
class DialogoDimensioniSfondo(tk.Toplevel):
    RIDIMENSIONA = "ridimensiona"
    CONTINUA     = "continua"
    ANNULLA      = "annulla"

    def __init__(self, parent, w_att, h_att, w_tgt, h_tgt, dpi_tgt=300, palette=None):
        super().__init__(parent)
        self.title("Dimensioni sfondo non ottimali")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        p = palette or TEMI["chiaro"]
        self.configure(bg=p["bg"])
        self._azione = self.ANNULLA
        hdr = tk.Frame(self, bg=p.get("warn_bg","#fff3cd"))
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⚠  Dimensioni sfondo non ottimali per la stampa",
                 bg=p.get("warn_bg","#fff3cd"), fg=p.get("warn_fg","#856404"),
                 font=("Arial",10,"bold")).pack(padx=12, pady=8, anchor="w")
        body = tk.Frame(self, bg=p["bg"])
        body.pack(fill=tk.BOTH, padx=16, pady=10)
        for label, valore, colore in [
            ("Dimensioni rilevate:", f"{w_att} × {h_att} px", p["fg"]),
            ("Dimensioni ottimali:",
             f"{w_tgt} × {h_tgt} px  ({QSL_MM_W}×{QSL_MM_H} mm @ {dpi_tgt} DPI)",
             p["accent"]),
        ]:
            r = tk.Frame(body, bg=p["bg"]); r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, width=22, anchor="w",
                     bg=p["bg"], fg=p["fg_dim"], font=("Arial",9)).pack(side=tk.LEFT)
            tk.Label(r, text=valore, anchor="w", bg=p["bg"], fg=colore,
                     font=("Courier",9,"bold")).pack(side=tk.LEFT)
        ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=8)
        tk.Label(body,
                 text="Il ridimensionamento automatico adatta l'immagine usando il\n"
                      "filtro Lanczos (alta qualità). Il file originale NON viene sovrascritto.",
                 bg=p["bg"], fg=p["fg"], font=("Arial",9), justify=tk.LEFT
                 ).pack(anchor="w", pady=(0,8))
        bf = tk.Frame(self, bg=p["bg"]); bf.pack(fill=tk.X, padx=16, pady=(0,14))
        tk.Button(bf, text="Annulla",
                  command=lambda: self._scegli(self.ANNULLA),
                  bg=p["bg_alt"], fg=p["fg"],
                  relief=tk.FLAT, padx=10, pady=5, cursor="hand2"
                  ).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text="Continua senza ridimensionare",
                  command=lambda: self._scegli(self.CONTINUA),
                  bg=p["bg_alt"], fg=p["fg"],
                  relief=tk.FLAT, padx=10, pady=5, cursor="hand2"
                  ).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text=f"✔  Ridimensiona a {w_tgt}×{h_tgt} px",
                  command=lambda: self._scegli(self.RIDIMENSIONA),
                  bg=p["accent"], fg="#ffffff",
                  relief=tk.FLAT, padx=10, pady=5,
                  font=("Arial",9,"bold"), cursor="hand2"
                  ).pack(side=tk.RIGHT, padx=4)
        self.update_idletasks()
        px = parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py = parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}")
        self.wait_window(self)

    def _scegli(self, azione):
        self._azione = azione; self.destroy()

    @property
    def azione(self) -> str: return self._azione


# ══════════════════════════════════════════════════════════════════════════════
# RETTANGOLO D'AREA
# ══════════════════════════════════════════════════════════════════════════════
HANDLE_SIZE = 8

class RettangoloArea:
    def __init__(self):
        self.nome     = "Area 1"; self.attivo   = True
        self.x_pct    = 0.05;     self.y_pct    = 0.05
        self.w_pct    = 0.40;     self.h_pct    = 0.25
        self.colore   = "#FFD700"; self.spessore = 3
        self.stile    = "Singolo"; self.raggio   = 0
        self.gap      = 6

    def to_dict(self) -> dict:
        return {k: getattr(self,k) for k in
                ("nome","attivo","x_pct","y_pct","w_pct","h_pct",
                 "colore","spessore","stile","raggio","gap")}

    @classmethod
    def from_dict(cls, d: dict) -> "RettangoloArea":
        r = cls()
        for k in ("nome","attivo","x_pct","y_pct","w_pct","h_pct",
                  "colore","spessore","stile","raggio","gap"):
            if k in d: setattr(r, k, d[k])
        if r.stile not in STILI_RETTANGOLO: r.stile = "Singolo"
        return r

    def box_px(self, W: int, H: int):
        return (int(self.x_pct*W), int(self.y_pct*H),
                int((self.x_pct+self.w_pct)*W), int((self.y_pct+self.h_pct)*H))


# ══════════════════════════════════════════════════════════════════════════════
# PRIMITIVE PIL
# ══════════════════════════════════════════════════════════════════════════════
def _rettangolo_arrotondato_pil(draw, box, raggio, colore, spessore):
    x0,y0,x1,y1 = [int(v) for v in box]
    if x1-x0 < 2 or y1-y0 < 2: return
    r = min(max(0,raggio),(x1-x0)//2,(y1-y0)//2)
    if r <= 0:
        draw.rectangle([x0,y0,x1,y1], outline=colore, width=spessore); return
    draw.arc([x0,y0,x0+2*r,y0+2*r],     180,270, outline=colore, width=spessore)
    draw.arc([x1-2*r,y0,x1,y0+2*r],     270,360, outline=colore, width=spessore)
    draw.arc([x0,y1-2*r,x0+2*r,y1],      90,180, outline=colore, width=spessore)
    draw.arc([x1-2*r,y1-2*r,x1,y1],       0, 90, outline=colore, width=spessore)
    draw.line([x0+r,y0,x1-r,y0], fill=colore, width=spessore)
    draw.line([x0+r,y1,x1-r,y1], fill=colore, width=spessore)
    draw.line([x0,y0+r,x0,y1-r], fill=colore, width=spessore)
    draw.line([x1,y0+r,x1,y1-r], fill=colore, width=spessore)

def _linea_trattini_pil(draw,x0,y0,x1,y1,colore,sp,lt=14,gap=7):
    dist = math.hypot(x1-x0,y1-y0)
    if dist==0: return
    ux,uy = (x1-x0)/dist,(y1-y0)/dist
    pos,on = 0.0,True
    while pos < dist:
        fine = min(pos+(lt if on else gap), dist)
        if on:
            draw.line([(x0+ux*pos,y0+uy*pos),(x0+ux*fine,y0+uy*fine)],
                      fill=colore, width=sp)
        pos,on = fine,not on

def _linea_punti_pil(draw,x0,y0,x1,y1,colore,sp,gap=9):
    _linea_trattini_pil(draw,x0,y0,x1,y1,colore,sp,lt=sp+1,gap=gap)

def _linea_tratto_punto_pil(draw,x0,y0,x1,y1,colore,sp):
    dist = math.hypot(x1-x0,y1-y0)
    if dist==0: return
    ux,uy=(x1-x0)/dist,(y1-y0)/dist
    seq=[12,5,3,5]; pos,idx,on=0.0,0,True
    while pos < dist:
        l=seq[idx%len(seq)]; fine=min(pos+l,dist)
        if on:
            draw.line([(x0+ux*pos,y0+uy*pos),(x0+ux*fine,y0+uy*fine)],
                      fill=colore, width=sp)
        pos,on,idx=fine,not on,idx+1

def _rettangolo_trattini_pil(draw,box,colore,sp,stile):
    x0,y0,x1,y1=box
    fn=(_linea_punti_pil if stile=="Punti" else
        _linea_tratto_punto_pil if stile=="Tratto-Punto" else
        _linea_trattini_pil)
    fn(draw,x0,y0,x1,y0,colore,sp); fn(draw,x1,y0,x1,y1,colore,sp)
    fn(draw,x1,y1,x0,y1,colore,sp); fn(draw,x0,y1,x0,y0,colore,sp)

def _onda_pil(draw,x0,y0,x1,y1,colore,sp,amp=8,freq=24):
    for (xa,xb,ya,vert) in [(x0,x1,y0,False),(x0,x1,y1,False),
                             (y0,y1,x0,True),(y0,y1,x1,True)]:
        L=xb-xa; n=max(2,int(L//2)); pts=[]
        for k in range(n+1):
            t=k/n; d=amp*math.sin(2*math.pi*t*(L/freq))
            pts.append((ya+d,xa+t*L) if vert else (xa+t*L,ya+d))
        if len(pts)>=2: draw.line(pts,fill=colore,width=sp)

def _angoli_pil(draw,box,colore,sp,lung=40):
    x0,y0,x1,y1=box
    for ax,ay,sx,sy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
        draw.line([(ax,ay),(ax+sx*lung,ay)],fill=colore,width=sp)
        draw.line([(ax,ay),(ax,ay+sy*lung)],fill=colore,width=sp)

def _disegna_rettangolo_pil(draw,box,stile,colore,sp,raggio,gap):
    x0,y0,x1,y1=box; r,g=raggio,gap
    if   stile=="Singolo":
        _rettangolo_arrotondato_pil(draw,box,r,colore,sp)
    elif stile=="Doppio":
        _rettangolo_arrotondato_pil(draw,box,r,colore,sp)
        _rettangolo_arrotondato_pil(draw,[x0+g+sp,y0+g+sp,x1-g-sp,y1-g-sp],
                                    max(0,r-g-sp),colore,sp)
    elif stile=="Triplo":
        g2=max(2,g//2)
        _rettangolo_arrotondato_pil(draw,box,r,colore,sp)
        _rettangolo_arrotondato_pil(draw,[x0+g2+sp,y0+g2+sp,x1-g2-sp,y1-g2-sp],
                                    max(0,r-g2-sp),colore,sp)
        _rettangolo_arrotondato_pil(draw,[x0+2*(g2+sp),y0+2*(g2+sp),
                                          x1-2*(g2+sp),y1-2*(g2+sp)],
                                    max(0,r-2*(g2+sp)),colore,sp)
    elif stile in ("Trattini","Punti","Tratto-Punto"):
        _rettangolo_trattini_pil(draw,box,colore,sp,stile)
    elif stile=="Onda":
        _onda_pil(draw,x0,y0,x1,y1,colore,sp)
    elif stile=="Angoli decorativi":
        _angoli_pil(draw,box,colore,sp,lung=max(10,min(60,(x1-x0+y1-y0)//8)))

def applica_rettangoli_pil(img: Image.Image, rettangoli: list) -> Image.Image:
    draw=ImageDraw.Draw(img); W,H=img.size
    for r in rettangoli:
        if not r.attivo: continue
        _disegna_rettangolo_pil(draw,list(r.box_px(W,H)),r.stile,r.colore,
                                 max(1,r.spessore),r.raggio,r.gap)
    return img


# ══════════════════════════════════════════════════════════════════════════════
# PRIMITIVE CANVAS TK
# ══════════════════════════════════════════════════════════════════════════════
def _rettangolo_arrotondato_tk(canvas,box,r,colore,sp,dash=()):
    x0,y0,x1,y1=box
    r=min(r,(x1-x0)//2,(y1-y0)//2) if r>0 else 0
    kw={"fill":"","outline":colore,"width":sp}
    kw2={"fill":colore,"width":sp}
    if dash: kw["dash"]=kw2["dash"]=dash
    if r<=0:
        canvas.create_rectangle(x0,y0,x1,y1,**kw); return
    canvas.create_arc(x0,    y0,    x0+2*r,y0+2*r,start=90, extent=90,style="arc",**kw)
    canvas.create_arc(x1-2*r,y0,    x1,    y0+2*r,start=0,  extent=90,style="arc",**kw)
    canvas.create_arc(x0,    y1-2*r,x0+2*r,y1,    start=180,extent=90,style="arc",**kw)
    canvas.create_arc(x1-2*r,y1-2*r,x1,    y1,    start=270,extent=90,style="arc",**kw)
    canvas.create_line(x0+r,y0,x1-r,y0,**kw2); canvas.create_line(x0+r,y1,x1-r,y1,**kw2)
    canvas.create_line(x0,y0+r,x0,y1-r,**kw2); canvas.create_line(x1,y0+r,x1,y1-r,**kw2)

def _onda_tk(canvas,box,colore,sp,amp=6,freq=22):
    x0,y0,x1,y1=box
    kw={"fill":colore,"width":sp,"smooth":True}
    for (xa,xb,ya,vert) in [(x0,x1,y0,False),(x0,x1,y1,False),
                             (y0,y1,x0,True),(y0,y1,x1,True)]:
        L=xb-xa; n=max(2,L//3); pts=[]
        for k in range(n+1):
            t=k/n; d=amp*math.sin(2*math.pi*t*(L/freq))
            if vert: pts+=[ya+d,xa+t*L]
            else:    pts+=[xa+t*L,ya+d]
        canvas.create_line(*pts,**kw)

def _angoli_tk(canvas,box,colore,sp,lung=28):
    x0,y0,x1,y1=box; kw={"fill":colore,"width":sp}
    for ax,ay,sx,sy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
        canvas.create_line(ax,ay,ax+sx*lung,ay,**kw)
        canvas.create_line(ax,ay,ax,ay+sy*lung,**kw)

def _disegna_rettangolo_tk(canvas,box,stile,colore,sp,raggio,gap,dash_zoom=1.0):
    x0,y0,x1,y1=[int(v) for v in box]; r,g=raggio,gap
    dm={"Trattini":    (max(1,int(12*dash_zoom)),max(1,int(6*dash_zoom))),
        "Punti":       (max(1,int(3*dash_zoom)), max(1,int(8*dash_zoom))),
        "Tratto-Punto":(max(1,int(10*dash_zoom)),max(1,int(4*dash_zoom)),
                        max(1,int(3*dash_zoom)), max(1,int(4*dash_zoom)))}
    if stile=="Singolo":
        _rettangolo_arrotondato_tk(canvas,(x0,y0,x1,y1),r,colore,sp)
    elif stile=="Doppio":
        _rettangolo_arrotondato_tk(canvas,(x0,y0,x1,y1),r,colore,sp)
        _rettangolo_arrotondato_tk(canvas,(x0+g+sp,y0+g+sp,x1-g-sp,y1-g-sp),
                                   max(0,r-g-sp),colore,sp)
    elif stile=="Triplo":
        g2=max(2,g//2)
        _rettangolo_arrotondato_tk(canvas,(x0,y0,x1,y1),r,colore,sp)
        _rettangolo_arrotondato_tk(canvas,(x0+g2+sp,y0+g2+sp,x1-g2-sp,y1-g2-sp),
                                   max(0,r-g2-sp),colore,sp)
        _rettangolo_arrotondato_tk(canvas,(x0+2*(g2+sp),y0+2*(g2+sp),
                                           x1-2*(g2+sp),y1-2*(g2+sp)),
                                   max(0,r-2*(g2+sp)),colore,sp)
    elif stile in ("Trattini","Punti","Tratto-Punto"):
        _rettangolo_arrotondato_tk(canvas,(x0,y0,x1,y1),r,colore,sp,dash=dm.get(stile,(6,4)))
    elif stile=="Onda":
        _onda_tk(canvas,(x0,y0,x1,y1),colore,sp)
    elif stile=="Angoli decorativi":
        _angoli_tk(canvas,(x0,y0,x1,y1),colore,sp,lung=max(10,min(50,(x1-x0+y1-y0)//8)))

def disegna_rettangoli_su_canvas(canvas,rettangoli,img_w,img_h,zoom,sel_idx=None):
    for i,r in enumerate(rettangoli):
        if not r.attivo: continue
        x0=r.x_pct*img_w*zoom; y0=r.y_pct*img_h*zoom
        x1=(r.x_pct+r.w_pct)*img_w*zoom; y1=(r.y_pct+r.h_pct)*img_h*zoom
        sp=max(1,int(r.spessore*zoom))
        rz=int(r.raggio*zoom); gz=int(r.gap*zoom)
        _disegna_rettangolo_tk(canvas,(x0,y0,x1,y1),r.stile,r.colore,sp,rz,gz,dash_zoom=zoom)
        if i==sel_idx:
            canvas.create_rectangle(x0-2,y0-2,x1+2,y1+2,
                                     outline="orange",width=1,dash=(4,2))
            hs=HANDLE_SIZE
            canvas.create_rectangle(x1-hs,y1-hs,x1+hs,y1+hs,
                                     fill="orange",outline="#a05000",width=1,
                                     tags="resize_handle")


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO TESTO
# ══════════════════════════════════════════════════════════════════════════════
class CampoTesto:
    def __init__(self, tipo="libero", valore="Testo"):
        self.tipo=tipo; self.valore=valore
        self.x_pct=0.05; self.y_pct=0.5
        self.font_nome="Arial"; self.dimensione=75  # Imposto a 75 come richiesto
        self.colore="#000000"
        self.adatta_w=False; self.adatta_max_w=ADATTA_MAX_W_DEFAULT

    def risolvi(self, record: dict) -> str:
        if self.tipo=="libero": return self.valore
        raw=record.get(self.valore,"") or ""
        if self.valore=="qso_date": return formatta_data(raw)
        if self.valore=="time_on":  return formatta_ora(raw)
        return raw

    def to_dict(self) -> dict:
        return {"tipo":self.tipo,"valore":self.valore,
                "x_pct":self.x_pct,"y_pct":self.y_pct,
                "font_nome":self.font_nome,"dimensione":self.dimensione,
                "colore":self.colore,
                "adatta_w":self.adatta_w,"adatta_max_w":self.adatta_max_w}

    @classmethod
    def from_dict(cls, d: dict) -> "CampoTesto":
        obj=cls()
        obj.tipo        =str(d.get("tipo",       obj.tipo))
        obj.valore      =str(d.get("valore",     obj.valore))
        obj.x_pct       =float(d.get("x_pct",   obj.x_pct))
        obj.y_pct       =float(d.get("y_pct",   obj.y_pct))
        obj.font_nome   =str(d.get("font_nome",  obj.font_nome))
        obj.dimensione  =int(d.get("dimensione", obj.dimensione))
        obj.colore      =str(d.get("colore",     obj.colore))
        obj.adatta_w    =bool(d.get("adatta_w",  obj.adatta_w))
        obj.adatta_max_w=float(d.get("adatta_max_w", obj.adatta_max_w))
        return obj


# ══════════════════════════════════════════════════════════════════════════════
# MODELLO QSL
# ══════════════════════════════════════════════════════════════════════════════
class ModelloQSL:
    def __init__(self):
        self.bg_path=""; self.campi=[]; self.rettangoli=[]

    def salva(self, percorso: str):
        with open(percorso,"w",encoding="utf-8") as f:
            json.dump({"bg_path":self.bg_path,
                       "campi":     [c.to_dict() for c in self.campi],
                       "rettangoli":[r.to_dict() for r in self.rettangoli]},
                      f, indent=2, ensure_ascii=False)

    @classmethod
    def carica(cls, percorso: str) -> "ModelloQSL":
        with open(percorso,encoding="utf-8") as f:
            d=json.load(f)
        m=cls()
        m.bg_path    =d.get("bg_path","")
        m.campi      =[CampoTesto.from_dict(x)
                       for x in d.get("campi", d.get("fields",[]))]
        m.rettangoli =[RettangoloArea.from_dict(x)
                       for x in d.get("rettangoli", d.get("bordi",[]))]
        return m


# ══════════════════════════════════════════════════════════════════════════════
# RICERCA FONT
# ══════════════════════════════════════════════════════════════════════════════
def _cerca_font(nome: str, dimensione: int):
    import subprocess, glob
    for ext in ("",".ttf",".otf",".TTF",".OTF"):
        for base in (nome,nome.lower(),nome.replace(" ",""),
                     nome.replace(" ","-"),nome.replace(" ","_")):
            for directory in ("","C:/Windows/Fonts/","/Library/Fonts/",
                               os.path.expanduser("~/Library/Fonts/"),
                               "/usr/share/fonts/truetype/msttcorefonts/",
                               "/usr/share/fonts/truetype/"):
                try: return ImageFont.truetype(directory+base+ext, dimensione)
                except OSError: pass
    try:
        res=subprocess.run(["fc-match",nome,"--format=%{file}"],
                           capture_output=True,text=True,timeout=2)
        fc=res.stdout.strip()
        if fc and os.path.exists(fc): return ImageFont.truetype(fc,dimensione)
    except Exception: pass
    for radice in ("/usr/share/fonts","/usr/local/share/fonts"):
        for p in glob.glob(os.path.join(radice,"**","*.ttf"),recursive=True):
            if nome.lower().replace(" ","") in os.path.basename(p).lower().replace(" ",""):
                try: return ImageFont.truetype(p,dimensione)
                except OSError: pass
    for p in ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
              "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p,dimensione)
            except OSError: pass
    try: return ImageFont.load_default(size=dimensione)
    except TypeError: return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════════════════
# ADATTAMENTO FONT — PIL
# ══════════════════════════════════════════════════════════════════════════════
def _dimensione_adattata_pil(testo, font_nome, dim_max, larghezza_max_px):
    """Riduce dim_max finché il testo entra in larghezza_max_px (px PIL)."""
    dim=dim_max
    while dim>6:
        font=_cerca_font(font_nome,dim)
        try:
            bbox=font.getbbox(testo); w_txt=bbox[2]-bbox[0]
        except AttributeError:
            w_txt=int(font.getlength(testo))
        if w_txt<=larghezza_max_px: break
        dim-=1
    return dim


# ══════════════════════════════════════════════════════════════════════════════
# GENERAZIONE PNG FINALE  [P4][P7]
# ══════════════════════════════════════════════════════════════════════════════
def genera_qsl(modello: "ModelloQSL", record: dict, file_out: str,
               target_w: int = 900,
               target_h: int = 600,
               dpi: int = QSL_DPI_PRINT,
               bg_img: Image.Image = None):
    """
    Genera il PNG finale della QSL.

    Parametri:
        bg_img  : immagine PIL già caricata e ridimensionata (priorità sul disco).
                  Se None riapre modello.bg_path e ridimensiona.

    campo.dimensione  = px assoluti sull'immagine finale @ dpi.
    Le coordinate x_pct/y_pct sono sempre in percentuale sulla dimensione target.
    I rettangoli d'area usano le stesse coordinate percentuali.
    """
    # ── Sfondo ───────────────────────────────────────────────────
    if bg_img is not None:
        img = bg_img.copy().convert("RGBA")
        # Assicura dimensioni esatte anche se bg_img era già pronto
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)
    else:
        img = Image.open(modello.bg_path).convert("RGBA")
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    w, h = img.size   # w == target_w, h == target_h

    # ── Testi ─────────────────────────────────────────────────────
    for campo in modello.campi:
        testo = campo.risolvi(record)
        if not testo: continue

        # campo.dimensione = px PIL (coerente con il canvas Tk usando _dim_pil_to_canvas)
        dim = campo.dimensione
        if campo.adatta_w:
            max_px = int(campo.adatta_max_w * w)   # px immagine
            dim    = _dimensione_adattata_pil(testo, campo.font_nome, dim, max_px)

        font = _cerca_font(campo.font_nome, dim)
        draw.text(
            (int(campo.x_pct * w), int(campo.y_pct * h)),
            testo, fill=campo.colore, font=font
        )

    # ── Rettangoli d'area ─────────────────────────────────────────
    if modello.rettangoli:
        img = applica_rettangoli_pil(img, modello.rettangoli)

    img.convert("RGB").save(file_out, dpi=(dpi, dpi))


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÀ RIDIMENSIONAMENTO
# ══════════════════════════════════════════════════════════════════════════════
def _sfondo_ottimale(img: Image.Image, tw: int, th: int) -> bool:
    w,h = img.size
    return abs(w-tw)<=QSL_SIZE_TOL and abs(h-th)<=QSL_SIZE_TOL

def ridimensiona_sfondo(img: Image.Image, tw: int, th: int) -> Image.Image:
    return img.resize((tw,th), Image.LANCZOS)


# ══════════════════════════════════════════════════════════════════════════════
# PANNELLO RETTANGOLI D'AREA
# ══════════════════════════════════════════════════════════════════════════════
class PannelloRettangoli(ttk.Frame):
    def __init__(self, parent, modello_getter, on_change, on_select, palette_getter, **kw):
        super().__init__(parent,**kw)
        self._modello_getter=modello_getter
        self._on_change=on_change; self._on_select=on_select
        self._palette_getter=palette_getter; self._selezionato=None
        self._build()

    def _p(self): return self._palette_getter()
    def _rett(self): return self._modello_getter().rettangoli

    def _build(self):
        p=self._p()
        ttk.Label(self,text="Rettangoli d'area",font=("",9,"bold")
                  ).pack(anchor="w",padx=6,pady=(6,0))
        ttk.Label(self,text="Trascina per spostare · quadratino arancio per ridimensionare",
                  foreground=p["fg_dim"],font=("",7)).pack(anchor="w",padx=6)
        self._lista=tk.Listbox(self,height=5,activestyle="dotbox",
                                bg=p["listbox_bg"],fg=p["listbox_fg"],
                                selectbackground=p["listbox_sel_bg"],
                                selectforeground=p["listbox_sel_fg"],
                                relief=tk.FLAT,bd=1)
        self._lista.pack(fill="x",padx=6,pady=(2,0))
        self._lista.bind("<<ListboxSelect>>",self._su_selezione_lista)
        fb=ttk.Frame(self); fb.pack(fill="x",padx=6,pady=2)
        ttk.Button(fb,text="+ Aggiungi",command=self._aggiungi
                   ).pack(side="left",expand=True,fill="x")
        ttk.Button(fb,text="▲",width=3,command=self._sposta_su).pack(side="left")
        ttk.Button(fb,text="▼",width=3,command=self._sposta_giu).pack(side="left")
        ttk.Button(fb,text="✕ Rimuovi",command=self._rimuovi
                   ).pack(side="left",expand=True,fill="x")
        ttk.Separator(self,orient="horizontal").pack(fill="x",pady=4)

        prop=ttk.LabelFrame(self,text="Proprietà area selezionata")
        prop.pack(fill="x",padx=6,pady=(0,4))
        fn=ttk.Frame(prop); fn.pack(fill="x",padx=4,pady=2)
        ttk.Label(fn,text="Nome:",width=10,anchor="w").pack(side="left")
        self._var_nome=tk.StringVar()
        ttk.Entry(fn,textvariable=self._var_nome,width=14
                  ).pack(side="left",fill="x",expand=True)
        self._var_nome.trace_add("write",lambda *_: self._aggiorna_nome())
        self._var_attivo=tk.BooleanVar(value=True)
        ttk.Checkbutton(prop,text="Visibile",variable=self._var_attivo,
                        command=self._commit).pack(anchor="w",padx=4,pady=1)
        fs=ttk.Frame(prop); fs.pack(fill="x",padx=4,pady=2)
        ttk.Label(fs,text="Stile:",width=10,anchor="w").pack(side="left")
        self._var_stile=tk.StringVar()
        ttk.Combobox(fs,textvariable=self._var_stile,values=STILI_RETTANGOLO,
                     state="readonly",width=16
                     ).pack(side="left",fill="x",expand=True)
        self._var_stile.trace_add("write",lambda *_: self._commit())
        fc=ttk.Frame(prop); fc.pack(fill="x",padx=4,pady=2)
        ttk.Label(fc,text="Colore:",width=10,anchor="w").pack(side="left")
        self._anteprima_col=tk.Label(fc,bg="#FFD700",width=3,relief="solid",
                                      cursor="hand2",highlightthickness=1)
        self._anteprima_col.pack(side="left",padx=3)
        self._anteprima_col.bind("<Button-1>",lambda _: self._scegli_colore())
        ttk.Button(fc,text="Scegli…",command=self._scegli_colore).pack(side="left")
        self._var_sp=tk.IntVar(value=3); self._var_raggio=tk.IntVar(value=0)
        self._var_gap=tk.IntVar(value=6)
        self._spinrow(prop,"Spessore (px):",self._var_sp,1,60,"sp")
        self._spinrow(prop,"Raggio angoli:",self._var_raggio,0,200,"raggio",step=2)
        self._spinrow(prop,"Gap doppio:",   self._var_gap,1,80,"gap")
        ttk.Separator(prop,orient="horizontal").pack(fill="x",pady=3)
        ttk.Label(prop,text="Posizione e dimensione  (% immagine)",
                  font=("",8,"bold")).pack(anchor="w",padx=4,pady=(2,0))
        self._var_x=tk.DoubleVar(value=5.0); self._var_y=tk.DoubleVar(value=5.0)
        self._var_w=tk.DoubleVar(value=40.0); self._var_h=tk.DoubleVar(value=25.0)
        for label,var in [("X  (%):",self._var_x),("Y  (%):",self._var_y),
                           ("W (%):", self._var_w),("H  (%):",self._var_h)]:
            fr=ttk.Frame(prop); fr.pack(fill="x",padx=4,pady=1)
            ttk.Label(fr,text=label,width=8,anchor="w").pack(side="left")
            sp=ttk.Spinbox(fr,from_=0.1,to=99.9,increment=0.5,width=7,
                           textvariable=var,format="%.1f",command=self._commit_geom)
            sp.pack(side="left",padx=2)
            sp.bind("<Return>",  lambda _: self._commit_geom())
            sp.bind("<FocusOut>",lambda _: self._commit_geom())
            ttk.Button(fr,text="−",width=2,
                       command=lambda v=var: self._step_var(v,-0.5)).pack(side="left")
            ttk.Button(fr,text="+",width=2,
                       command=lambda v=var: self._step_var(v,+0.5)).pack(side="left")
        self._aggiorna_lista(); self._abilita_prop(False)

    def _spinrow(self,parent,label,var,lo,hi,key,step=1):
        fr=ttk.Frame(parent); fr.pack(fill="x",padx=4,pady=2)
        ttk.Label(fr,text=label,width=13,anchor="w").pack(side="left")
        sp=ttk.Spinbox(fr,from_=lo,to=hi,width=5,textvariable=var,command=self._commit)
        sp.pack(side="left",padx=2)
        sp.bind("<Return>",  lambda _: self._commit())
        sp.bind("<FocusOut>",lambda _: self._commit())
        ttk.Button(fr,text="−",width=2,
                   command=lambda: self._step_var(var,-step,lo,hi)).pack(side="left")
        ttk.Button(fr,text="+",width=2,
                   command=lambda: self._step_var(var,+step,lo,hi)).pack(side="left")

    def aggiorna_tema(self):
        p=self._p()
        self._lista.configure(bg=p["listbox_bg"],fg=p["listbox_fg"],
                               selectbackground=p["listbox_sel_bg"],
                               selectforeground=p["listbox_sel_fg"])
        try: self._anteprima_col.configure(highlightbackground=p["accent"])
        except Exception: pass

    # ── CRUD ─────────────────────────────────────────────────────
    def _aggiungi(self):
        rl=self._rett(); r=RettangoloArea()
        r.nome=f"Area {len(rl)+1}"
        r.y_pct=min(0.05+len(rl)*0.05,0.80)
        rl.append(r); self._selezionato=len(rl)-1
        self._aggiorna_lista(); self._carica_in_ui(r); self._abilita_prop(True)
        self._on_select(self._selezionato); self._on_change()

    def _rimuovi(self):
        if self._selezionato is None: return
        rl=self._rett()
        if not rl: return
        del rl[self._selezionato]
        self._selezionato=min(self._selezionato,len(rl)-1) if rl else None
        self._aggiorna_lista()
        if self._selezionato is not None and rl: self._carica_in_ui(rl[self._selezionato])
        else: self._abilita_prop(False)
        self._on_select(self._selezionato); self._on_change()

    def _sposta_su(self):
        if self._selezionato is None or self._selezionato==0: return
        rl=self._rett(); i=self._selezionato
        rl[i-1],rl[i]=rl[i],rl[i-1]
        self._selezionato-=1; self._aggiorna_lista(); self._on_change()

    def _sposta_giu(self):
        rl=self._rett()
        if self._selezionato is None or self._selezionato>=len(rl)-1: return
        i=self._selezionato; rl[i],rl[i+1]=rl[i+1],rl[i]
        self._selezionato+=1; self._aggiorna_lista(); self._on_change()

    def _su_selezione_lista(self,_=None):
        sel=self._lista.curselection()
        if not sel: return
        self._selezionato=sel[0]; rl=self._rett()
        if 0<=self._selezionato<len(rl):
            self._carica_in_ui(rl[self._selezionato]); self._abilita_prop(True)
        self._on_select(self._selezionato); self._on_change()

    def seleziona_esternamente(self,idx):
        self._selezionato=idx; self._aggiorna_lista(); rl=self._rett()
        if idx is not None and 0<=idx<len(rl):
            self._carica_in_ui(rl[idx]); self._abilita_prop(True)
        else: self._abilita_prop(False)

    def aggiorna_geom_da_modello(self):
        if self._selezionato is None: return
        rl=self._rett()
        if not(0<=self._selezionato<len(rl)): return
        r=rl[self._selezionato]
        self._var_x.set(round(r.x_pct*100,1)); self._var_y.set(round(r.y_pct*100,1))
        self._var_w.set(round(r.w_pct*100,1)); self._var_h.set(round(r.h_pct*100,1))

    # [P8] metodo pubblico invece di _aggiorna_lista chiamato dall'esterno
    def aggiorna_lista_pubblica(self):
        self._aggiorna_lista()

    def _carica_in_ui(self,r):
        self._var_nome.set(r.nome); self._var_attivo.set(r.attivo)
        self._var_stile.set(r.stile); self._anteprima_col.configure(bg=r.colore)
        self._var_sp.set(r.spessore); self._var_raggio.set(r.raggio)
        self._var_gap.set(r.gap)
        self._var_x.set(round(r.x_pct*100,1)); self._var_y.set(round(r.y_pct*100,1))
        self._var_w.set(round(r.w_pct*100,1)); self._var_h.set(round(r.h_pct*100,1))

    def _aggiorna_lista(self):
        rl=self._rett(); self._lista.delete(0,tk.END)
        for r in rl:
            self._lista.insert(tk.END,f"{'✔' if r.attivo else '✕'}  {r.nome}  [{r.stile}]")
        if self._selezionato is not None and self._selezionato<len(rl):
            self._lista.selection_set(self._selezionato)

    def _abilita_prop(self,stato:bool):
        s=tk.NORMAL if stato else tk.DISABLED
        for w in self.winfo_children():
            if isinstance(w,ttk.LabelFrame):
                for c in self._tutti_figli(w):
                    try: c.configure(state=s)
                    except tk.TclError: pass

    @staticmethod
    def _tutti_figli(w):
        res=[]
        for c in w.winfo_children(): res.append(c); res.extend(PannelloRettangoli._tutti_figli(c))
        return res

    def _commit(self,*_):
        if self._selezionato is None: return
        rl=self._rett()
        if not(0<=self._selezionato<len(rl)): return
        r=rl[self._selezionato]
        r.attivo=self._var_attivo.get(); r.stile=self._var_stile.get()
        r.spessore=max(1,self._var_sp.get()); r.raggio=max(0,self._var_raggio.get())
        r.gap=max(1,self._var_gap.get())
        self._aggiorna_lista(); self._on_change()

    def _commit_geom(self,*_):
        if self._selezionato is None: return
        rl=self._rett()
        if not(0<=self._selezionato<len(rl)): return
        r=rl[self._selezionato]
        try:
            r.x_pct=max(0.0,min(0.99,self._var_x.get()/100.0))
            r.y_pct=max(0.0,min(0.99,self._var_y.get()/100.0))
            r.w_pct=max(0.01,min(1.0-r.x_pct,self._var_w.get()/100.0))
            r.h_pct=max(0.01,min(1.0-r.y_pct,self._var_h.get()/100.0))
        except(ValueError,tk.TclError): pass
        self._on_change()

    def _aggiorna_nome(self):
        if self._selezionato is None: return
        rl=self._rett()
        if 0<=self._selezionato<len(rl):
            rl[self._selezionato].nome=self._var_nome.get(); self._aggiorna_lista()

    def _scegli_colore(self):
        if self._selezionato is None: return
        rl=self._rett()
        if not(0<=self._selezionato<len(rl)): return
        r=rl[self._selezionato]
        ris=colorchooser.askcolor(color=r.colore,title="Colore rettangolo",parent=self)
        if ris and ris[1]:
            r.colore=ris[1]; self._anteprima_col.configure(bg=r.colore); self._on_change()

    def _step_var(self,var,delta,lo=None,hi=None):
        try:
            v=var.get()+delta
            if lo is not None: v=max(lo,v)
            if hi is not None: v=min(hi,v)
            var.set(round(v,1) if isinstance(delta,float) else int(v))
        except(ValueError,tk.TclError): pass
        self._commit(); self._commit_geom()


# ══════════════════════════════════════════════════════════════════════════════
# APPLICAZIONE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
class AppQSLEditor:

    def __init__(self, root: tk.Tk):
        self.root=root
        self.root.title("QSL Designer PRO — IZ8GCH  v9")
        self.root.geometry("1340x820"); self.root.minsize(960,620)

        self.modello     = ModelloQSL()
        self.bg          = None   # Image PIL — dimensionata al target corrente
        self.bg_photo    = None
        self.zoom        = 1.0
        self.selezionato = None
        self.sel_rett    = None
        self.drag        = None
        self._drag_mode  = None
        self._primo_carico = True

        self._export_w   = QSL_TARGET_W
        self._export_h   = QSL_TARGET_H
        self._export_dpi = QSL_DPI_PRINT

        self.records=[]
        self.griglia_attiva=tk.BooleanVar(value=False)
        self.griglia_passo =tk.IntVar(value=GRID_STEP_DEFAULT)
        self._adatta_w_var    =tk.BooleanVar(value=False)
        self._adatta_maxw_var =tk.DoubleVar(value=ADATTA_MAX_W_DEFAULT*100)
        self._famiglie_font   =_font_di_sistema()
        self._tema_nome =_leggi_tema_config()
        self._p_        =TEMI[self._tema_nome]
        self._var_tema  =tk.StringVar(value=self._tema_nome)

        self._applica_tema_ttk()
        self._costruisci_ui()
        self._costruisci_menu()

        # [P5] Rileva screen DPI a runtime dopo che la finestra esiste
        global _SCREEN_DPI
        try:
            _SCREEN_DPI = self.root.winfo_fpixels("1i")
        except Exception:
            _SCREEN_DPI = 96.0

        self._applica_colori_tk()
        self._carica_db()

    def _palette(self): return self._p_

    # ══════════════════════════════════════════
    # TEMA
    # ══════════════════════════════════════════
    def _applica_tema_ttk(self):
        p=self._p_; style=ttk.Style(self.root)
        style.theme_use(p["ttk_theme"])
        style.configure(".",background=p["bg"],foreground=p["fg"],
                        fieldbackground=p["entry_bg"],troughcolor=p["bg_alt"],
                        selectbackground=p["entry_sel_bg"],selectforeground=p["fg"])
        style.configure("TFrame",background=p["bg"])
        style.configure("TLabel",background=p["bg"],foreground=p["fg"])
        style.configure("TLabelframe",background=p["bg"],foreground=p["accent"])
        style.configure("TLabelframe.Label",background=p["bg"],foreground=p["accent"],
                        font=("Arial",9,"bold"))
        style.configure("TEntry",fieldbackground=p["entry_bg"],foreground=p["entry_fg"],
                        insertcolor=p["fg"])
        style.configure("TButton",background=p["barra_btn_bg"],foreground=p["barra_fg"],
                        padding=[6,3])
        style.map("TButton",background=[("active",p["accent"])],
                  foreground=[("active","#ffffff")])
        style.configure("TScrollbar",background=p["bg_alt"],troughcolor=p["bg"],
                        arrowcolor=p["fg_dim"])
        style.configure("TCheckbutton",background=p["bg"],foreground=p["fg"])
        style.map("TCheckbutton",background=[("active",p["bg"])],
                  foreground=[("active",p["accent"])])
        style.configure("TCombobox",fieldbackground=p["entry_bg"],foreground=p["entry_fg"],
                        selectbackground=p["entry_sel_bg"],selectforeground=p["fg"])
        style.map("TCombobox",fieldbackground=[("readonly",p["entry_bg"])],
                  foreground=[("readonly",p["entry_fg"])])
        style.configure("TSpinbox",fieldbackground=p["entry_bg"],foreground=p["entry_fg"])
        style.configure("TSeparator",background=p["sep"])
        self.root.configure(bg=p["bg"])

    def _applica_colori_tk(self):
        p=self._p_
        if hasattr(self,"lista_campi"):
            self.lista_campi.configure(bg=p["listbox_bg"],fg=p["listbox_fg"],
                                        selectbackground=p["listbox_sel_bg"],
                                        selectforeground=p["listbox_sel_fg"])
        if hasattr(self,"anteprima_colore"):
            self.anteprima_colore.configure(highlightbackground=p["accent"],
                                             highlightthickness=1)
        if hasattr(self,"canvas"): self.canvas.configure(bg=p["canvas_bg"])
        if hasattr(self,"_pannello_rett"): self._pannello_rett.aggiorna_tema()
        self._aggiorna_lbl_info()

    def _cambia_tema(self,nome:str):
        if nome==self._tema_nome: return
        self._tema_nome=nome; self._p_=TEMI[nome]
        _salva_tema_config(nome)
        self._applica_tema_ttk(); self._applica_colori_tk()
        self._var_tema.set(nome); self.refresh()

    # ══════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════
    def _costruisci_ui(self):
        p=self._p_
        paned=ttk.PanedWindow(self.root,orient=tk.HORIZONTAL)
        paned.pack(fill="both",expand=True)
        sinistra=ttk.Frame(paned,width=310); sinistra.pack_propagate(False)
        paned.add(sinistra,weight=0)
        notebook=ttk.Notebook(sinistra); notebook.pack(fill="both",expand=True)

        # ── TAB Testi ──────────────────────────────────────────────
        tab_t=ttk.Frame(notebook); notebook.add(tab_t,text="  Testi  ")
        ttk.Label(tab_t,text="Campi",font=("",9,"bold")
                  ).pack(anchor="w",padx=6,pady=(6,0))
        self.lista_campi=tk.Listbox(tab_t,height=7,activestyle="dotbox",
                                     bg=p["listbox_bg"],fg=p["listbox_fg"],
                                     selectbackground=p["listbox_sel_bg"],
                                     selectforeground=p["listbox_sel_fg"],
                                     relief=tk.FLAT,bd=1)
        self.lista_campi.pack(fill="both",expand=False,padx=6,pady=(2,0))
        self.lista_campi.bind("<<ListboxSelect>>",self._seleziona_dalla_lista)
        fb=ttk.Frame(tab_t); fb.pack(fill="x",padx=6,pady=2)
        ttk.Button(fb,text="+ Testo",   command=self._aggiungi_testo
                   ).pack(side="left",expand=True,fill="x")
        ttk.Button(fb,text="+ Campo DB",command=self._aggiungi_campo_db
                   ).pack(side="left",expand=True,fill="x")
        ttk.Button(fb,text="✕ Elimina", command=self._elimina_campo
                   ).pack(side="left",expand=True,fill="x")
        ttk.Button(tab_t,text="↔ Allinea in altezza al primo",
                   command=self._allinea_altezza).pack(fill="x",padx=6,pady=(0,2))
        ttk.Separator(tab_t,orient="horizontal").pack(fill="x",pady=5)
        ttk.Label(tab_t,text="Testo libero").pack(anchor="w",padx=6)
        self.campo_testo=ttk.Entry(tab_t)
        self.campo_testo.pack(fill="x",padx=6,pady=2)
        self.campo_testo.bind("<KeyRelease>",self._aggiorna_testo)
        ttk.Separator(tab_t,orient="horizontal").pack(fill="x",pady=5)
        ttk.Label(tab_t,text="Font",font=("",9,"bold")).pack(anchor="w",padx=6)
        self.combo_font=ttk.Combobox(tab_t,values=self._famiglie_font,state="readonly")
        self.combo_font.pack(fill="x",padx=6,pady=2); self.combo_font.set("Arial")
        self.combo_font.bind("<<ComboboxSelected>>",self._aggiorna_font)
        fd=ttk.Frame(tab_t); fd.pack(fill="x",padx=6,pady=2)
        ttk.Label(fd,text="Dimensione (px img):").pack(side="left")
        self.spin_dim=ttk.Spinbox(fd,from_=1,to=2000,width=6,
                                   command=self._aggiorna_dimensione)
        self.spin_dim.set(75)   # Imposto default a 75 come richiesto
        self.spin_dim.pack(side="left",padx=4)
        self.spin_dim.bind("<Return>",  lambda e: self._aggiorna_dimensione())
        self.spin_dim.bind("<FocusOut>",lambda e: self._aggiorna_dimensione())
        ttk.Button(fd,text="−",width=2,command=lambda: self._step_dimensione(-1)
                   ).pack(side="left")
        ttk.Button(fd,text="+",width=2,command=lambda: self._step_dimensione(+1)
                   ).pack(side="left")
        # Label info mm equivalenti  [P1]
        self._lbl_font_mm=ttk.Label(tab_t,text="",foreground=p["fg_dim"],font=("",7))
        self._lbl_font_mm.pack(anchor="w",padx=8)
        fc=ttk.Frame(tab_t); fc.pack(fill="x",padx=6,pady=2)
        ttk.Label(fc,text="Colore:").pack(side="left")
        self.anteprima_colore=tk.Label(fc,bg="#000000",width=4,relief="solid",
                                        highlightthickness=1,
                                        highlightbackground=p["accent"])
        self.anteprima_colore.pack(side="left",padx=4)
        ttk.Button(fc,text="Scegli…",command=self._scegli_colore).pack(side="left")
        ttk.Separator(tab_t,orient="horizontal").pack(fill="x",pady=5)
        ttk.Label(tab_t,text="Adattamento larghezza",font=("",9,"bold")
                  ).pack(anchor="w",padx=6)
        ttk.Checkbutton(tab_t,text="Adatta dimensione al contenuto",
                        variable=self._adatta_w_var,
                        command=self._aggiorna_adatta_w
                        ).pack(anchor="w",padx=6,pady=2)
        fmw=ttk.Frame(tab_t); fmw.pack(fill="x",padx=6,pady=(0,2))
        ttk.Label(fmw,text="Larghezza max (%):").pack(side="left")
        self._spin_maxw=ttk.Spinbox(fmw,from_=5,to=100,width=5,
                                     textvariable=self._adatta_maxw_var,
                                     command=self._aggiorna_adatta_w)
        self._spin_maxw.pack(side="left",padx=4)
        self._spin_maxw.bind("<Return>",  lambda e: self._aggiorna_adatta_w())
        self._spin_maxw.bind("<FocusOut>",lambda e: self._aggiorna_adatta_w())
        ttk.Label(fmw,text="della larghezza card",foreground=p["fg_dim"]
                  ).pack(side="left")
        ttk.Separator(tab_t,orient="horizontal").pack(fill="x",pady=5)
        ttk.Label(tab_t,text="Anteprima record dal DB").pack(anchor="w",padx=6)
        self.combo_record=ttk.Combobox(tab_t,state="readonly")
        self.combo_record.pack(fill="x",padx=6,pady=2)
        self.combo_record.bind("<<ComboboxSelected>>",lambda e: self.refresh())

        # ── TAB Aree ───────────────────────────────────────────────
        tab_r=ttk.Frame(notebook); notebook.add(tab_r,text="  Aree  ")
        self._pannello_rett=PannelloRettangoli(
            tab_r,
            modello_getter=lambda: self.modello,
            on_change=self.refresh,
            on_select=self._su_selezione_rett,
            palette_getter=self._palette)
        self._pannello_rett.pack(fill="both",expand=True)

        # ── Canvas ─────────────────────────────────────────────────
        destra=ttk.Frame(paned); paned.add(destra,weight=1)
        toolbar=ttk.Frame(destra); toolbar.pack(fill="x",pady=2)
        ttk.Checkbutton(toolbar,text="Griglia",variable=self.griglia_attiva,
                        command=self.refresh).pack(side="left",padx=4)
        ttk.Label(toolbar,text="Passo:").pack(side="left")
        sp=ttk.Spinbox(toolbar,from_=5,to=200,width=4,
                       textvariable=self.griglia_passo,command=self.refresh)
        sp.pack(side="left")
        sp.bind("<Return>",  lambda e: self.refresh())
        sp.bind("<FocusOut>",lambda e: self.refresh())
        ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)
        ttk.Label(toolbar,text="Zoom:").pack(side="left")
        ttk.Button(toolbar,text="−",width=2,
                   command=lambda: self._zoom_step(-1)).pack(side="left",padx=1)
        ttk.Button(toolbar,text="+",width=2,
                   command=lambda: self._zoom_step(+1)).pack(side="left",padx=1)
        ttk.Button(toolbar,text="Adatta",width=7,
                   command=self._zoom_adatta).pack(side="left",padx=4)
        ttk.Button(toolbar,text="100%",width=5,
                   command=self._zoom_reset).pack(side="left",padx=1)
        self._lbl_zoom=ttk.Label(toolbar,text="100%",width=6,foreground=p["fg_dim"])
        self._lbl_zoom.pack(side="left",padx=2)
        ttk.Separator(toolbar,orient="vertical").pack(side="left",fill="y",padx=6)
        self._lbl_info=ttk.Label(toolbar,text="",foreground=p["fg_dim"],font=("",8))
        self._lbl_info.pack(side="left",padx=4)
        cf=ttk.Frame(destra); cf.pack(fill="both",expand=True)
        cf.rowconfigure(0,weight=1); cf.columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(cf,bg=p["canvas_bg"],
                              xscrollincrement=1,yscrollincrement=1)
        sb_x=ttk.Scrollbar(cf,orient=tk.HORIZONTAL,command=self.canvas.xview)
        sb_y=ttk.Scrollbar(cf,orient=tk.VERTICAL,  command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sb_x.set,yscrollcommand=sb_y.set)
        self.canvas.grid(row=0,column=0,sticky="nsew")
        sb_y.grid(row=0,column=1,sticky="ns")
        sb_x.grid(row=1,column=0,sticky="ew")
        self.canvas.bind("<ButtonPress-1>",  self._mouse_giu)
        self.canvas.bind("<B1-Motion>",      self._mouse_trascina)
        self.canvas.bind("<ButtonRelease-1>",self._mouse_su)
        self.canvas.bind("<MouseWheel>",     self._rotella)
        self.canvas.bind("<ButtonPress-2>",  self._pan_giu)
        self.canvas.bind("<B2-Motion>",      self._pan_muovi)
        self.canvas.bind("<Configure>",      self._on_canvas_configure)

    def _aggiorna_lbl_info(self):
        if not hasattr(self,"_lbl_info"): return
        if self.bg:
            w,h=self.bg.size
            txt=(f"Sfondo: {w}×{h}px  →  Export: "
                 f"{self._export_w}×{self._export_h}px @{self._export_dpi}DPI  "
                 f"| Screen DPI: {_SCREEN_DPI:.0f}")
        else:
            txt=f"Export: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI"
        self._lbl_info.configure(text=txt)

    def _aggiorna_lbl_font_mm(self, dim_pil: int):
        """Mostra dimensione equivalente in mm sull'immagine finale."""
        if not hasattr(self,"_lbl_font_mm"): return
        mm = dim_pil / self._export_dpi * 25.4
        dim_c = _dim_pil_to_canvas(dim_pil, 1.0, self._export_dpi)
        self._lbl_font_mm.configure(
            text=f"≈ {mm:.1f} mm @{self._export_dpi}DPI  "
                 f"(canvas zoom=1: {dim_c}px)")

    # ══════════════════════════════════════════
    # MENU
    # ══════════════════════════════════════════
    def _costruisci_menu(self):
        p=self._p_
        barra=tk.Menu(self.root,bg=p["bg_alt"],fg=p["fg"],
                      activebackground=p["accent"],activeforeground="#ffffff",
                      relief=tk.FLAT)
        self.root.config(menu=barra)
        def sub():
            return tk.Menu(barra,tearoff=0,bg=p["bg_alt"],fg=p["fg"],
                           activebackground=p["accent"],activeforeground="#ffffff",
                           relief=tk.FLAT,bd=1,font=("Arial",9))
        mf=sub(); barra.add_cascade(label="File",menu=mf)
        mf.add_command(label="Carica Sfondo…",  command=self._carica_sfondo)
        mf.add_command(label="Salva Modello…",  command=self._salva_modello)
        mf.add_command(label="Carica Modello…", command=self._carica_modello)
        mf.add_separator()
        mf.add_command(label="Esci",command=self.root.quit)
        mv=sub(); barra.add_cascade(label="Vista",menu=mv)
        mv.add_checkbutton(label="Mostra griglia",variable=self.griglia_attiva,
                           command=self.refresh)
        mv.add_separator()
        mv.add_command(label="Zoom adatta",command=self._zoom_adatta)
        mv.add_command(label="Zoom 100%",  command=self._zoom_reset)
        mv.add_separator()
        mv.add_radiobutton(label="🌙  Tema scuro",variable=self._var_tema,value="scuro",
                           command=lambda: self._cambia_tema("scuro"))
        mv.add_radiobutton(label="☀  Tema chiaro",variable=self._var_tema,value="chiaro",
                           command=lambda: self._cambia_tema("chiaro"))
        ma=sub(); barra.add_cascade(label="Allinea",menu=ma)
        ma.add_command(label="Allinea in altezza al primo campo",
                       command=self._allinea_altezza)
        ma.add_command(label="Allinea tutti a sinistra (x del primo)",
                       command=self._allinea_sinistra)
        mg=sub(); barra.add_cascade(label="Genera",menu=mg)
        mg.add_command(label="Genera QSL…",command=self._genera_una)
        mg.add_separator()
        mg.add_command(label="📐 Imposta dimensioni export…",
                       command=self._imposta_dimensioni_export)
        mg.add_command(label="🔄 Ridimensiona sfondo corrente…",
                       command=self._ridimensiona_sfondo_manuale)

    # ══════════════════════════════════════════
    # DB
    # ══════════════════════════════════════════
    def _carica_db(self):
        if not os.path.exists(DB_FILE): return
        conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
        cur.execute("SELECT * FROM qsl_records")
        colonne=[d[0] for d in cur.description]
        for riga in cur.fetchall():
            self.records.append(dict(zip(colonne,riga)))
        conn.close()
        etichette=[r["call"]+"  "+r.get("qso_date","") for r in self.records]
        self.combo_record["values"]=etichette
        if etichette: self.combo_record.current(0)

    def _record_corrente(self) -> dict:
        i=self.combo_record.current()
        return self.records[i] if 0<=i<len(self.records) else {}

    # ══════════════════════════════════════════
    # CAMPI TESTO
    # ══════════════════════════════════════════
    def _aggiungi_testo(self):
        campo=CampoTesto("libero","Testo")
        self._applica_y_riferimento(campo)
        self.modello.campi.append(campo)
        self.selezionato=len(self.modello.campi)-1; self.refresh()

    def _aggiungi_campo_db(self):
        p=self._p_; win=tk.Toplevel(self.root)
        win.title("Aggiungi campo DB"); win.resizable(False,False)
        win.configure(bg=p["bg"])
        lb=tk.Listbox(win,selectmode=tk.MULTIPLE,width=30,height=12,
                       bg=p["listbox_bg"],fg=p["listbox_fg"],
                       selectbackground=p["listbox_sel_bg"],
                       selectforeground=p["listbox_sel_fg"],
                       relief=tk.FLAT,bd=1)
        for chiave,etichetta in CAMPI_DB:
            lb.insert(tk.END,f"{etichetta}  [{chiave}]")
        lb.pack(padx=10,pady=10,fill="both",expand=True)
        def ok():
            for i in lb.curselection():
                campo=CampoTesto("db",CAMPI_DB[i][0])
                self._applica_y_riferimento(campo)
                self.modello.campi.append(campo)
                self.selezionato=len(self.modello.campi)-1
            win.destroy(); self.refresh()
        ttk.Button(win,text="Aggiungi",command=ok).pack(pady=(0,8))

    def _applica_y_riferimento(self,campo):
        if self.modello.campi:
            # Allinea sia alla Y che alla X del primo campo
            primo_campo = self.modello.campi[0]
            campo.y_pct = primo_campo.y_pct  # Allineamento in alto
            campo.x_pct = primo_campo.x_pct  # Allineamento a sinistra

    def _allinea_altezza(self):
        if len(self.modello.campi)<2: return
        y=self.modello.campi[0].y_pct
        for c in self.modello.campi[1:]: c.y_pct=y
        self.refresh()

    def _allinea_sinistra(self):
        if len(self.modello.campi)<2: return
        x=self.modello.campi[0].x_pct
        for c in self.modello.campi[1:]: c.x_pct=x
        self.refresh()

    def _elimina_campo(self):
        if self.selezionato is None: return
        del self.modello.campi[self.selezionato]
        self.selezionato=None; self.refresh()

    def _seleziona_dalla_lista(self,_=None):
        sel=self.lista_campi.curselection()
        if not sel: return
        self.selezionato=sel[0]
        self._sincronizza_pannello_campo(self.modello.campi[self.selezionato])
        self.refresh()

    def _sincronizza_pannello_campo(self, campo):
        """Aggiorna tutti i widget del pannello sinistro con i valori del campo."""
        self.campo_testo.delete(0,tk.END)
        if campo.tipo=="libero": self.campo_testo.insert(0,campo.valore)
        self.combo_font.set(campo.font_nome
                            if campo.font_nome in self._famiglie_font else "Arial")
        self.spin_dim.delete(0,tk.END)
        self.spin_dim.insert(0,str(campo.dimensione))
        self.anteprima_colore.config(bg=campo.colore)
        self._adatta_w_var.set(campo.adatta_w)
        self._adatta_maxw_var.set(round(campo.adatta_max_w*100,1))
        self._aggiorna_lbl_font_mm(campo.dimensione)

    def _aggiorna_testo(self,_=None):
        if self.selezionato is None: return
        campo=self.modello.campi[self.selezionato]
        if campo.tipo=="libero": campo.valore=self.campo_testo.get(); self.refresh()

    def _aggiorna_font(self,_=None):
        if self.selezionato is None: return
        self.modello.campi[self.selezionato].font_nome=self.combo_font.get()
        self.refresh()

    def _aggiorna_dimensione(self):
        if self.selezionato is None: return
        try: dim=max(1,min(2000,int(self.spin_dim.get())))
        except ValueError: return
        self.modello.campi[self.selezionato].dimensione=dim
        self._aggiorna_lbl_font_mm(dim); self.refresh()

    def _step_dimensione(self,delta:int):
        if self.selezionato is None: return
        campo=self.modello.campi[self.selezionato]
        campo.dimensione=max(1,campo.dimensione+delta)
        self.spin_dim.delete(0,tk.END)
        self.spin_dim.insert(0,str(campo.dimensione))
        self._aggiorna_lbl_font_mm(campo.dimensione); self.refresh()

    def _scegli_colore(self):
        if self.selezionato is None:
            messagebox.showwarning("Attenzione","Seleziona prima un campo."); return
        campo=self.modello.campi[self.selezionato]
        r=colorchooser.askcolor(color=campo.colore,title="Scegli colore font",
                                 parent=self.root)
        if r and r[1]:
            campo.colore=r[1]; self.anteprima_colore.config(bg=campo.colore); self.refresh()

    def _aggiorna_adatta_w(self,_=None):
        if self.selezionato is None: return
        campo=self.modello.campi[self.selezionato]
        campo.adatta_w=self._adatta_w_var.get()
        try:
            pct=float(self._adatta_maxw_var.get())
            campo.adatta_max_w=max(0.05,min(1.0,pct/100.0))
        except(ValueError,tk.TclError): pass
        self.refresh()

    # ══════════════════════════════════════════
    # SFONDO  [P9]
    # ══════════════════════════════════════════
    def _carica_sfondo(self):
        path=filedialog.askopenfilename(
            filetypes=[("Immagini","*.png *.jpg *.jpeg *.bmp *.tiff")])
        if not path: return
        self._carica_e_prepara_sfondo(path)

    def _carica_e_prepara_sfondo(self, path: str):
        """
        Carica il file, chiede se ridimensionare, aggiorna self.bg.
        Usato sia da _carica_sfondo che da _carica_modello.
        """
        try:
            img=Image.open(path)
        except Exception as e:
            messagebox.showerror("Errore apertura sfondo",str(e)); return False

        w,h=img.size
        if not _sfondo_ottimale(img,self._export_w,self._export_h):
            dlg=DialogoDimensioniSfondo(
                self.root,w,h,self._export_w,self._export_h,
                self._export_dpi,palette=self._p_)
            azione=dlg.azione
            if azione==DialogoDimensioniSfondo.ANNULLA:
                return False
            elif azione==DialogoDimensioniSfondo.RIDIMENSIONA:
                img=ridimensiona_sfondo(img,self._export_w,self._export_h)
                messagebox.showinfo(
                    "Sfondo ridimensionato",
                    f"Ridimensionato da {w}×{h} a "
                    f"{self._export_w}×{self._export_h} px.\n"
                    f"Il file originale NON è stato sovrascritto.")
            # CONTINUA: usa img as-is

        self.modello.bg_path=path
        self.bg=img
        self._primo_carico=True
        self._aggiorna_lbl_info()
        return True

    def _ridimensiona_sfondo_manuale(self):
        if not self.bg:
            messagebox.showwarning("Attenzione","Nessuno sfondo caricato."); return
        w,h=self.bg.size
        if _sfondo_ottimale(self.bg,self._export_w,self._export_h):
            messagebox.showinfo("Già ottimale",
                                f"Lo sfondo è già {w}×{h} px."); return
        if not messagebox.askyesno("Ridimensiona sfondo",
                                    f"Ridimensionare da {w}×{h} a "
                                    f"{self._export_w}×{self._export_h} px?"):
            return
        self.bg=ridimensiona_sfondo(self.bg,self._export_w,self._export_h)
        self._aggiorna_lbl_info(); self.refresh()
        messagebox.showinfo("Completato",
                            f"Sfondo ridimensionato a "
                            f"{self._export_w}×{self._export_h} px.")

    def _imposta_dimensioni_export(self):
        dlg=DialogoEsportazione(self.root,palette=self._p_)
        if dlg.confermato:
            self._export_w,self._export_h=dlg.dimensioni
            self._export_dpi=dlg.dpi
            self._aggiorna_lbl_info()
            messagebox.showinfo(
                "Dimensioni export aggiornate",
                f"Export: {self._export_w}×{self._export_h} px @{self._export_dpi} DPI.\n"
                f"Le prossime generazioni useranno queste dimensioni.")

    # ══════════════════════════════════════════
    # ZOOM
    # ══════════════════════════════════════════
    def _zoom_step(self,d:int):
        self.zoom=(min(self.zoom*1.15,8.0) if d>0 else max(self.zoom/1.15,0.05))
        self.refresh()

    def _zoom_reset(self):
        self.zoom=1.0; self.refresh()
        self.canvas.xview_moveto(0); self.canvas.yview_moveto(0)

    def _zoom_adatta(self):
        if not self.bg: return
        self.canvas.update_idletasks()
        cw=self.canvas.winfo_width(); ch=self.canvas.winfo_height()
        if cw<10 or ch<10: return
        w,h=self.bg.size
        if w==0 or h==0: return
        self.zoom=max(0.05,min(8.0,min(cw/w,ch/h)*0.96))
        self.refresh()
        self.canvas.xview_moveto(0); self.canvas.yview_moveto(0)

    def _on_canvas_configure(self,event):
        if self._primo_carico and self.bg and event.width>10:
            self._primo_carico=False; self._zoom_adatta()

    # ══════════════════════════════════════════
    # SCALA FONT CANVAS  [P1][P2][P6]
    # ══════════════════════════════════════════
    def _dim_canvas(self, dim_pil: int) -> int:
        """
        Converte dim PIL → px canvas per il font Tk.
        Usa size negativo → Tk interpreta come pixel schermo assoluti.
        """
        return _dim_pil_to_canvas(dim_pil, self.zoom, self._export_dpi)

    def _dim_canvas_adattata(self, campo, testo: str) -> int:
        """
        [P2][P6] Calcola la dim canvas con adatta_w usando ricerca binaria.
        max_px_canvas = adatta_max_w * w_img * zoom / dpi_ratio
        """
        if not self.bg: return self._dim_canvas(campo.dimensione)
        w_img,_=self.bg.size
        # Larghezza massima in px canvas
        max_px_canvas=int(campo.adatta_max_w * w_img * self.zoom
                          / _dpi_ratio(self._export_dpi))
        max_px_canvas=max(1,max_px_canvas)
        # Ricerca binaria sulla dimensione PIL  [P6]
        lo,hi=1,campo.dimensione
        result=1
        while lo<=hi:
            mid=(lo+hi)//2
            dc=_dim_pil_to_canvas(mid,self.zoom,self._export_dpi)
            f=tkfont.Font(family=campo.font_nome,size=-dc)
            if f.measure(testo)<=max_px_canvas:
                result=mid; lo=mid+1
            else:
                hi=mid-1
        return _dim_pil_to_canvas(result,self.zoom,self._export_dpi)

    # ══════════════════════════════════════════
    # REFRESH
    # ══════════════════════════════════════════
    def refresh(self):
        self.canvas.delete("all")
        self.lista_campi.delete(0,tk.END)

        if self.bg:
            w,h=self.bg.size
            img_w=max(1,int(w*self.zoom)); img_h=max(1,int(h*self.zoom))
            img=self.bg.resize((img_w,img_h),Image.LANCZOS)
            self.bg_photo=ImageTk.PhotoImage(img)
            self.canvas.create_image(0,0,anchor="nw",image=self.bg_photo)
        else:
            w,h=CANVAS_W,CANVAS_H; img_w=w; img_h=h

        self.canvas.configure(scrollregion=(0,0,img_w,img_h))
        try: self._lbl_zoom.configure(text=f"{int(self.zoom*100)}%")
        except Exception: pass

        if self.griglia_attiva.get():
            try: passo=max(5,int(self.griglia_passo.get()))
            except(ValueError,tk.TclError): passo=GRID_STEP_DEFAULT
            for gx in range(passo,img_w,passo):
                self.canvas.create_line(gx,0,gx,img_h,fill=GRID_COLOR,dash=GRID_DASH)
            for gy in range(passo,img_h,passo):
                self.canvas.create_line(0,gy,img_w,gy,fill=GRID_COLOR,dash=GRID_DASH)

        if self.bg and self.modello.rettangoli:
            disegna_rettangoli_su_canvas(self.canvas,self.modello.rettangoli,
                                         w,h,self.zoom,sel_idx=self.sel_rett)

        record=self._record_corrente()
        for i,campo in enumerate(self.modello.campi):
            base=campo.valore if campo.tipo=="libero" else f"[{campo.valore}]"
            self.lista_campi.insert(tk.END,base+(" ⇔" if campo.adatta_w else ""))
            if not self.bg: continue

            cx=campo.x_pct*w*self.zoom
            cy=campo.y_pct*h*self.zoom
            testo=campo.risolvi(record)

            # [P1] dimensione canvas corretta
            if campo.adatta_w and testo:
                dc=self._dim_canvas_adattata(campo,testo)
            else:
                dc=self._dim_canvas(campo.dimensione)

            elem=self.canvas.create_text(
                cx,cy,text=testo,anchor="nw",
                font=(campo.font_nome,-dc),   # negativo = px assoluti Tk
                fill=campo.colore)

            if i==self.selezionato:
                box=self.canvas.bbox(elem)
                if box:
                    self.canvas.create_rectangle(
                        box,outline="orange",width=2,dash=(4,2))
            if i==self.selezionato and campo.adatta_w:
                ratio=_dpi_ratio(self._export_dpi)
                x_lim=cx+campo.adatta_max_w*w*self.zoom/ratio
                self.canvas.create_line(x_lim,cy-4,x_lim,cy+dc+4,
                                        fill="#ff6600",dash=(4,3),width=1)

        if(self.selezionato is not None
           and self.selezionato<len(self.modello.campi)):
            self.lista_campi.selection_set(self.selezionato)
            self.lista_campi.see(self.selezionato)

    # ══════════════════════════════════════════
    # HIT TEST CAMPO TESTO  [P3]
    # ══════════════════════════════════════════
    def _hit_test_campo(self, cx, cy):
        """
        [P3] Usa esattamente lo stesso font (size=-dc) usato nel refresh
        per calcolare il bbox del testo. Ordine inverso = priorità al campo
        disegnato sopra.
        """
        if not self.bg: return None
        w,h=self.bg.size
        record=self._record_corrente()
        for i in range(len(self.modello.campi)-1,-1,-1):
            campo=self.modello.campi[i]
            testo=campo.risolvi(record) or (campo.valore if campo.tipo=="libero" else "")
            if not testo: continue
            fx=campo.x_pct*w*self.zoom
            fy=campo.y_pct*h*self.zoom
            # Stessa logica del refresh
            if campo.adatta_w:
                dc=self._dim_canvas_adattata(campo,testo)
            else:
                dc=self._dim_canvas(campo.dimensione)
            f=tkfont.Font(family=campo.font_nome,size=-dc)
            fw=f.measure(testo)
            fh=f.metrics("linespace")
            if fx<=cx<=fx+fw and fy<=cy<=fy+fh:
                return i
        return None

    # ══════════════════════════════════════════
    # RETTANGOLI — selezione
    # ══════════════════════════════════════════
    def _su_selezione_rett(self,idx):
        self.sel_rett=idx; self.selezionato=None; self.refresh()

    def _hit_test_rettangolo(self,cx,cy):
        if not self.bg: return None,None
        w,h=self.bg.size; rl=self.modello.rettangoli; hs=HANDLE_SIZE+2
        def _check(r):
            if not r.attivo: return None
            x0=r.x_pct*w*self.zoom; y0=r.y_pct*h*self.zoom
            x1=(r.x_pct+r.w_pct)*w*self.zoom; y1=(r.y_pct+r.h_pct)*h*self.zoom
            if abs(cx-x1)<=hs and abs(cy-y1)<=hs: return "handle"
            tol=8
            if x0-tol<=cx<=x1+tol and y0-tol<=cy<=y1+tol: return "body"
            return None
        if self.sel_rett is not None and 0<=self.sel_rett<len(rl):
            res=_check(rl[self.sel_rett])
            if res: return self.sel_rett,res
        for i in range(len(rl)-1,-1,-1):
            if i==self.sel_rett: continue
            res=_check(rl[i])
            if res: return i,res
        return None,None

    # ══════════════════════════════════════════
    # MOUSE
    # ══════════════════════════════════════════
    def _mouse_giu(self,e):
        cx=self.canvas.canvasx(e.x); cy=self.canvas.canvasy(e.y)
        self.drag=(cx,cy); self._drag_mode=None

        # 1. Rettangoli
        idx,zona=self._hit_test_rettangolo(cx,cy)
        if idx is not None:
            self.sel_rett=idx; self.selezionato=None
            self._drag_mode="resize_rett" if zona=="handle" else "move_rett"
            self._pannello_rett.seleziona_esternamente(idx)
            self.refresh(); return

        # 2. Campi testo  [P3]
        ci=self._hit_test_campo(cx,cy)
        if ci is not None:
            self.sel_rett=None; self.selezionato=ci
            self._drag_mode="move_campo"
            self._pannello_rett.seleziona_esternamente(None)
            self.lista_campi.selection_clear(0,tk.END)
            self.lista_campi.selection_set(ci); self.lista_campi.see(ci)
            self._sincronizza_pannello_campo(self.modello.campi[ci])
            self.refresh(); return

        # 3. Area vuota → deseleziona tutto
        self.sel_rett=None; self.selezionato=None; self._drag_mode=None
        self._pannello_rett.seleziona_esternamente(None)
        self.refresh()

    def _mouse_trascina(self,e):
        if not self.drag or not self.bg: return
        cx,cy=self.canvas.canvasx(e.x),self.canvas.canvasy(e.y)
        dx,dy=cx-self.drag[0],cy-self.drag[1]
        self.drag=(cx,cy); w,h=self.bg.size
        if self._drag_mode=="move_rett" and self.sel_rett is not None:
            rl=self.modello.rettangoli
            if 0<=self.sel_rett<len(rl):
                r=rl[self.sel_rett]
                r.x_pct=max(0.0,min(0.99-r.w_pct,r.x_pct+dx/(w*self.zoom)))
                r.y_pct=max(0.0,min(0.99-r.h_pct,r.y_pct+dy/(h*self.zoom)))
                self._pannello_rett.aggiorna_geom_da_modello(); self.refresh()
            return
        if self._drag_mode=="resize_rett" and self.sel_rett is not None:
            rl=self.modello.rettangoli
            if 0<=self.sel_rett<len(rl):
                r=rl[self.sel_rett]
                r.w_pct=max(0.02,min(1.0-r.x_pct,r.w_pct+dx/(w*self.zoom)))
                r.h_pct=max(0.02,min(1.0-r.y_pct,r.h_pct+dy/(h*self.zoom)))
                self._pannello_rett.aggiorna_geom_da_modello(); self.refresh()
            return
        if self._drag_mode=="move_campo" and self.selezionato is not None:
            campo=self.modello.campi[self.selezionato]
            campo.x_pct=max(0.0,min(0.99,campo.x_pct+dx/(w*self.zoom)))
            campo.y_pct=max(0.0,min(0.99,campo.y_pct+dy/(h*self.zoom)))
            self.refresh()

    def _mouse_su(self,e):
        self.drag=None; self._drag_mode=None

    def _pan_giu(self,e): self._pan_last=(e.x,e.y)

    def _pan_muovi(self,e):
        if not hasattr(self,"_pan_last"): return
        dx=self._pan_last[0]-e.x; dy=self._pan_last[1]-e.y
        self._pan_last=(e.x,e.y)
        self.canvas.xview_scroll(dx,"units"); self.canvas.yview_scroll(dy,"units")

    def _rotella(self,e):
        if e.state&0x4:
            if self.selezionato is None: return
            campo=self.modello.campi[self.selezionato]
            campo.dimensione=max(1,campo.dimensione+(1 if e.delta>0 else -1))
            self.spin_dim.delete(0,tk.END)
            self.spin_dim.insert(0,str(campo.dimensione))
            self._aggiorna_lbl_font_mm(campo.dimensione)
        else:
            self.zoom=(min(self.zoom*1.1,8.0) if e.delta>0 else max(self.zoom/1.1,0.05))
        self.refresh()

    # ══════════════════════════════════════════
    # FILE
    # ══════════════════════════════════════════
    def _salva_modello(self):
        p=filedialog.asksaveasfilename(
            defaultextension=".json",initialdir=MODELS_DIR,
            filetypes=[("Modello QSL","*.json")])
        if not p: return
        self.modello.salva(p)
        
        # Salva anche come modello default nel config.ini
        self._imposta_modello_default(p)
        
        messagebox.showinfo("Modello salvato",
                            f"File: {p}\nCampi: {len(self.modello.campi)}"
                            f"\nAree: {len(self.modello.rettangoli)}\n\n"
                            f"✅ Impostato come modello default")

    def _carica_modello(self):
        """[P9] Carica modello JSON e prepara lo sfondo con verifica dimensioni."""
        p=filedialog.askopenfilename(
            initialdir=MODELS_DIR,filetypes=[("Modello QSL","*.json")])
        if not p: return
        try:
            modello=ModelloQSL.carica(p)
        except Exception as e:
            messagebox.showerror("Errore caricamento modello",str(e)); return

        self.modello=modello
        self.selezionato=None; self.sel_rett=None
        self._pannello_rett.seleziona_esternamente(None)
        self._pannello_rett.aggiorna_lista_pubblica()   # [P8]

        # Imposta il modello caricato come default
        self._imposta_modello_default(p)

        # Carica e prepara lo sfondo (con dialog ridimensionamento se necessario)
        if self.modello.bg_path and os.path.exists(self.modello.bg_path):
            ok=self._carica_e_prepara_sfondo(self.modello.bg_path)
            if not ok:
                # Utente ha annullato → carica comunque l'immagine originale senza resize
                try:
                    self.bg=Image.open(self.modello.bg_path).convert("RGBA")
                except Exception as e:
                    messagebox.showerror("Errore sfondo",f"Impossibile caricare {self.modello.bg_path}: {e}")
                    self.bg=None
        else:
            self.bg=None
            if self.modello.bg_path:
                messagebox.showwarning(
                    "Sfondo non trovato",
                    f"Il file sfondo del modello non esiste:\n{self.modello.bg_path}\n\n"
                    f"Carica manualmente uno sfondo con File → Carica Sfondo…")

        self._primo_carico=True
        self._aggiorna_lbl_info()
        self.refresh()
        if self.modello.campi:
            self.lista_campi.selection_set(0)
            self._seleziona_dalla_lista()
        if self.bg: self._zoom_adatta()

    def _imposta_modello_default(self, percorso_completo: str):
        """Imposta il modello specificato come default nel config.ini"""
        try:
            config = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
            
            # Assicura che la sezione DEFAULTS esista
            if "DEFAULTS" not in config:
                config["DEFAULTS"] = {}
            
            # Salva il percorso completo del modello
            config["DEFAULTS"]["modello_json"] = percorso_completo
            
            # Salva il config
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                config.write(f)
                f.flush()
                os.fsync(f.fileno())
            
            print(f"[INFO] Modello default impostato: {percorso_completo}")
            
        except Exception as e:
            print(f"[ERRORE] Impossibile impostare modello default: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare il modello come default:\n{e}")

    # ══════════════════════════════════════════
    # GENERA  [P4]
    # ══════════════════════════════════════════
    def _genera_una(self):
        record=self._record_corrente()
        if not record:
            messagebox.showwarning("Attenzione","Nessun record selezionato."); return
        if not self.modello.bg_path or not os.path.exists(self.modello.bg_path):
            messagebox.showwarning("Attenzione","Nessuno sfondo caricato."); return

        dlg=DialogoEsportazione(self.root,palette=self._p_)
        if not dlg.confermato: return
        target_w,target_h=dlg.dimensioni
        dpi=dlg.dpi
        self._export_w=target_w; self._export_h=target_h; self._export_dpi=dpi
        self._aggiorna_lbl_info()

        nominativo=record.get("call","SCONOSCIUTO")
        file_out=os.path.join(OUTPUT_DIR,f"{nominativo}_{target_w}x{target_h}.jpg")

        try:
            # [P4] Passa self.bg (già ridimensionato in memoria) a genera_qsl
            genera_qsl(self.modello,record,file_out,
                       target_w=target_w,target_h=target_h,dpi=dpi,
                       bg_img=self.bg)
            n_aree=sum(1 for r in self.modello.rettangoli if r.attivo)
            messagebox.showinfo(
                "QSL Generata",
                f"File: {file_out}\n\n"
                f"Dimensioni: {target_w}×{target_h} px  @{dpi} DPI\n"
                f"Standard:   {QSL_MM_W}×{QSL_MM_H} mm\n"
                f"Aree disegnate: {n_aree}")
        except Exception as err:
            messagebox.showerror("Errore",str(err))


# ══════════════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    root = tk.Tk()
    AppQSLEditor(root)
    root.mainloop()
