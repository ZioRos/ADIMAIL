"""
Gestione Record QSL — IZ8GCH  v4.3
====================================
v4.1: gestione duplicati (CALL + Data + Ora)
v4.2: gestione eliminazione file QSL dal disco
v4.3: integrazione completa con qsl_editor2_tema
      - Importa DialogoEsportazione e DialogoDimensioniSfondo dall'editor
      - rigenera_qsl_da_modello passa bg_img + target_w/h/dpi a genera_qsl
      - _carica_modello verifica dimensioni sfondo e offre ridimensionamento
      - _esegui_rigenerazione apre dialog DPI prima di ogni generazione
      - _rigenera_tutti_da_modello: sfondo precaricato una volta per il batch,
        dialog DPI prima del loop
      - Rispetto esatto delle regole del modello JSON (posizioni %, font px,
        rettangoli d'area) con la stessa scala PIL usata dall'editor
"""

import os
import re
import sys
import time
import sqlite3
import smtplib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from collections import defaultdict
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk

# ── Import dall'editor v9 ─────────────────────────────────────────────────────
try:
    from qsl_editor2_tema import (
        # Classi modello
        CampoTesto, ModelloQSL,
        # Generazione immagine
        genera_qsl, formatta_data, formatta_ora, _cerca_font,
        # Costanti percorsi
        MODELS_DIR, OUTPUT_DIR, CAMPI_DB,
        # Dimensioni QSL
        mm_to_px, dimensioni_qsl, ridimensiona_sfondo, _sfondo_ottimale,
        QSL_DPI_PRINT, QSL_MM_W, QSL_MM_H,
        # Dialog condivisi
        DialogoEsportazione, DialogoDimensioniSfondo,
    )
    # QSL_TARGET_W/H sono tuple-unpacking nel modulo, le ricalcoliamo
    QSL_TARGET_W, QSL_TARGET_H = 900, 600
    EDITOR_DISPONIBILE = True
except ImportError as _err:
    EDITOR_DISPONIBILE = False
    MODELS_DIR   = "qsl_models"
    OUTPUT_DIR   = "qsl_output"
    QSL_DPI_PRINT = 300
    QSL_MM_W, QSL_MM_H = 148, 105
    QSL_TARGET_W, QSL_TARGET_H = 900, 600
    print(f"[ATTENZIONE] qsl_editor2_tema.py non trovato: {_err}")

try:
    import qrcode
    QRCODE_DISPONIBILE = True
except ImportError:
    QRCODE_DISPONIBILE = False

DB_FILE     = "qsl_records.db"
CONFIG_FILE = "config.ini"

# ── Costanti modalità legacy ──────────────────────────────────────────────────
BASE_FONT_SIZE  = 10
CALL_FONT_SIZE  = 14
QR_POSITION_PERCENT = (0.83, 0.03)
QR_SIZE_PERCENT     = 0.12
TEXT_AREAS_PERCENT  = {
    "CALL": (0.63, 0.33, 0.97, 0.22),
    "NAME": (0.63, 0.38, 0.97, 0.31),
    "DATE": (0.63, 0.42, 0.97, 0.43),
    "TIME": (0.63, 0.45, 0.97, 0.52),
    "MODE": (0.63, 0.48, 0.97, 0.61),
    "BAND": (0.63, 0.51, 0.97, 0.70),
    "RST":  (0.63, 0.54, 0.97, 0.79),
}
QR_URL = "https://iz8gch.jimdofree.com/"

_TUPLA_KEYS = ["id", "call", "qso_date", "time_on", "mode", "band",
               "rst_sent", "email", "qsl_file", "sent", "name", "qth", "grid"]

# ══════════════════════════════════════════════════════════════════════════════
# PALETTE TEMI
# ══════════════════════════════════════════════════════════════════════════════
TEMI = {
    "scuro": {
        "bg": "#1e2530", "bg_alt": "#252d3a", "fg": "#d0dce8", "fg_dim": "#6a7f96",
        "barra_off": "#0d1f2d", "barra_on": "#0d2d1a", "barra_fg": "#c8dce8",
        "barra_btn_bg": "#1a4a72", "filtri_bg": "#1a2230", "filtri_fg": "#8aaac4",
        "entry_bg": "#151e28", "entry_fg": "#d0dce8", "entry_select_bg": "#2e5080",
        "tree_bg": "#1a2230", "tree_fg": "#c8dce8",
        "tree_heading_bg": "#0d1f2d", "tree_heading_fg": "#4a9eca",
        "tree_inviato_bg": "#0d2d1a", "tree_inviato_fg": "#5dbb7a",
        "tree_pending_bg": "#2d2200", "tree_pending_fg": "#c8a040",
        "status_fg": "#4a7090", "lf_fg": "#4a9eca", "accent": "#4a9eca",
        "danger": "#e05555", "warning_bg": "#2d1a00", "warning_fg": "#e09050",
        "warn_bg": "#3a2800", "warn_fg": "#f0a030",
        "ttk_theme": "clam",
    },
    "chiaro": {
        "bg": "#f0f4f8", "bg_alt": "#ffffff", "fg": "#1a2a3a", "fg_dim": "#6a7f96",
        "barra_off": "#1a3a5c", "barra_on": "#1a5c2a", "barra_fg": "#ffffff",
        "barra_btn_bg": "#2e6da4", "filtri_bg": "#dde8f4", "filtri_fg": "#1a3a5c",
        "entry_bg": "#ffffff", "entry_fg": "#1a2a3a", "entry_select_bg": "#b0ccee",
        "tree_bg": "#ffffff", "tree_fg": "#1a2a3a",
        "tree_heading_bg": "#dde8f4", "tree_heading_fg": "#1a3a5c",
        "tree_inviato_bg": "#d4edda", "tree_inviato_fg": "#155724",
        "tree_pending_bg": "#fff3cd", "tree_pending_fg": "#856404",
        "status_fg": "#5a7090", "lf_fg": "#1a3a5c", "accent": "#1a3a5c",
        "danger": "#c0392b", "warning_bg": "#fff3cd", "warning_fg": "#856404",
        "warn_bg": "#fff3cd", "warn_fg": "#856404",
        "ttk_theme": "clam",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÀ FILE QSL
# ══════════════════════════════════════════════════════════════════════════════

def _dimensione_leggibile(n_bytes: int) -> str:
    if n_bytes < 1024:            return f"{n_bytes} B"
    elif n_bytes < 1024 ** 2:     return f"{n_bytes/1024:.1f} KB"
    else:                          return f"{n_bytes/1024**2:.2f} MB"

def _elimina_file_fisico(path: str) -> tuple:
    if not path or not os.path.isfile(path): return False, 0
    try:
        size = os.path.getsize(path); os.remove(path); return True, size
    except Exception: return False, 0

def _dimensione_file(path: str) -> int:
    try: return os.path.getsize(path) if path and os.path.isfile(path) else 0
    except Exception: return 0


# ══════════════════════════════════════════════════════════════════════════════
# PREPARAZIONE SFONDO  [v4.3]
# ══════════════════════════════════════════════════════════════════════════════

def _carica_e_ridimensiona_sfondo(parent_win, bg_path: str,
                                   target_w: int, target_h: int,
                                   dpi: int, palette: dict) -> Image.Image | None:
    """
    Apre il file sfondo, verifica le dimensioni e mostra il dialog
    DialogoDimensioniSfondo se necessario.

    Ritorna:
        Image.Image  già ridimensionata se l'utente ha accettato/continuato
        None         se l'utente ha annullato o il file non esiste
    """
    if not bg_path or not os.path.exists(bg_path):
        messagebox.showerror("Sfondo mancante",
                             f"File sfondo non trovato:\n{bg_path}",
                             parent=parent_win)
        return None
    try:
        img = Image.open(bg_path)
    except Exception as e:
        messagebox.showerror("Errore apertura sfondo", str(e), parent=parent_win)
        return None

    if not EDITOR_DISPONIBILE:
        # Senza editor, ridimensiona silenziosamente
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)
        return img

    w, h = img.size
    if not _sfondo_ottimale(img, target_w, target_h):
        dlg = DialogoDimensioniSfondo(
            parent_win, w, h, target_w, target_h, dpi, palette=palette)
        azione = dlg.azione
        if azione == DialogoDimensioniSfondo.ANNULLA:
            return None
        elif azione == DialogoDimensioniSfondo.RIDIMENSIONA:
            img = ridimensiona_sfondo(img, target_w, target_h)
        # CONTINUA: usa img as-is

    return img


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG ELIMINA CON FILE
# ══════════════════════════════════════════════════════════════════════════════
class DialogoEliminaConFile(tk.Toplevel):
    def __init__(self, parent, records: list, palette=None):
        super().__init__(parent)
        self.title("Conferma eliminazione")
        self.resizable(False, False); self.transient(parent); self.grab_set()
        p = palette or TEMI["chiaro"]; self.configure(bg=p["bg"])
        self._elimina_record = False; self._elimina_file = False
        self._var_file = tk.BooleanVar(value=False)
        n = len(records); multi = n > 1
        calls = [r[1] for r in records if r[1]]
        files = [r[2] for r in records if r[2] and os.path.isfile(r[2])]
        tot_bytes = sum(_dimensione_file(r[2]) for r in records)
        hdr = tk.Frame(self, bg=p.get("warning_bg", p["bg_alt"])); hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⚠", font=("Arial",18),
                 bg=p.get("warning_bg",p["bg_alt"]),
                 fg=p.get("warning_fg",p["fg"])).pack(side=tk.LEFT,padx=12,pady=8)
        tk.Label(hdr,
                 text=f"Eliminare {n} record?" if multi
                      else f"Eliminare il record di {calls[0] if calls else '???'}?",
                 font=("Arial",11,"bold"),
                 bg=p.get("warning_bg",p["bg_alt"]),
                 fg=p.get("warning_fg",p["fg"])).pack(side=tk.LEFT,padx=4,pady=8)
        body = tk.Frame(self, bg=p["bg"]); body.pack(fill=tk.X,padx=16,pady=(10,4))
        if multi:
            anteprima = ", ".join(calls[:6])
            if len(calls)>6: anteprima += f" … +{len(calls)-6}"
            tk.Label(body,text=f"Nominativi: {anteprima}",bg=p["bg"],fg=p["fg"],
                     font=("Arial",9),wraplength=380,justify=tk.LEFT).pack(anchor=tk.W,pady=2)
        else:
            tk.Label(body,text=f"Nominativo: {records[0][1] or '???'}",
                     bg=p["bg"],fg=p["fg"],font=("Arial",9)).pack(anchor=tk.W)
        ttk.Separator(body,orient="horizontal").pack(fill=tk.X,pady=6)
        if files:
            ff = tk.Frame(body,bg=p["bg"]); ff.pack(fill=tk.X,pady=(0,4))
            tk.Label(ff,text=f"File PNG associat{'i' if multi else 'o'}:",
                     bg=p["bg"],fg=p["fg_dim"],font=("Arial",8,"bold")).pack(anchor=tk.W)
            if not multi and records[0][2]:
                sp = records[0][2] if len(records[0][2])<=52 else "…"+records[0][2][-51:]
                tk.Label(ff,text=f"  {sp}",bg=p["bg"],fg=p["fg"],
                         font=("Courier",8)).pack(anchor=tk.W)
            size_txt = _dimensione_leggibile(tot_bytes)
            tk.Label(ff,text=f"  {len(files)} file/s  ·  {size_txt} su disco",
                     bg=p["bg"],fg=p["accent"],font=("Arial",8,"bold")
                     ).pack(anchor=tk.W,pady=(2,4))
            tk.Checkbutton(ff,
                           text=f"🗑  Elimina anche il{'i' if multi else ''} file PNG dal disco  ({size_txt})",
                           variable=self._var_file,bg=p["bg"],fg=p["fg"],
                           selectcolor=p["bg_alt"],activebackground=p["bg"],
                           activeforeground=p.get("danger","#e05555"),
                           font=("Arial",9,"bold"),cursor="hand2").pack(anchor=tk.W,pady=2)
        else:
            tk.Label(body,text="ℹ  Nessun file PNG presente su disco.",
                     bg=p["bg"],fg=p["fg_dim"],font=("Arial",8,"italic")).pack(anchor=tk.W,pady=4)
        bf = tk.Frame(self,bg=p["bg"]); bf.pack(fill=tk.X,padx=16,pady=(6,14))
        tk.Button(bf,text="Annulla",command=self._annulla,
                  bg=p["bg_alt"],fg=p["fg"],activebackground=p["accent"],activeforeground="#fff",
                  relief=tk.FLAT,padx=14,pady=5,cursor="hand2").pack(side=tk.RIGHT,padx=4)
        tk.Button(bf,text="✔  Elimina record",command=self._conferma,
                  bg=p.get("danger","#c0392b"),fg="#ffffff",
                  activebackground="#a93226",activeforeground="#fff",
                  relief=tk.FLAT,padx=14,pady=5,cursor="hand2",
                  font=("Arial",9,"bold")).pack(side=tk.RIGHT,padx=4)
        self.update_idletasks()
        px=parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py=parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}"); self.wait_window(self)

    def _conferma(self):
        self._elimina_record=True; self._elimina_file=self._var_file.get(); self.destroy()
    def _annulla(self):
        self._elimina_record=False; self._elimina_file=False; self.destroy()
    @property
    def risultato(self): return self._elimina_record, self._elimina_file


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG PULIZIA FILE
# ══════════════════════════════════════════════════════════════════════════════
class DialogoPuliziaFile(tk.Toplevel):
    def __init__(self, parent, db_files: set, output_dir: str, palette=None):
        super().__init__(parent)
        self.title("Pulizia File QSL su Disco")
        self.geometry("560x480"); self.resizable(False,False)
        self.transient(parent); self.grab_set()
        p = palette or TEMI["chiaro"]; self.configure(bg=p["bg"])
        self._p=p; self._output_dir=output_dir; self._db_files=db_files; self._azione=None
        self._files_su_disco=self._scansiona_disco()
        self._orfani=self._files_su_disco-self._db_files
        self._referenziati=self._files_su_disco&self._db_files
        self._build_ui()
        self.update_idletasks()
        px=parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py=parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}"); self.wait_window(self)

    def _scansiona_disco(self) -> set:
        if not os.path.isdir(self._output_dir): return set()
        return {os.path.abspath(os.path.join(self._output_dir,f))
                for f in os.listdir(self._output_dir) if f.lower().endswith(".jpg")}

    @staticmethod
    def _somma_bytes(paths: set) -> int:
        tot=0
        for p in paths:
            try: tot+=os.path.getsize(p)
            except Exception: pass
        return tot

    def _build_ui(self):
        p=self._p
        hdr=tk.Frame(self,bg=p["barra_off"]); hdr.pack(fill=tk.X)
        tk.Label(hdr,text="🧹  Pulizia File QSL su Disco",bg=p["barra_off"],fg=p["barra_fg"],
                 font=("Arial",11,"bold")).pack(side=tk.LEFT,padx=12,pady=8)
        body=tk.Frame(self,bg=p["bg"]); body.pack(fill=tk.BOTH,expand=True,padx=16,pady=10)
        sf=tk.LabelFrame(body,text="Statistiche cartella output",bg=p["bg"],fg=p["lf_fg"],
                          font=("Arial",9,"bold")); sf.pack(fill=tk.X,pady=(0,10))
        bd=self._somma_bytes(self._files_su_disco)
        bo=self._somma_bytes(self._orfani); br=self._somma_bytes(self._referenziati)
        for label,valore in [
            ("📁 Cartella output:", self._output_dir if os.path.isdir(self._output_dir) else "non trovata"),
            ("📄 File JPG su disco:", f"{len(self._files_su_disco)}  ({_dimensione_leggibile(bd)})"),
            ("🔗 Referenziati nel DB:", f"{len(self._referenziati)}  ({_dimensione_leggibile(br)})"),
            ("👻 Orfani (non nel DB):", f"{len(self._orfani)}  ({_dimensione_leggibile(bo)})"),
        ]:
            r=tk.Frame(sf,bg=p["bg"]); r.pack(fill=tk.X,padx=8,pady=2)
            tk.Label(r,text=label,bg=p["bg"],fg=p["fg_dim"],font=("Arial",8),
                     width=26,anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(r,text=valore,bg=p["bg"],fg=p["fg"],font=("Courier",8),
                     anchor=tk.W,wraplength=280).pack(side=tk.LEFT,padx=4)
        fa=tk.LabelFrame(body,text="Opzione A — Elimina solo file orfani",bg=p["bg"],
                          fg=p["lf_fg"],font=("Arial",9,"bold")); fa.pack(fill=tk.X,pady=(0,8))
        tk.Label(fa,text=f"File presenti su disco ma NON referenziati nel database.\n"
                          f"  Trovati: {len(self._orfani)} file orfani ({_dimensione_leggibile(bo)})",
                 bg=p["bg"],fg=p["fg"],font=("Arial",9),justify=tk.LEFT
                 ).pack(anchor=tk.W,padx=10,pady=4)
        tk.Button(fa,text=f"🗑  Elimina {len(self._orfani)} file orfani  ({_dimensione_leggibile(bo)})",
                  command=self._elimina_orfani,bg=p["barra_btn_bg"],fg=p["barra_fg"],
                  activebackground=p["accent"],activeforeground="#fff",relief=tk.FLAT,
                  padx=10,pady=4,font=("Arial",9),cursor="hand2",
                  state=tk.NORMAL if self._orfani else tk.DISABLED
                  ).pack(anchor=tk.W,padx=10,pady=(0,8))
        fb=tk.LabelFrame(body,text="Opzione B — Elimina TUTTI i file referenziati nel DB",
                          bg=p["bg"],fg=p.get("danger","#c0392b"),
                          font=("Arial",9,"bold")); fb.pack(fill=tk.X,pady=(0,8))
        tk.Label(fb,text=f"⚠  Elimina dal disco TUTTI i file PNG associati a record nel DB.\n"
                          f"   I record nel database NON vengono eliminati.\n"
                          f"  File: {len(self._referenziati)}  ({_dimensione_leggibile(br)})",
                 bg=p["bg"],fg=p.get("warning_fg",p["fg"]),font=("Arial",9),justify=tk.LEFT
                 ).pack(anchor=tk.W,padx=10,pady=4)
        tk.Button(fb,text=f"⚠  Elimina {len(self._referenziati)} file referenziati  ({_dimensione_leggibile(br)})",
                  command=self._elimina_referenziati,bg=p.get("danger","#c0392b"),fg="#ffffff",
                  activebackground="#a93226",activeforeground="#fff",relief=tk.FLAT,
                  padx=10,pady=4,font=("Arial",9,"bold"),cursor="hand2",
                  state=tk.NORMAL if self._referenziati else tk.DISABLED
                  ).pack(anchor=tk.W,padx=10,pady=(0,8))
        bf=tk.Frame(self,bg=p["bg"]); bf.pack(fill=tk.X,padx=16,pady=(0,12))
        tk.Button(bf,text="Chiudi",command=self.destroy,bg=p["bg_alt"],fg=p["fg"],
                  activebackground=p["accent"],activeforeground="#fff",
                  relief=tk.FLAT,padx=14,pady=5,cursor="hand2").pack(side=tk.RIGHT)

    def _elimina_orfani(self):
        if not self._orfani:
            messagebox.showinfo("Pulizia","Nessun file orfano trovato.",parent=self); return
        n=len(self._orfani); ts=_dimensione_leggibile(self._somma_bytes(self._orfani))
        if not messagebox.askyesno("Conferma",f"Eliminare {n} file orfani?\nSpazio: {ts}",parent=self): return
        ok=0; errori=[]; bl=0
        for path in list(self._orfani):
            s,sz=_elimina_file_fisico(path)
            if s: ok+=1; bl+=sz
            else: errori.append(os.path.basename(path))
        msg=f"✅ Eliminati {ok} file orfani.\nSpazio liberato: {_dimensione_leggibile(bl)}"
        if errori: msg+=f"\n❌ Errori ({len(errori)}): "+", ".join(errori[:5])
        messagebox.showinfo("Pulizia completata",msg,parent=self)
        self._azione="orfani"; self.destroy()

    def _elimina_referenziati(self):
        if not self._referenziati:
            messagebox.showinfo("Pulizia","Nessun file referenziato trovato.",parent=self); return
        n=len(self._referenziati); ts=_dimensione_leggibile(self._somma_bytes(self._referenziati))
        if not messagebox.askyesno("⚠ Conferma",
                                    f"Eliminare {n} file PNG?\nSpazio: {ts}\n\n"
                                    f"I record nel DB NON vengono eliminati.",parent=self): return
        if not messagebox.askyesno("⚠ Ultima conferma",
                                    "Confermi eliminazione di TUTTI i file PNG?",parent=self): return
        ok=0; errori=[]; bl=0
        conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
        for path in list(self._referenziati):
            s,sz=_elimina_file_fisico(path)
            if s:
                ok+=1; bl+=sz
                cur.execute("UPDATE qsl_records SET qsl_file=NULL WHERE qsl_file=?",(path,))
            else: errori.append(os.path.basename(path))
        conn.commit(); conn.close()
        msg=(f"✅ Eliminati {ok} file PNG.\nSpazio liberato: {_dimensione_leggibile(bl)}\n"
             f"Il campo qsl_file dei record è stato azzerato.")
        if errori: msg+=f"\n❌ Errori ({len(errori)}): "+", ".join(errori[:5])
        messagebox.showinfo("Pulizia completata",msg,parent=self)
        self._azione="tutti"; self.destroy()

    @property
    def azione_eseguita(self): return self._azione


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAZIONE
# ══════════════════════════════════════════════════════════════════════════════
def _carica_config():
    config=configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        messagebox.showerror("Errore",f"File '{CONFIG_FILE}' non trovato!")
        return None,None,"scuro"
    config.read(CONFIG_FILE)
    try:
        smtp={"server":config["SMTP"]["Server"],"port":int(config["SMTP"]["Port"]),
              "user":config["SMTP"]["User"],"password":config["SMTP"]["Password"]}
    except KeyError as e:
        messagebox.showerror("Errore",f"Chiave SMTP mancante nel config.ini: {e}")
        return None,None,"scuro"
    hamqth=None
    if "HAMQTH" in config:
        try: hamqth={"user":config["HAMQTH"]["User"],"password":config["HAMQTH"]["Password"]}
        except KeyError: pass
    tema="scuro"
    if "UI" in config:
        tema=config["UI"].get("tema","scuro").lower()
        if tema not in TEMI: tema="scuro"
    return smtp,hamqth,tema

def _salva_tema_config(tema:str):
    config=configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE): config.read(CONFIG_FILE)
    if "UI" not in config: config["UI"]={}
    config["UI"]["tema"]=tema
    try:
        with open(CONFIG_FILE,"w") as f: config.write(f)
    except Exception: pass

SMTP_CONF,HAMQTH_CONF,TEMA_INIZIALE=_carica_config()
if SMTP_CONF is None: sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÀ RECORD
# ══════════════════════════════════════════════════════════════════════════════
def _tupla_in_dict(record_tupla:tuple) -> dict:
    return dict(zip(_TUPLA_KEYS,record_tupla))


# ══════════════════════════════════════════════════════════════════════════════
# CLIENT HAMQTH
# ══════════════════════════════════════════════════════════════════════════════
class ClientHamQTH:
    BASE_URL="https://www.hamqth.com/xml.php"
    APP_NAME="QSLManager_IZ8GCH"
    def __init__(self,username,password):
        self.username=username; self.password=password
        self.session_id=None; self.session_time=0
    def _fetch_xml(self,url):
        try:
            with urllib.request.urlopen(url,timeout=10) as resp: data=resp.read()
            return ET.fromstring(data)
        except Exception as e: raise ConnectionError(f"Errore di rete: {e}")
    def login(self):
        url=(f"{self.BASE_URL}?u={urllib.parse.quote(self.username)}"
             f"&p={urllib.parse.quote(self.password)}")
        root=self._fetch_xml(url); ns={"h":"https://www.hamqth.com"}
        err=root.find(".//h:e",ns)
        if err is not None: raise ValueError(f"Login HamQTH fallito: {err.text}")
        sid=root.find(".//h:session_id",ns)
        if sid is None: raise ValueError("Session ID non ricevuto.")
        self.session_id=sid.text; self.session_time=time.time()
    def _assicura_sessione(self):
        if self.session_id is None or (time.time()-self.session_time)>3300: self.login()
    def cerca_nominativo(self,callsign:str):
        self._assicura_sessione()
        url=(f"{self.BASE_URL}?id={self.session_id}"
             f"&callsign={urllib.parse.quote(callsign.upper())}&prg={self.APP_NAME}")
        root=self._fetch_xml(url); ns={"h":"https://www.hamqth.com"}
        err=root.find(".//h:e",ns)
        if err is not None:
            msg=(err.text or "").lower()
            if "expired" in msg or "does not exist" in msg:
                self.login(); return self.cerca_nominativo(callsign)
            elif "not found" in msg: return None
            raise ValueError(f"Errore HamQTH: {err.text}")
        search=root.find(".//h:search",ns)
        if search is None: return None
        campi=["callsign","nick","qth","country","adif","itu","cq","grid","adr_name",
               "adr_street1","adr_city","adr_zip","adr_country","email","lotw","eqsl",
               "qsl","qsldirect","latitude","longitude","continent","utc_offset",
               "picture","iota","qsl_via"]
        return {c:search.find(f"h:{c}",ns).text.strip() for c in campi
                if search.find(f"h:{c}",ns) is not None and search.find(f"h:{c}",ns).text}

hamqth_client=None
if HAMQTH_CONF:
    hamqth_client=ClientHamQTH(HAMQTH_CONF["user"],HAMQTH_CONF["password"])


# ══════════════════════════════════════════════════════════════════════════════
# MODALITÀ LEGACY (senza editor)
# ══════════════════════════════════════════════════════════════════════════════
def _trova_font_legacy():
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p): return p
    return None
_LEGACY_FONT=_trova_font_legacy()

def _font_legacy(size):
    if _LEGACY_FONT: return ImageFont.truetype(_LEGACY_FONT,size)
    return ImageFont.load_default()

def _pct_px(box,w,h):
    return (int(box[0]*w),int(box[1]*h),int(box[2]*w),int(box[3]*h))

def _disegna_centrato(draw,text,box,font):
    bbox=draw.textbbox((0,0),text,font=font)
    tw=bbox[2]-bbox[0]; th=bbox[3]-bbox[1]
    x=box[0]+(box[2]-box[0]-tw)//2; y=box[1]+(box[3]-box[1]-th)//2
    draw.text((x,y),text,fill="black",font=font)

def _gen_qr(data,img_width):
    if not QRCODE_DISPONIBILE: return None
    qr=qrcode.QRCode(box_size=3,border=2)
    qr.add_data(data); qr.make(fit=True)
    img_qr=qr.make_image(fill_color="black",back_color="white").convert("RGB")
    return img_qr.resize((int(img_width*QR_SIZE_PERCENT),)*2)

def _fmt_data(d):
    if d and len(d)==8: return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return d or ""

def _fmt_ora(t):
    if t and len(t)>=4: return f"{t[0:2]}:{t[2:4]}"
    return t or ""

def rigenera_qsl_legacy(template_path,record,suffisso="sfondo"):
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template non trovato: {template_path}")
    r=_tupla_in_dict(record)
    call=r.get("call",""); qso_date=r.get("qso_date",""); time_on=r.get("time_on","")
    mode=r.get("mode",""); band=r.get("band",""); rst=r.get("rst_sent",""); name=r.get("name","")
    img=Image.open(template_path).convert("RGB")
    draw=ImageDraw.Draw(img); w,h=img.size
    data_map={"CALL":call,"NAME":name,"DATE":_fmt_data(qso_date),
              "TIME":_fmt_ora(time_on),"MODE":mode,"BAND":band,"RST":rst}
    for key,value in data_map.items():
        if key in TEXT_AREAS_PERCENT and value:
            box=_pct_px(TEXT_AREAS_PERCENT[key],w,h)
            font=_font_legacy(CALL_FONT_SIZE if key=="CALL" else BASE_FONT_SIZE)
            _disegna_centrato(draw,value,box,font)
    qr_img=_gen_qr(QR_URL,w)
    if qr_img:
        img.paste(qr_img,(int(QR_POSITION_PERCENT[0]*w),int(QR_POSITION_PERCENT[1]*h)))
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    safe_call=re.sub(r'[\\/:*?"<>|]','_',call)
    ts=time.strftime("%Y%m%d_%H%M%S")
    out_path=os.path.join(OUTPUT_DIR,f"{safe_call}_{_fmt_data(qso_date)}_{suffisso}_{ts}.jpg")
    img.save(out_path,dpi=(300,300),format="JPEG",quality=95); return out_path


# ══════════════════════════════════════════════════════════════════════════════
# RIGENERAZIONE DA MODELLO JSON  [v4.3 — passa bg_img + dpi]
# ══════════════════════════════════════════════════════════════════════════════
def rigenera_qsl_da_modello(modello_path, record_tupla,
                             modello_fallback=None,
                             bg_img: Image.Image = None,
                             target_w: int = None,
                             target_h: int = None,
                             dpi: int = None):
    """
    Rigenera la QSL usando le regole del modello JSON.

    v4.3:
        bg_img   — immagine PIL già aperta e ridimensionata (priorità sul disco).
                   Se None, genera_qsl riapre il file e ridimensiona da sola.
        target_w / target_h — dimensioni output in px.
        dpi      — DPI del file PNG salvato.

    Il modello viene sempre riletto dal disco (per avere la versione aggiornata).
    """
    if not EDITOR_DISPONIBILE:
        raise RuntimeError("qsl_editor2_tema.py non disponibile.")

    if modello_path and os.path.exists(modello_path):
        modello = ModelloQSL.carica(modello_path)
    elif modello_fallback is not None:
        modello = modello_fallback
    else:
        raise FileNotFoundError(f"Modello JSON non trovato: {modello_path}")

    rec_dict  = _tupla_in_dict(record_tupla)
    call      = rec_dict.get("call","SCONOSCIUTO")
    qso_date  = rec_dict.get("qso_date","")
    safe_call = re.sub(r'[\\/:*?"<>|]','_',call)
    ts        = time.strftime("%Y%m%d_%H%M%S")

    # Usa dimensioni target se specificate, altrimenti default da editor
    tw  = target_w or 900
    th  = target_h or 600
    dpi = dpi      or QSL_DPI_PRINT

    filename = f"{safe_call}_{_fmt_data(qso_date)}_modello_{ts}.jpg"
    out_path = os.path.join(OUTPUT_DIR,filename)

    # [v4.3] Passa bg_img (già ridimensionato) per evitare riapertura da disco
    genera_qsl(modello, rec_dict, out_path,
               target_w=tw, target_h=th, dpi=dpi,
               bg_img=bg_img)
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL
# ══════════════════════════════════════════════════════════════════════════════
def _data_per_email(raw_date:str) -> str:
    d=raw_date.replace("-","")
    if len(d)==8 and d.isdigit(): return f"{d[6:8]}/{d[4:6]}/{d[0:4]}"
    return raw_date

def _e_italiano(call:str) -> bool:
    return call.upper().startswith("I")

def _componi_testo_email(call:str,data_fmt:str):
    if _e_italiano(call):
        return (f"QSL Card per {call} - {data_fmt}",
                f"Caro/a {call},\n\nTi invio la QSL per il collegamento del {data_fmt}.\n\n"
                f"Cordiali saluti e 73 de IZ8GCH GL.\n\nSpero di rivederti sulla mia frequenza!")
    return (f"QSL Card for {call} - {data_fmt}",
            f"Dear {call},\n\nI'm sending you the QSL card for our contact on {data_fmt}.\n\n"
            f"All the best. 73 de IZ8GCH GL.\n\nHope to meet you again on the air!")


class DialogoEmail(tk.Toplevel):
    def __init__(self,parent,oggetto_default,testo_default,
                 destinatario="",titolo="Componi Email",palette=None):
        super().__init__(parent)
        self.title(titolo); self.resizable(True,True)
        self.geometry("620x520"); self.minsize(500,420)
        self.transient(parent); self.grab_set()
        p=palette or TEMI["chiaro"]; self.configure(bg=p["bg"])
        self._oggetto=None; self._testo=None
        if destinatario:
            hdr=tk.Frame(self,bg=p["bg"]); hdr.pack(fill=tk.X,padx=10,pady=(10,0))
            tk.Label(hdr,text="A:",bg=p["bg"],fg=p["fg_dim"]).pack(side=tk.LEFT)
            tk.Label(hdr,text=destinatario,bg=p["bg"],fg=p["accent"],
                     font=("",9,"bold")).pack(side=tk.LEFT,padx=6)
        frm_ogg=tk.Frame(self,bg=p["bg"]); frm_ogg.pack(fill=tk.X,padx=10,pady=(8,0))
        tk.Label(frm_ogg,text="Oggetto:",bg=p["bg"],fg=p["fg"]).pack(side=tk.LEFT)
        self.var_oggetto=tk.StringVar(value=oggetto_default)
        tk.Entry(frm_ogg,textvariable=self.var_oggetto,width=55,
                 bg=p["entry_bg"],fg=p["entry_fg"],insertbackground=p["fg"],
                 selectbackground=p["entry_select_bg"],relief=tk.FLAT,bd=2
                 ).pack(side=tk.LEFT,padx=6,fill=tk.X,expand=True)
        frm_btn=tk.Frame(self,bg=p["bg"]); frm_btn.pack(side=tk.BOTTOM,fill=tk.X,padx=10,pady=8)
        for txt,cmd,side in [("✖ Annulla",self._annulla,tk.RIGHT),
                              ("📧 Invia",self._conferma,tk.RIGHT),
                              ("🔄 Ripristina",lambda:self._ripristina(testo_default,oggetto_default),tk.LEFT)]:
            tk.Button(frm_btn,text=txt,command=cmd,bg=p["barra_btn_bg"],fg=p["barra_fg"],
                      activebackground=p["accent"],activeforeground="#ffffff",
                      relief=tk.FLAT,padx=10,pady=3,cursor="hand2").pack(side=side,padx=4)
        tk.Label(self,text="ℹ  Puoi usare {CALL} e {DATE} come segnaposto.",
                 bg=p["bg"],fg=p["fg_dim"],font=("",8)).pack(side=tk.BOTTOM,anchor=tk.W,padx=10,pady=(0,2))
        tk.Label(self,text="Messaggio:",bg=p["bg"],fg=p["fg"]).pack(anchor=tk.W,padx=10,pady=(8,0))
        frm_txt=tk.Frame(self,bg=p["bg"]); frm_txt.pack(fill=tk.BOTH,expand=True,padx=10,pady=(4,0))
        self.txt_corpo=tk.Text(frm_txt,wrap=tk.WORD,undo=True,font=("Consolas",10),
                                bg=p["entry_bg"],fg=p["entry_fg"],insertbackground=p["fg"],
                                selectbackground=p["entry_select_bg"],relief=tk.FLAT,bd=2)
        sb=tk.Scrollbar(frm_txt,command=self.txt_corpo.yview,bg=p["bg"],troughcolor=p["bg_alt"])
        self.txt_corpo.configure(yscrollcommand=sb.set)
        self.txt_corpo.pack(side=tk.LEFT,fill=tk.BOTH,expand=True); sb.pack(side=tk.RIGHT,fill=tk.Y)
        self.txt_corpo.insert("1.0",testo_default)
        self.update_idletasks()
        px=parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py=parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}"); self.wait_window(self)
    def _conferma(self):
        self._oggetto=self.var_oggetto.get().strip()
        self._testo=self.txt_corpo.get("1.0",tk.END).rstrip(); self.destroy()
    def _annulla(self): self._oggetto=None; self._testo=None; self.destroy()
    def _ripristina(self,testo_orig,oggetto_orig):
        self.var_oggetto.set(oggetto_orig)
        self.txt_corpo.delete("1.0",tk.END); self.txt_corpo.insert("1.0",testo_orig)
    @property
    def risultato(self): return self._oggetto,self._testo


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG DUPLICATI
# ══════════════════════════════════════════════════════════════════════════════
class DialogoDuplicati(tk.Toplevel):
    def __init__(self,parent,gruppi:list,records_map:dict,on_elimina_cb,palette=None):
        super().__init__(parent)
        self.title("Gestione Duplicati"); self.geometry("960x560")
        self.minsize(700,420); self.resizable(True,True)
        self.transient(parent); self.grab_set()
        p=palette or TEMI["chiaro"]; self.configure(bg=p["bg"])
        self._gruppi=list(gruppi); self._records_map=records_map
        self._on_elimina_cb=on_elimina_cb; self._p=p; self._idx=0
        self._da_conservare={i:gruppi[i][0] for i in range(len(gruppi))}
        self._build_ui(); self._mostra_gruppo(0)
        self.update_idletasks()
        px=parent.winfo_rootx()+(parent.winfo_width() -self.winfo_width()) //2
        py=parent.winfo_rooty()+(parent.winfo_height()-self.winfo_height())//2
        self.geometry(f"+{px}+{py}"); self.wait_window(self)

    def _build_ui(self):
        p=self._p; n=len(self._gruppi)
        hdr=tk.Frame(self,bg=p["barra_off"]); hdr.pack(fill=tk.X)
        self._lbl_hdr=tk.Label(hdr,
            text=f"Duplicati trovati: {n} gruppi  |  Criterio: CALL + Data QSO + Ora QSO",
            bg=p["barra_off"],fg=p["barra_fg"],font=("Arial",10,"bold"))
        self._lbl_hdr.pack(side=tk.LEFT,padx=12,pady=6)
        nav=tk.Frame(self,bg=p["bg"]); nav.pack(fill=tk.X,padx=10,pady=(6,0))
        tk.Button(nav,text="◀ Precedente",command=self._prev,bg=p["barra_btn_bg"],fg=p["barra_fg"],
                  activebackground=p["accent"],relief=tk.FLAT,cursor="hand2").pack(side=tk.LEFT,padx=4)
        self._lbl_nav=tk.Label(nav,text="",bg=p["bg"],fg=p["fg"],font=("Arial",9))
        self._lbl_nav.pack(side=tk.LEFT,padx=10)
        tk.Button(nav,text="Successivo ▶",command=self._next,bg=p["barra_btn_bg"],fg=p["barra_fg"],
                  activebackground=p["accent"],relief=tk.FLAT,cursor="hand2").pack(side=tk.LEFT,padx=4)
        tk.Label(self,text="🟢 Verde = da CONSERVARE  |  🟡 Giallo = da ELIMINARE  "
                            "— Clicca una riga per scegliere quale conservare.",
                 bg=p["bg"],fg=p["fg_dim"],font=("Arial",8,"italic")).pack(anchor=tk.W,padx=12,pady=(4,0))
        cols=("id","call","data","ora","mode","band","rst","nome","qth","email","qsl_file","sent")
        hdrs={"id":"ID","call":"CALL","data":"Data","ora":"Ora","mode":"Mode","band":"Band",
              "rst":"RST","nome":"Nome","qth":"QTH","email":"Email","qsl_file":"QSL File","sent":"Inv."}
        widths={"id":45,"call":85,"data":82,"ora":58,"mode":50,"band":55,"rst":45,
                "nome":110,"qth":90,"email":150,"qsl_file":150,"sent":42}
        frm_tree=tk.Frame(self,bg=p["bg"]); frm_tree.pack(fill=tk.BOTH,expand=True,padx=10,pady=6)
        style=ttk.Style()
        style.configure("Dup.Treeview",background=p["tree_bg"],foreground=p["tree_fg"],
                         fieldbackground=p["tree_bg"],rowheight=26)
        style.configure("Dup.Treeview.Heading",background=p["tree_heading_bg"],
                         foreground=p["tree_heading_fg"],font=("Arial",8,"bold"))
        style.map("Dup.Treeview",background=[("selected",p["entry_select_bg"])],
                  foreground=[("selected",p["fg"])])
        self._tree=ttk.Treeview(frm_tree,columns=cols,show="headings",
                                 style="Dup.Treeview",selectmode="browse")
        for col in cols:
            self._tree.heading(col,text=hdrs[col])
            self._tree.column(col,width=widths[col],minwidth=30,anchor="w",
                               stretch=(col in ("email","qsl_file")))
        self._tree.tag_configure("conserva",background=p["tree_inviato_bg"],foreground=p["tree_inviato_fg"])
        self._tree.tag_configure("elimina", background=p["tree_pending_bg"], foreground=p["tree_pending_fg"])
        sb_y=ttk.Scrollbar(frm_tree,orient=tk.VERTICAL,  command=self._tree.yview)
        sb_x=ttk.Scrollbar(frm_tree,orient=tk.HORIZONTAL,command=self._tree.xview)
        self._tree.configure(yscrollcommand=sb_y.set,xscrollcommand=sb_x.set)
        self._tree.grid(row=0,column=0,sticky="nsew"); sb_y.grid(row=0,column=1,sticky="ns")
        sb_x.grid(row=1,column=0,sticky="ew")
        frm_tree.rowconfigure(0,weight=1); frm_tree.columnconfigure(0,weight=1)
        self._tree.bind("<<TreeviewSelect>>",self._on_tree_select)
        frm_btn=tk.Frame(self,bg=p["bg"]); frm_btn.pack(fill=tk.X,padx=10,pady=(0,10))
        tk.Button(frm_btn,text="✅  Conserva selezionato — elimina gli altri",
                  command=self._applica_gruppo,bg=p["barra_btn_bg"],fg=p["barra_fg"],
                  activebackground=p["accent"],relief=tk.FLAT,font=("Arial",9,"bold"),
                  padx=10,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=4)
        tk.Button(frm_btn,text="⏭ Salta",command=self._next,bg=p["bg_alt"],fg=p["fg"],
                  activebackground=p["accent"],relief=tk.FLAT,font=("Arial",9),
                  padx=8,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=4)
        tk.Button(frm_btn,text="✖ Chiudi",command=self.destroy,bg=p["bg_alt"],fg=p["fg"],
                  activebackground=p["accent"],relief=tk.FLAT,font=("Arial",9),
                  padx=8,pady=4,cursor="hand2").pack(side=tk.RIGHT,padx=4)
        self._lbl_stato=tk.Label(frm_btn,text="",bg=p["bg"],fg=p["fg_dim"],font=("Arial",8))
        self._lbl_stato.pack(side=tk.LEFT,padx=12)

    def _mostra_gruppo(self,idx:int):
        if idx<0 or idx>=len(self._gruppi): return
        self._idx=idx; n=len(self._gruppi)
        self._lbl_nav.configure(text=f"Gruppo {idx+1} di {n}")
        gruppo=self._gruppi[idx]; da_conservare=self._da_conservare.get(idx,gruppo[0])
        self._tree.delete(*self._tree.get_children())
        for rec_id in gruppo:
            r=self._records_map[rec_id]
            tag="conserva" if rec_id==da_conservare else "elimina"
            vals=(r[0],r[1] or "",r[2] or "",r[3] or "",r[4] or "",r[5] or "",
                  r[6] or "",r[10] or "",r[11] or "",r[7] or "",
                  os.path.basename(r[8]) if r[8] else "","✅" if r[9] else "")
            self._tree.insert("",tk.END,iid=str(rec_id),values=vals,tags=(tag,))
        self._tree.selection_set(str(da_conservare)); self._tree.focus(str(da_conservare))

    def _on_tree_select(self,_event):
        sel=self._tree.selection()
        if not sel: return
        rec_id=int(sel[0]); self._da_conservare[self._idx]=rec_id
        for r_id in self._gruppi[self._idx]:
            self._tree.item(str(r_id),tags=("conserva" if r_id==rec_id else "elimina",))

    def _prev(self): self._mostra_gruppo(self._idx-1)
    def _next(self):
        if self._idx<len(self._gruppi)-1: self._mostra_gruppo(self._idx+1)
        else: self.destroy()

    def _applica_gruppo(self):
        idx=self._idx; gruppo=self._gruppi[idx]
        conserva=self._da_conservare.get(idx,gruppo[0])
        da_eliminare=[r_id for r_id in gruppo if r_id!=conserva]
        if not da_eliminare:
            self._lbl_stato.configure(text="Nessun duplicato da eliminare."); return
        call=self._records_map[conserva][1] or "???"
        data=_fmt_data(self._records_map[conserva][2])
        ora =_fmt_ora(self._records_map[conserva][3])
        if not messagebox.askyesno("Conferma eliminazione",
                                    f"Gruppo: {call}  {data}  {ora}\n\n"
                                    f"Conservare ID {conserva}.\nEliminare: {da_eliminare}"): return
        self._on_elimina_cb(da_eliminare)
        self._lbl_stato.configure(text=f"✅ Eliminati {len(da_eliminare)} duplicati per {call}.")
        self._gruppi.pop(idx)
        self._da_conservare={i:self._gruppi[i][0] for i in range(len(self._gruppi))}
        if not self._gruppi:
            messagebox.showinfo("Completato","Tutti i gruppi di duplicati sono stati gestiti.")
            self.destroy(); return
        new_idx=min(idx,len(self._gruppi)-1)
        self._lbl_hdr.configure(
            text=f"Duplicati trovati: {len(self._gruppi)} gruppi rimanenti  |  "
                 f"Criterio: CALL + Data QSO + Ora QSO")
        self._mostra_gruppo(new_idx)


# ══════════════════════════════════════════════════════════════════════════════
# APPLICAZIONE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
class GestoreQSL:

    def __init__(self,root:tk.Tk):
        self.root=root
        self.root.title("Gestione Record QSL — IZ8GCH  v4.3")
        self.root.geometry("1450x780"); self.root.minsize(1200,620)

        self.records          = []
        self.filtered_records = []
        self.selected_id      = None
        self.sort_col         = None
        self.sort_reverse     = False
        self.preview_window   = None
        self.modello_attivo   = None
        self.modello_path     = ""
        
        # Carica modello JSON default dal config (dopo aver inizializzato _p)
        self._tema_nome = TEMA_INIZIALE
        self._p         = TEMI[self._tema_nome]
        
        # [v4.3] Dimensioni export correnti (sincronizzate con DialogoEsportazione)
        self._export_w   = 900
        self._export_h   = 600
        self._export_dpi = QSL_DPI_PRINT
        
        os.makedirs(MODELS_DIR,exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self._applica_tema_ttk()
        self._costruisci_menu()
        self._costruisci_ui()  # Qui vengono create barra_modello e stato_modello_var
        self._carica_records()
        self._autocarica_modello()
        self._applica_colori_tk()
        
        # Carica modello JSON default dal config (dopo aver costruito l'UI)
        self._carica_modello_default()
        
        # [v4.3] Sfondo del modello già aperto e ridimensionato
        self._bg_modello: Image.Image = None
        
        # Se c'è un modello default, aggiorna la barra
        if self.modello_attivo:
            self._aggiorna_barra_modello()
            self._aggiorna_lbl_export()

    # ══════════════════════════════════════════
    # TEMA
    # ══════════════════════════════════════════
    def _applica_tema_ttk(self):
        p=self._p; style=ttk.Style(self.root); style.theme_use(p["ttk_theme"])
        style.configure(".",background=p["bg"],foreground=p["fg"],
                        fieldbackground=p["entry_bg"],troughcolor=p["bg_alt"],
                        selectbackground=p["entry_select_bg"],selectforeground=p["fg"])
        style.configure("TFrame",background=p["bg"])
        style.configure("TLabel",background=p["bg"],foreground=p["fg"])
        style.configure("TLabelframe",background=p["bg"],foreground=p["lf_fg"])
        style.configure("TLabelframe.Label",background=p["bg"],foreground=p["lf_fg"],
                        font=("Arial",9,"bold"))
        style.configure("TEntry",fieldbackground=p["entry_bg"],foreground=p["entry_fg"],
                        insertcolor=p["fg"])
        style.configure("TButton",background=p["barra_btn_bg"],foreground=p["barra_fg"],
                        padding=[6,3])
        style.map("TButton",background=[("active",p["accent"])],
                  foreground=[("active","#ffffff")])
        style.configure("TScrollbar",background=p["bg_alt"],troughcolor=p["bg"],
                        arrowcolor=p["fg_dim"])
        style.configure("Treeview",background=p["tree_bg"],foreground=p["tree_fg"],
                        fieldbackground=p["tree_bg"],rowheight=22)
        style.configure("Treeview.Heading",background=p["tree_heading_bg"],
                        foreground=p["tree_heading_fg"],font=("Arial",9,"bold"))
        style.map("Treeview",background=[("selected",p["entry_select_bg"])],
                  foreground=[("selected",p["fg"])])
        style.map("Treeview.Heading",background=[("active",p["accent"])],
                  foreground=[("active","#ffffff")])
        style.configure("TCheckbutton",background=p["filtri_bg"],foreground=p["filtri_fg"])
        style.map("TCheckbutton",background=[("active",p["filtri_bg"])],
                  foreground=[("active",p["accent"])])
        style.configure("TProgressbar",background=p["accent"],troughcolor=p["bg_alt"])
        self.root.configure(bg=p["bg"])

    def _applica_colori_tk(self):
        p=self._p
        colore_barra=p["barra_on"] if self.modello_attivo else p["barra_off"]
        self.barra_modello.configure(bg=colore_barra)
        for w in self.barra_modello.winfo_children():
            if isinstance(w,tk.Label): w.configure(bg=colore_barra,fg=p["barra_fg"])
            elif isinstance(w,tk.Button): w.configure(bg=p["barra_btn_bg"],fg=p["barra_fg"],
                                                       activebackground=p["accent"])
        self.filtri_frame.configure(bg=p["filtri_bg"])
        for w in self.filtri_frame.winfo_children():
            if isinstance(w,tk.Label): w.configure(bg=p["filtri_bg"],fg=p["filtri_fg"])
            elif isinstance(w,tk.Button): w.configure(bg=p["barra_btn_bg"],fg=p["barra_fg"],
                                                       activebackground=p["accent"])
            elif isinstance(w,tk.Checkbutton): w.configure(bg=p["filtri_bg"],fg=p["filtri_fg"],
                selectcolor=p["bg_alt"],activebackground=p["filtri_bg"],activeforeground=p["accent"])
        self.tree.tag_configure("inviato",
            background=p["tree_inviato_bg"],foreground=p["tree_inviato_fg"])
        self.tree.tag_configure("non_inviato",
            background=p["tree_pending_bg"],foreground=p["tree_pending_fg"])
        self.lbl_status.configure(fg=p["status_fg"],bg=p["bg"])

    def _cambia_tema(self,nome:str):
        if nome==self._tema_nome: return
        self._tema_nome=nome; self._p=TEMI[nome]
        _salva_tema_config(nome)
        self._applica_tema_ttk(); self._applica_colori_tk()
        self._aggiorna_barra_modello(); self._var_tema.set(nome)

    # ══════════════════════════════════════════
    # AUTO-CARICAMENTO MODELLO
    # ══════════════════════════════════════════
    def _autocarica_modello(self):
        if not EDITOR_DISPONIBILE or not os.path.isdir(MODELS_DIR): return
        modelli=[f for f in os.listdir(MODELS_DIR) if f.endswith(".json")]
        if len(modelli)==1:
            try:
                path=os.path.join(MODELS_DIR,modelli[0])
                self.modello_attivo=ModelloQSL.carica(path)
                self.modello_path=path
                # [v4.3] carica e prepara lo sfondo silenziosamente
                self._prepara_sfondo_modello(silent=True)
                self._aggiorna_barra_modello()
            except Exception: pass

    # ══════════════════════════════════════════
    # MENU
    # ══════════════════════════════════════════
    def _costruisci_menu(self):
        p=self._p
        barra=tk.Menu(self.root,bg=p["barra_off"],fg=p["barra_fg"],
                      activebackground=p["accent"],activeforeground="#ffffff",relief=tk.FLAT)
        self.root.config(menu=barra)
        def sub():
            return tk.Menu(barra,tearoff=0,bg=p["bg_alt"],fg=p["fg"],
                           activebackground=p["accent"],activeforeground="#ffffff",
                           relief=tk.FLAT,bd=1,font=("Arial",9))
        mf=sub(); barra.add_cascade(label="File",menu=mf)
        mf.add_command(label="Aggiorna record",command=self._carica_records)
        mf.add_separator(); mf.add_command(label="Esci",command=self.root.quit)
        mv=sub(); barra.add_cascade(label="Visualizza",menu=mv)
        self._var_tema=tk.StringVar(value=self._tema_nome)
        mv.add_radiobutton(label="🌙  Tema scuro",variable=self._var_tema,value="scuro",
                           command=lambda: self._cambia_tema("scuro"))
        mv.add_radiobutton(label="☀  Tema chiaro",variable=self._var_tema,value="chiaro",
                           command=lambda: self._cambia_tema("chiaro"))
        mm=sub(); barra.add_cascade(label="Modello QSL",menu=mm)
        mm.add_command(label="📂 Carica modello JSON…",command=self._carica_modello)
        mm.add_command(label="🖊 Apri QSL Editor",     command=self._apri_editor)
        mm.add_separator()
        mm.add_command(label="📐 Imposta dimensioni export…",
                       command=self._imposta_dimensioni_export)
        mm.add_separator()
        mm.add_command(label="ℹ Informazioni modello",  command=self._info_modello)
        mm.add_command(label="✖ Rimuovi modello (legacy)",command=self._rimuovi_modello)
        me=sub(); barra.add_cascade(label="Email",menu=me)
        me.add_command(label="Invia email al record selezionato",command=self._invia_email_click)
        me.add_command(label="Invia email a tutti i non inviati", command=self._invia_tutti_pending)
        mq=sub(); barra.add_cascade(label="QSL",menu=mq)
        mq.add_command(label="📁 Seleziona file PNG esistente",  command=self._seleziona_file_qsl)
        mq.add_command(label="🎨 Rigenera con nuovo sfondo",     command=self._scegli_sfondo_e_rigenera)
        mq.add_command(label="⚡ Rigenera da modello",           command=self._rigenera_da_modello_bg)
        mq.add_separator()
        mq.add_command(label="⚡⚡ Rigenera TUTTI dal modello",   command=self._rigenera_tutti_da_modello)
        mq.add_separator()
        mq.add_command(label="🖼 Anteprima immagine QSL",        command=self._mostra_anteprima)
        mq.add_separator()
        mq.add_command(label="🗑  Elimina file PNG dal disco (record selezionato)",
                       command=self._elimina_file_qsl_selezionato)
        mh=sub(); barra.add_cascade(label="HamQTH",menu=mh)
        mh.add_command(label="🔎 Cerca dati callsign",           command=self._cerca_hamqth)
        mh.add_command(label="🔄 Aggiorna tutti i record vuoti", command=self._aggiorna_tutti_hamqth)
        mh.add_command(label="ℹ Stato sessione",                 command=self._stato_sessione_hamqth)
        md=sub(); barra.add_cascade(label="Elimina",menu=md)
        md.add_command(label="🗑 Elimina record selezionato",
                       command=self._elimina_selezionato,accelerator="Canc")
        md.add_command(label="🗑 Elimina record selezionati (multi)",
                       command=self._elimina_multipli)
        md.add_separator()
        md.add_command(label="⚠ Elimina TUTTI i record…",command=self._elimina_tutti)
        mdisco=sub(); barra.add_cascade(label="🗑 Disco",menu=mdisco)
        mdisco.add_command(label="🗑  Elimina file PNG del record selezionato",
                           command=self._elimina_file_qsl_selezionato)
        mdisco.add_separator()
        mdisco.add_command(label="🧹  Pulizia file QSL (orfani e batch)…",
                           command=self._pulizia_file_qsl)
        mdisco.add_separator()
        mdisco.add_command(label="📊  Statistiche spazio cartella output",
                           command=self._statistiche_spazio)
        mdup=sub(); barra.add_cascade(label="Duplicati",menu=mdup)
        mdup.add_command(label="🔍 Gestione manuale duplicati…",command=self._gestisci_duplicati)
        mdup.add_command(label="⚡ Elimina automaticamente (tieni il più completo)",
                         command=self._elimina_duplicati_auto)
        mdup.add_separator()
        mdup.add_command(label="ℹ  Criterio: CALL + Data QSO + Ora QSO",state="disabled")
        mhelp=sub(); barra.add_cascade(label="?",menu=mhelp)
        mhelp.add_command(label="Informazioni",command=self._info_app)

    # ══════════════════════════════════════════
    # UI PRINCIPALE
    # ══════════════════════════════════════════
    def _costruisci_ui(self):
        p=self._p
        self.barra_modello=tk.Frame(self.root,bg=p["barra_off"],height=28)
        self.barra_modello.pack(fill=tk.X)
        self.stato_modello_var=tk.StringVar(value="⚠ Nessun modello JSON caricato — modalità legacy attiva")
        tk.Label(self.barra_modello,textvariable=self.stato_modello_var,
                 bg=p["barra_off"],fg=p["barra_fg"],font=("Arial",9)
                 ).pack(side=tk.LEFT,padx=10,pady=4)
        tk.Button(self.barra_modello,text="📂 Carica modello…",command=self._carica_modello,
                  bg=p["barra_btn_bg"],fg=p["barra_fg"],activebackground=p["accent"],
                  relief=tk.FLAT,font=("Arial",9)).pack(side=tk.LEFT,padx=4)
        tk.Button(self.barra_modello,text="🖊 Apri Editor",command=self._apri_editor,
                  bg=p["barra_btn_bg"],fg=p["barra_fg"],activebackground=p["accent"],
                  relief=tk.FLAT,font=("Arial",9)).pack(side=tk.LEFT,padx=4)
        # [v4.3] Label info dimensioni export
        self._lbl_export=tk.Label(self.barra_modello,text="",bg=p["barra_off"],
                                   fg=p["barra_fg"],font=("Arial",8))
        self._lbl_export.pack(side=tk.RIGHT,padx=10)

        outer=ttk.Frame(self.root); outer.pack(fill=tk.BOTH,expand=True,padx=6,pady=6)
        paned=ttk.PanedWindow(outer,orient=tk.HORIZONTAL); paned.pack(fill=tk.BOTH,expand=True)

        # ── Pannello sinistro ──────────────────────────────────────
        frame_sx=ttk.LabelFrame(paned,text="Record QSL"); paned.add(frame_sx,weight=3)
        cerca_frame=ttk.Frame(frame_sx); cerca_frame.pack(fill=tk.X,padx=5,pady=(5,2))
        ttk.Label(cerca_frame,text="🔍").pack(side=tk.LEFT)
        self.search_var=tk.StringVar(); self.search_var.trace("w",self._on_search)
        ttk.Entry(cerca_frame,textvariable=self.search_var).pack(side=tk.LEFT,padx=4,fill=tk.X,expand=True)
        ttk.Button(cerca_frame,text="✕",width=3,command=self._pulisci_ricerca).pack(side=tk.LEFT)
        self.filtri_frame=tk.Frame(frame_sx,bg=p["filtri_bg"],relief=tk.GROOVE,bd=1)
        self.filtri_frame.pack(fill=tk.X,padx=5,pady=(0,3))
        tk.Label(self.filtri_frame,text="Filtri:",bg=p["filtri_bg"],fg=p["filtri_fg"],
                 font=("Arial",8,"bold")).pack(side=tk.LEFT,padx=(6,4),pady=3)
        self.filtro_solo_email=tk.BooleanVar(value=False)
        self.filtro_solo_pending=tk.BooleanVar(value=False)
        for txt,var in [("📧 Solo con email",self.filtro_solo_email),
                        ("⏳ Solo non inviati",self.filtro_solo_pending)]:
            tk.Checkbutton(self.filtri_frame,text=txt,variable=var,
                           command=self._applica_filtro,bg=p["filtri_bg"],fg=p["filtri_fg"],
                           selectcolor=p["bg_alt"],activebackground=p["filtri_bg"],
                           activeforeground=p["accent"],font=("Arial",8)).pack(side=tk.LEFT,padx=4)
        tree_frame=ttk.Frame(frame_sx); tree_frame.pack(fill=tk.BOTH,expand=True,padx=5,pady=4)
        colonne=("call","data","nome","qth","email","stato")
        etichette={"call":"CALL","data":"Data QSO","nome":"Nome","qth":"QTH","email":"Email","stato":"Stato"}
        larghezze={"call":100,"data":90,"nome":120,"qth":120,"email":180,"stato":100}
        self.tree=ttk.Treeview(tree_frame,columns=colonne,show="headings",selectmode="extended")
        for col in colonne:
            self.tree.heading(col,text=etichette[col],command=lambda c=col: self._ordina_per_col(c))
            self.tree.column(col,width=larghezze[col],minwidth=60,anchor="w",stretch=True)
        self.tree.tag_configure("inviato",background=p["tree_inviato_bg"],foreground=p["tree_inviato_fg"])
        self.tree.tag_configure("non_inviato",background=p["tree_pending_bg"],foreground=p["tree_pending_fg"])
        sb_y=ttk.Scrollbar(tree_frame,orient=tk.VERTICAL,  command=self.tree.yview)
        sb_x=ttk.Scrollbar(tree_frame,orient=tk.HORIZONTAL,command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set,xscrollcommand=sb_x.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); sb_y.grid(row=0,column=1,sticky="ns")
        sb_x.grid(row=1,column=0,sticky="ew")
        tree_frame.rowconfigure(0,weight=1); tree_frame.columnconfigure(0,weight=1)
        self.tree.bind("<<TreeviewSelect>>",self._on_select)
        self.tree.bind("<Delete>",lambda e: self._elimina_selezionato())
        barra_sx=ttk.Frame(frame_sx); barra_sx.pack(fill=tk.X,padx=5,pady=(0,4))
        self.status_var=tk.StringVar(value="")
        self.lbl_status=tk.Label(barra_sx,textvariable=self.status_var,
                                  fg=p["status_fg"],bg=p["bg"],font=("Arial",8))
        self.lbl_status.pack(side=tk.LEFT,fill=tk.X,expand=True)
        ttk.Button(barra_sx,text="🗑 Elimina sel.",command=self._elimina_multipli).pack(side=tk.RIGHT)

        # ── Pannello destro ────────────────────────────────────────
        frame_dx=ttk.Frame(paned); paned.add(frame_dx,weight=1)
        det=ttk.LabelFrame(frame_dx,text="Dettagli Record"); det.pack(fill=tk.X,padx=4,pady=(0,4))
        label_list=["CALL","Data QSO","Ora QSO","Modalità","Banda","RST",
                    "Email","Sent","QSL File","Nome","QTH","Grid"]
        self.entries={}
        for i,lbl in enumerate(label_list):
            ttk.Label(det,text=lbl+":").grid(row=i,column=0,sticky=tk.W,padx=(8,2),pady=2)
            e=ttk.Entry(det,width=32); e.grid(row=i,column=1,sticky="ew",padx=(2,8),pady=2)
            if lbl in ("Sent","Nome","QTH","Grid"): e.configure(state="readonly")
            self.entries[lbl]=e
        det.columnconfigure(1,weight=1)
        btn_frame=ttk.LabelFrame(frame_dx,text="Azioni"); btn_frame.pack(fill=tk.X,padx=4,pady=(0,4))
        riga1=ttk.Frame(btn_frame); riga1.pack(fill=tk.X,padx=4,pady=(4,2))
        for txt,cmd in [("💾 Salva",self._salva_modifiche),("📧 Email",self._invia_email_click),
                        ("🔎 HamQTH",self._cerca_hamqth),("🗑 Elimina",self._elimina_selezionato)]:
            b=ttk.Button(riga1,text=txt,command=cmd,width=11); b.pack(side=tk.LEFT,padx=2)
            if txt=="🔎 HamQTH":
                self.btn_hamqth=b
                if not hamqth_client: b.configure(state="disabled")
        riga2=ttk.Frame(btn_frame); riga2.pack(fill=tk.X,padx=4,pady=(2,2))
        for txt,cmd in [("📁 PNG",self._seleziona_file_qsl),
                        ("🎨 Nuovo sfondo",self._scegli_sfondo_e_rigenera),
                        ("⚡ Da modello",self._rigenera_da_modello_bg),
                        ("🖼 Anteprima",self._mostra_anteprima)]:
            ttk.Button(riga2,text=txt,command=cmd,width=14).pack(side=tk.LEFT,padx=2)
        riga3=ttk.Frame(btn_frame); riga3.pack(fill=tk.X,padx=4,pady=(0,6))
        ttk.Button(riga3,text="🗑 Elimina file PNG",
                   command=self._elimina_file_qsl_selezionato,width=18).pack(side=tk.LEFT,padx=2)
        ttk.Button(riga3,text="🧹 Pulizia disco",
                   command=self._pulizia_file_qsl,width=16).pack(side=tk.LEFT,padx=2)
        hq_frame=ttk.LabelFrame(frame_dx,text="Dati da HamQTH"); hq_frame.pack(fill=tk.X,padx=4,pady=(0,4))
        hq_fields=[("Nome","nick"),("QTH","qth"),("Paese","country"),("Grid","grid"),
                   ("CQ Zone","cq"),("ITU Zone","itu"),("LoTW","lotw"),("eQSL","eqsl"),("QSL via","qsl_via")]
        self.hamqth_labels={}
        for i,(label,key) in enumerate(hq_fields):
            ttk.Label(hq_frame,text=label+":",foreground=p["fg_dim"]
                      ).grid(row=i//3,column=(i%3)*2,sticky=tk.W,padx=6,pady=2)
            v=ttk.Label(hq_frame,text="—",width=11)
            v.grid(row=i//3,column=(i%3)*2+1,sticky=tk.W,padx=2,pady=2)
            self.hamqth_labels[key]=v
        prev=ttk.LabelFrame(frame_dx,text="Anteprima QSL")
        prev.pack(fill=tk.BOTH,expand=True,padx=4,pady=(0,4))
        self.thumb_label=ttk.Label(prev,text="Nessuna immagine selezionata",anchor="center")
        self.thumb_label.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)

    def _aggiorna_lbl_export(self):
        """Aggiorna la label info export nella barra del modello."""
        if not hasattr(self,"_lbl_export"): return
        p=self._p
        colore=p["barra_on"] if self.modello_attivo else p["barra_off"]
        if self.modello_attivo:
            txt=(f"📐 {self._export_w}×{self._export_h}px  @{self._export_dpi}DPI  "
                 f"({QSL_MM_W}×{QSL_MM_H}mm)")
        else:
            txt=""
        self._lbl_export.configure(text=txt,bg=colore)

    # ══════════════════════════════════════════
    # GESTIONE MODELLO JSON  [v4.3]
    # ══════════════════════════════════════════
    def _prepara_sfondo_modello(self, silent: bool = False) -> bool:
        """
        Apre lo sfondo del modello attivo, verifica le dimensioni e
        lo ridimensiona se l'utente acconsente.
        Salva il risultato in self._bg_modello.
        silent=True: se le dimensioni sono già ottimali non mostra nulla.
        """
        if not self.modello_attivo or not self.modello_attivo.bg_path:
            self._bg_modello = None; return False

        bg_path = self.modello_attivo.bg_path
        if not os.path.exists(bg_path):
            if not silent:
                messagebox.showwarning("Sfondo non trovato",
                                       f"Il file sfondo non esiste:\n{bg_path}\n\n"
                                       f"Carica uno sfondo alternativo tramite QSL → Rigenera con nuovo sfondo.",
                                       parent=self.root)
            self._bg_modello = None; return False

        try:
            img = Image.open(bg_path)
        except Exception as e:
            if not silent:
                messagebox.showerror("Errore apertura sfondo", str(e), parent=self.root)
            self._bg_modello = None; return False

        if not EDITOR_DISPONIBILE:
            if img.size != (self._export_w, self._export_h):
                img = img.resize((self._export_w, self._export_h), Image.LANCZOS)
            self._bg_modello = img; return True

        w, h = img.size
        if _sfondo_ottimale(img, self._export_w, self._export_h) or silent:
            # In modalità silent ridimensiona senza chiedere
            if img.size != (self._export_w, self._export_h):
                img = img.resize((self._export_w, self._export_h), Image.LANCZOS)
            self._bg_modello = img; return True

        dlg = DialogoDimensioniSfondo(
            self.root, w, h, self._export_w, self._export_h,
            self._export_dpi, palette=self._p)
        azione = dlg.azione
        if azione == DialogoDimensioniSfondo.ANNULLA:
            self._bg_modello = None; return False
        elif azione == DialogoDimensioniSfondo.RIDIMENSIONA:
            img = ridimensiona_sfondo(img, self._export_w, self._export_h)
        # CONTINUA: usa img as-is

        self._bg_modello = img; return True

    def _carica_modello(self):
        if not EDITOR_DISPONIBILE:
            messagebox.showerror("qsl_editor2_tema non trovato",
                                 "Il file qsl_editor2_tema.py non è presente nella stessa cartella.")
            return
        path=filedialog.askopenfilename(
            title="Carica modello QSL",initialdir=MODELS_DIR,
            filetypes=[("Modelli QSL","*.json"),("Tutti","*.*")])
        if not path: return
        try:
            self.modello_attivo=ModelloQSL.carica(path)
            self.modello_path=path
        except Exception as e:
            messagebox.showerror("Errore",f"Impossibile caricare il modello:\n{e}"); return

        # Imposta il modello caricato come default
        self._imposta_modello_default(path)

        # [v4.3] Verifica e prepara lo sfondo subito dopo il caricamento
        sfondo_ok = self._prepara_sfondo_modello(silent=False)

        self._aggiorna_barra_modello()
        self._aggiorna_lbl_export()

        msg = (f"File: {os.path.basename(path)}\n"
               f"Sfondo: {os.path.basename(self.modello_attivo.bg_path)}\n"
               f"Campi testo: {len(self.modello_attivo.campi)}\n"
               f"Aree rettangoli: {len(self.modello_attivo.rettangoli)}\n"
               f"Dimensioni export: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI")
        if not sfondo_ok:
            msg += "\n\n⚠ Sfondo non caricato — usa 'Rigenera con nuovo sfondo' per selezionarne uno."
        msg += "\n\n✅ Impostato come modello default"
        messagebox.showinfo("Modello caricato", msg)

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
            
            print(f"[INFO] Modello default impostato in qsl_records: {percorso_completo}")
            
        except Exception as e:
            print(f"[ERRORE] Impossibile impostare modello default in qsl_records: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare il modello come default:\n{e}")

    def _imposta_dimensioni_export(self):
        """Apre DialogoEsportazione solo per impostare DPI/dimensioni (senza generare)."""
        if not EDITOR_DISPONIBILE:
            messagebox.showwarning("Non disponibile",
                                   "Richiede qsl_editor2_tema.py per usare il dialog."); return
        dlg = DialogoEsportazione(self.root, palette=self._p)
        if dlg.confermato:
            self._export_w, self._export_h = dlg.dimensioni
            self._export_dpi = dlg.dpi
            self._aggiorna_lbl_export()
            # Ricarica lo sfondo con le nuove dimensioni
            if self.modello_attivo:
                self._prepara_sfondo_modello(silent=True)
            messagebox.showinfo(
                "Dimensioni export aggiornate",
                f"Export: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI\n"
                f"Standard: {QSL_MM_W}×{QSL_MM_H}mm\n\n"
                f"Le prossime rigenerazioni useranno queste dimensioni.")

    def _carica_modello_default(self):
        """Carica il modello JSON default dal config.ini se presente"""
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if "DEFAULTS" in config and "modello_json" in config["DEFAULTS"]:
                modello_path = config["DEFAULTS"]["modello_json"]
                if modello_path.strip():
                    # Se è un percorso completo, usalo direttamente
                    if os.path.isabs(modello_path):
                        modello_file = modello_path
                    else:
                        # Altrimenti, cerca nella directory models
                        modello_file = os.path.join(MODELS_DIR, modello_path)
                    
                    if os.path.exists(modello_file):
                        try:
                            self.modello_attivo = ModelloQSL.carica(modello_file)
                            self.modello_path = modello_file
                            # Prepara lo sfondo silenziosamente
                            self._prepara_sfondo_modello(silent=True)
                            print(f"[INFO] Modello default caricato: {modello_file}")
                        except Exception as e:
                            print(f"[ATTENZIONE] Impossibile caricare modello default {modello_file}: {e}")
                    else:
                        print(f"[ATTENZIONE] Modello default non trovato: {modello_file}")
                else:
                    print("[INFO] Nessun modello JSON default configurato")
    
    def _rimuovi_modello(self):
        self.modello_attivo=None; self.modello_path=""; self._bg_modello=None
        self._aggiorna_barra_modello(); self._aggiorna_lbl_export()
        messagebox.showinfo("Modello rimosso","Modalità legacy riattivata.")

    def _aggiorna_barra_modello(self):
        p=self._p
        if self.modello_attivo:
            fname=os.path.basename(self.modello_path)
            n_r=len(self.modello_attivo.rettangoli) if hasattr(self.modello_attivo,"rettangoli") else 0
            self.stato_modello_var.set(
                f"✅ Modello: {fname}  —  {len(self.modello_attivo.campi)} campi  "
                f"|  {n_r} aree  |  Sfondo: {os.path.basename(self.modello_attivo.bg_path)}")
            colore=p["barra_on"]
        else:
            self.stato_modello_var.set("⚠ Nessun modello JSON caricato — modalità legacy attiva")
            colore=p["barra_off"]
        self.barra_modello.configure(bg=colore)
        for w in self.barra_modello.winfo_children():
            if isinstance(w,tk.Label): w.configure(bg=colore,fg=p["barra_fg"])
            elif isinstance(w,tk.Button): w.configure(bg=p["barra_btn_bg"],fg=p["barra_fg"])

    def _info_modello(self):
        if not self.modello_attivo:
            messagebox.showinfo("Modello","Nessun modello caricato."); return
        m=self.modello_attivo
        n_r=len(m.rettangoli) if hasattr(m,"rettangoli") else 0
        info="\n".join(
            f"  • [{c.tipo}] {c.valore}  {c.font_nome} {c.dimensione}px  {c.colore}"
            +("  ⇔adatta" if c.adatta_w else "")
            for c in m.campi)
        sfondo_stato="✅ caricato" if self._bg_modello else "⚠ non caricato"
        messagebox.showinfo("Modello attivo",
                            f"File: {self.modello_path}\nSfondo: {m.bg_path}  [{sfondo_stato}]\n"
                            f"Dimensioni export: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI\n"
                            f"Campi ({len(m.campi)}):\n{info}\n"
                            f"Rettangoli d'area: {n_r}")

    def _apri_editor(self):
        import subprocess
        editor=os.path.join(os.path.dirname(os.path.abspath(__file__)),"qsl_editor2_tema.py")
        if not os.path.exists(editor):
            messagebox.showerror("Editor non trovato",f"qsl_editor2_tema.py non trovato:\n{editor}"); return
        try: subprocess.Popen([sys.executable,editor])
        except Exception as e: messagebox.showerror("Errore avvio editor",str(e))

    # ══════════════════════════════════════════
    # RIGENERAZIONE QSL  [v4.3]
    # ══════════════════════════════════════════

    def _chiedi_opzioni_export(self) -> bool:
        """
        Mostra DialogoEsportazione per scegliere DPI/dimensioni.
        Aggiorna self._export_w/h/dpi e ricarica lo sfondo se le dimensioni cambiano.
        Ritorna True se l'utente ha confermato, False se ha annullato.
        """
        if not EDITOR_DISPONIBILE:
            return True   # senza editor usa dimensioni default
        dlg = DialogoEsportazione(self.root, palette=self._p)
        if not dlg.confermato:
            return False
        vecchie = (self._export_w, self._export_h, self._export_dpi)
        self._export_w, self._export_h = dlg.dimensioni
        self._export_dpi = dlg.dpi
        self._aggiorna_lbl_export()
        # Se le dimensioni sono cambiate, ricarica lo sfondo
        if (self._export_w, self._export_h, self._export_dpi) != vecchie:
            if self.modello_attivo:
                self._prepara_sfondo_modello(silent=True)
        return True

    def _scegli_sfondo_e_rigenera(self):
        if not self.selected_id:
            messagebox.showwarning("Seleziona record","Seleziona prima un record."); return
        record=next((r for r in self.records if r[0]==self.selected_id),None)
        if not record: return
        bg=filedialog.askopenfilename(
            title=f"Seleziona sfondo per {record[1]}",
            filetypes=[("Immagini","*.png *.jpg *.jpeg")])
        if not bg: return
        self._esegui_rigenerazione(record,bg)

    def _rigenera_da_modello_bg(self):
        if not self.selected_id:
            messagebox.showwarning("Seleziona record","Seleziona prima un record."); return
        if not self.modello_attivo:
            messagebox.showwarning("Nessun modello","Carica prima un modello JSON."); return
        record=next((r for r in self.records if r[0]==self.selected_id),None)
        if not record: return
        self._esegui_rigenerazione(record, self.modello_attivo.bg_path)

    def _esegui_rigenerazione(self, record, bg_path: str):
        """
        [v4.3] Mostra dialog DPI, apre e ridimensiona lo sfondo,
        poi genera la QSL passando bg_img a genera_qsl/rigenera_qsl_da_modello.
        """
        # 1. Scegli opzioni export
        if not self._chiedi_opzioni_export(): return

        self.root.configure(cursor="watch"); self.root.update()
        call=record[1] or "???"
        new_path=None; modo=""

        try:
            if self.modello_attivo and EDITOR_DISPONIBILE:
                # [v4.3] Apri e ridimensiona sfondo
                bg_img = _carica_e_ridimensiona_sfondo(
                    self.root, bg_path,
                    self._export_w, self._export_h, self._export_dpi, self._p)
                if bg_img is None:
                    self.root.configure(cursor=""); return

                new_path = rigenera_qsl_da_modello(
                    self.modello_path, record,
                    modello_fallback=self.modello_attivo,
                    bg_img=bg_img,
                    target_w=self._export_w,
                    target_h=self._export_h,
                    dpi=self._export_dpi)
                modo="modello JSON"
            else:
                new_path=rigenera_qsl_legacy(bg_path,record)
                modo="modalità legacy"
        except Exception as e:
            self.root.configure(cursor="")
            messagebox.showerror("Errore rigenerazione",str(e)); return

        self.root.configure(cursor="")
        conn=sqlite3.connect(DB_FILE)
        conn.execute("UPDATE qsl_records SET qsl_file=? WHERE id=?",(new_path,self.selected_id))
        conn.commit(); conn.close()
        self.entries["QSL File"].delete(0,tk.END)
        self.entries["QSL File"].insert(0,new_path)
        self._aggiorna_thumbnail(new_path); self._carica_records()
        messagebox.showinfo("QSL rigenerata",
                            f"QSL per {call} rigenerata ({modo}).\n"
                            f"Dimensioni: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI\n"
                            f"File: {os.path.basename(new_path)}")

    def _rigenera_tutti_da_modello(self):
        """
        [v4.3] Mostra dialog DPI, precarica lo sfondo UNA VOLTA per tutto il batch,
        poi rigenera tutti i record passando bg_img a ogni chiamata (efficiente).
        """
        if not self.modello_attivo:
            messagebox.showwarning("Nessun modello","Carica prima un modello JSON."); return
        totale=len(self.records)
        if totale==0:
            messagebox.showinfo("Vuoto","Il database è vuoto."); return

        # 1. Dialog DPI
        if not self._chiedi_opzioni_export(): return

        # 2. Apri e ridimensiona sfondo (con dialog se necessario)
        bg_img = _carica_e_ridimensiona_sfondo(
            self.root,
            self.modello_attivo.bg_path,
            self._export_w, self._export_h, self._export_dpi, self._p)
        if bg_img is None: return

        # Aggiorna self._bg_modello con la versione già pronta
        self._bg_modello = bg_img

        if not messagebox.askyesno("Rigenera tutti",
                                    f"Rigenerare la QSL per tutti i {totale} record?\n"
                                    f"Dimensioni: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI\n"
                                    f"I file verranno salvati in: {OUTPUT_DIR}"):
            return

        prog=tk.Toplevel(self.root); prog.title("Rigenerazione in corso…")
        prog.geometry("460x160"); prog.resizable(False,False); prog.configure(bg=self._p["bg"])
        ttk.Label(prog,text=f"Rigenerazione QSL da modello  "
                            f"({self._export_w}×{self._export_h}px @{self._export_dpi}DPI)…"
                  ).pack(pady=8)
        pvar=tk.DoubleVar()
        ttk.Progressbar(prog,variable=pvar,maximum=totale).pack(fill=tk.X,padx=20)
        lbl_info=ttk.Label(prog,text=""); lbl_info.pack(pady=4)

        ok=0; errori=[]
        conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
        for i,record in enumerate(self.records):
            call=record[1] or "SCONOSCIUTO"
            try:
                out=rigenera_qsl_da_modello(
                    self.modello_path, record,
                    modello_fallback=self.modello_attivo,
                    bg_img=bg_img,              # sfondo precaricato [v4.3]
                    target_w=self._export_w,
                    target_h=self._export_h,
                    dpi=self._export_dpi)
                cur.execute("UPDATE qsl_records SET qsl_file=? WHERE id=?",(out,record[0]))
                ok+=1
            except Exception as e:
                errori.append(f"{call}: {e}")
            pvar.set(i+1); lbl_info.configure(text=f"{i+1}/{totale}: {call}"); prog.update()

        conn.commit(); conn.close()
        prog.destroy(); self._carica_records()
        risultato=f"✅ Rigenerate: {ok}"
        if errori: risultato+=f"\n❌ Errori: {len(errori)}\n"+"\n".join(errori[:5])
        messagebox.showinfo("Rigenerazione completata",risultato)

    # ══════════════════════════════════════════
    # CARICAMENTO E FILTRAGGIO RECORD
    # ══════════════════════════════════════════
    def _carica_records(self):
        conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
        existenti=[r[1] for r in cur.execute("PRAGMA table_info(qsl_records)")]
        for col,tipo in [("name","TEXT"),("qth","TEXT"),("grid","TEXT")]:
            if col not in existenti:
                cur.execute(f"ALTER TABLE qsl_records ADD COLUMN {col} {tipo}")
        conn.commit()
        cur.execute("SELECT id,call,qso_date,time_on,mode,band,rst_sent,"
                    "email,qsl_file,sent,name,qth,grid FROM qsl_records")
        self.records=cur.fetchall(); conn.close()
        self._applica_filtro()

    def _applica_filtro(self):
        q=self.search_var.get().lower() if hasattr(self,"search_var") else ""
        risultato=list(self.records)
        if q:
            risultato=[r for r in risultato
                       if q in (r[1] or "").lower() or q in (r[2] or "").lower()
                       or q in (r[7] or "").lower() or q in (r[10] or "").lower()
                       or q in (r[11] or "").lower()]
        if hasattr(self,"filtro_solo_email") and self.filtro_solo_email.get():
            risultato=[r for r in risultato if r[7] and r[7].strip()]
        if hasattr(self,"filtro_solo_pending") and self.filtro_solo_pending.get():
            risultato=[r for r in risultato if not r[9]]
        self.filtered_records=risultato
        if self.sort_col: self._applica_ordinamento()
        else: self._aggiorna_tree()

    def _aggiorna_tree(self):
        self.tree.delete(*self.tree.get_children())
        for rec in self.filtered_records:
            stato="✅ Inviato" if rec[9] else "⏳ Non inviato"
            tag="inviato" if rec[9] else "non_inviato"
            self.tree.insert("",tk.END,iid=str(rec[0]),
                              values=(rec[1],rec[2],rec[10] or "",rec[11] or "",rec[7] or "",stato),
                              tags=(tag,))
        totale=len(self.records); mostrati=len(self.filtered_records)
        inviati=sum(1 for r in self.records if r[9])
        self.status_var.set(f"Mostrati: {mostrati} / Totale: {totale} | "
                            f"Inviati: {inviati} | Non inviati: {totale-inviati}  "
                            "— Ctrl/Shift+Click per selezione multipla")
        self._svuota_campi()

    # ══════════════════════════════════════════
    # RICERCA E ORDINAMENTO
    # ══════════════════════════════════════════
    def _on_search(self,*args): self._applica_filtro()
    def _pulisci_ricerca(self): self.search_var.set("")

    def _ordina_per_col(self,col):
        if self.sort_col==col: self.sort_reverse=not self.sort_reverse
        else: self.sort_col=col; self.sort_reverse=False
        self._applica_ordinamento()

    def _applica_ordinamento(self):
        idx_map={"call":1,"data":2,"nome":10,"qth":11,"email":7,"stato":9}
        idx=idx_map[self.sort_col]
        self.filtered_records.sort(key=lambda r:(r[idx] or ""),reverse=self.sort_reverse)
        etichette={"call":"CALL","data":"Data QSO","nome":"Nome","qth":"QTH","email":"Email","stato":"Stato"}
        for col,lbl in etichette.items():
            freccia=(" ▲" if not self.sort_reverse else " ▼") if col==self.sort_col else ""
            self.tree.heading(col,text=lbl+freccia)
        self._aggiorna_tree()

    # ══════════════════════════════════════════
    # SELEZIONE RECORD
    # ══════════════════════════════════════════
    def _on_select(self,event):
        sel=self.tree.selection()
        if not sel: return
        if len(sel)>1:
            self.status_var.set(f"{len(sel)} record selezionati — premi 🗑 per rimuoverli"); return
        rec_id=int(sel[0])
        record=next((r for r in self.records if r[0]==rec_id),None)
        if not record: return
        self.selected_id=rec_id
        mappa={"CALL":record[1] or "","Data QSO":record[2] or "","Ora QSO":record[3] or "",
               "Modalità":record[4] or "","Banda":record[5] or "","RST":record[6] or "",
               "Email":record[7] or "","QSL File":record[8] or "",
               "Sent":"1" if record[9] else "0",
               "Nome":record[10] or "","QTH":record[11] or "","Grid":record[12] or ""}
        for key,entry in self.entries.items():
            entry.configure(state="normal"); entry.delete(0,tk.END); entry.insert(0,mappa.get(key,""))
            if key in ("Sent","Nome","QTH","Grid"): entry.configure(state="readonly")
        self._aggiorna_thumbnail(record[8]); self._pulisci_panel_hamqth()

    def _svuota_campi(self):
        for key,entry in self.entries.items():
            entry.configure(state="normal"); entry.delete(0,tk.END)
            if key in ("Sent","Nome","QTH","Grid"): entry.configure(state="readonly")
        self.selected_id=None
        self.thumb_label.configure(image="",text="Nessuna immagine selezionata")
        self.thumb_label.image=None
        self._pulisci_panel_hamqth()

    def _pulisci_panel_hamqth(self):
        for lbl in self.hamqth_labels.values(): lbl.configure(text="—")

    # ══════════════════════════════════════════
    # ELIMINAZIONE RECORD
    # ══════════════════════════════════════════
    def _ids_selezionati(self): return [int(iid) for iid in self.tree.selection()]

    def _elimina_selezionato(self):
        if not self.selected_id:
            messagebox.showwarning("Attenzione","Seleziona prima un record."); return
        record=next((r for r in self.records if r[0]==self.selected_id),None)
        if not record: return
        call=record[1] or str(self.selected_id); qsl_file=record[8] or ""
        dlg=DialogoEliminaConFile(self.root,records=[(record[0],call,qsl_file)],palette=self._p)
        elimina_rec,elimina_file=dlg.risultato
        if not elimina_rec: return
        bl=0
        if elimina_file and qsl_file: _,bl=_elimina_file_fisico(qsl_file)
        self._cancella_ids([self.selected_id])
        msg=f"Record di {call} eliminato."
        if elimina_file and bl>0: msg+=f"\nFile PNG rimosso: {_dimensione_leggibile(bl)} liberati."
        elif elimina_file: msg+="\nFile PNG non trovato su disco (già assente)."
        messagebox.showinfo("Eliminato",msg)

    def _elimina_multipli(self):
        ids=self._ids_selezionati()
        if not ids: messagebox.showwarning("Attenzione","Seleziona uno o più record."); return
        records_sel=[(r[0],r[1] or "???",r[8] or "")
                     for rid in ids for r in self.records if r[0]==rid]
        dlg=DialogoEliminaConFile(self.root,records=records_sel,palette=self._p)
        elimina_rec,elimina_file=dlg.risultato
        if not elimina_rec: return
        bl=0
        if elimina_file:
            for _,_,qf in records_sel:
                if qf: _,sz=_elimina_file_fisico(qf); bl+=sz
        self._cancella_ids(ids)
        msg=f"{len(ids)} record eliminati."
        if elimina_file: msg+=f"\nSpazio liberato: {_dimensione_leggibile(bl)}."
        messagebox.showinfo("Eliminazione completata",msg)

    def _elimina_tutti(self):
        totale=len(self.records)
        if totale==0: messagebox.showinfo("Database vuoto","Nessun record da eliminare."); return
        files_presenti=[r[8] for r in self.records if r[8] and os.path.isfile(r[8])]
        tot_bytes=sum(_dimensione_file(f) for f in files_presenti)
        var_file=tk.BooleanVar(value=False)
        dlg=tk.Toplevel(self.root); dlg.title("⚠ Eliminazione totale")
        dlg.resizable(False,False); dlg.transient(self.root); dlg.grab_set()
        p=self._p; dlg.configure(bg=p["bg"])
        hdr=tk.Frame(dlg,bg=p.get("warning_bg",p["barra_off"])); hdr.pack(fill=tk.X)
        tk.Label(hdr,text=f"⚠  Eliminare TUTTI i {totale} record?",
                 bg=p.get("warning_bg",p["barra_off"]),fg=p.get("warning_fg",p["barra_fg"]),
                 font=("Arial",11,"bold")).pack(padx=12,pady=8)
        body=tk.Frame(dlg,bg=p["bg"]); body.pack(padx=16,pady=10)
        tk.Label(body,text="OPERAZIONE IRREVERSIBILE.\nTutti i record del database verranno eliminati.",
                 bg=p["bg"],fg=p["fg"],justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Separator(body,orient="horizontal").pack(fill=tk.X,pady=6)
        if files_presenti:
            tk.Checkbutton(body,
                           text=f"🗑  Elimina anche i {len(files_presenti)} file PNG  ({_dimensione_leggibile(tot_bytes)})",
                           variable=var_file,bg=p["bg"],fg=p["fg"],selectcolor=p["bg_alt"],
                           activebackground=p["bg"],activeforeground=p.get("danger","#e05555"),
                           font=("Arial",9,"bold"),cursor="hand2").pack(anchor=tk.W)
        result=[False,False]
        def _conferma(): result[0]=True; result[1]=var_file.get(); dlg.destroy()
        frm_btn=tk.Frame(dlg,bg=p["bg"]); frm_btn.pack(fill=tk.X,padx=16,pady=(0,12))
        tk.Button(frm_btn,text="Annulla",command=dlg.destroy,bg=p["bg_alt"],fg=p["fg"],
                  relief=tk.FLAT,padx=12,pady=5,cursor="hand2").pack(side=tk.RIGHT,padx=4)
        tk.Button(frm_btn,text="⚠ Elimina tutti",command=_conferma,
                  bg=p.get("danger","#c0392b"),fg="#fff",
                  relief=tk.FLAT,padx=12,pady=5,cursor="hand2",
                  font=("Arial",9,"bold")).pack(side=tk.RIGHT,padx=4)
        dlg.update_idletasks()
        px=self.root.winfo_rootx()+(self.root.winfo_width() -dlg.winfo_width()) //2
        py=self.root.winfo_rooty()+(self.root.winfo_height()-dlg.winfo_height())//2
        dlg.geometry(f"+{px}+{py}"); self.root.wait_window(dlg)
        if not result[0]: return
        if not messagebox.askyesno("⚠ Ultima conferma","Sei assolutamente sicuro?"): return
        bl=0
        if result[1]:
            for f in files_presenti: _,sz=_elimina_file_fisico(f); bl+=sz
        conn=sqlite3.connect(DB_FILE); conn.execute("DELETE FROM qsl_records"); conn.commit(); conn.close()
        self._carica_records()
        msg=f"Tutti i {totale} record eliminati."
        if result[1]: msg+=f"\nSpazio liberato: {_dimensione_leggibile(bl)}."
        messagebox.showinfo("Database svuotato",msg)

    def _cancella_ids(self,ids):
        if not ids: return
        conn=sqlite3.connect(DB_FILE)
        conn.cursor().executemany("DELETE FROM qsl_records WHERE id=?",[(i,) for i in ids])
        conn.commit(); conn.close()
        self.selected_id=None; self._carica_records()

    # ══════════════════════════════════════════
    # GESTIONE FILE QSL SU DISCO
    # ══════════════════════════════════════════
    def _elimina_file_qsl_selezionato(self):
        if not self.selected_id:
            messagebox.showwarning("Attenzione","Seleziona prima un record."); return
        record=next((r for r in self.records if r[0]==self.selected_id),None)
        if not record: return
        call=record[1] or "???"; qsl_file=record[8] or ""
        if not qsl_file:
            messagebox.showinfo("Nessun file",f"Il record di {call} non ha un file QSL associato."); return
        if not os.path.isfile(qsl_file):
            if messagebox.askyesno("File non trovato",
                                    f"Il file non esiste su disco:\n{qsl_file}\n\n"
                                    f"Azzerare il percorso nel database?"):
                conn=sqlite3.connect(DB_FILE)
                conn.execute("UPDATE qsl_records SET qsl_file=NULL WHERE id=?",(self.selected_id,))
                conn.commit(); conn.close()
                self.entries["QSL File"].configure(state="normal")
                self.entries["QSL File"].delete(0,tk.END)
                self.entries["QSL File"].configure(state="readonly")
                self._aggiorna_thumbnail(None); self._carica_records()
            return
        size_str=_dimensione_leggibile(_dimensione_file(qsl_file))
        short=qsl_file if len(qsl_file)<=55 else "…"+qsl_file[-54:]
        if not messagebox.askyesno("Elimina file PNG",
                                    f"Record: {call}\nFile: {short}\nSpazio: {size_str}\n\n"
                                    f"Il file verrà eliminato dal disco.\n"
                                    f"Il record nel database viene MANTENUTO.\n\nContinuare?"): return
        successo,bl=_elimina_file_fisico(qsl_file)
        if successo:
            conn=sqlite3.connect(DB_FILE)
            conn.execute("UPDATE qsl_records SET qsl_file=NULL WHERE id=?",(self.selected_id,))
            conn.commit(); conn.close()
            self.entries["QSL File"].configure(state="normal")
            self.entries["QSL File"].delete(0,tk.END)
            self.entries["QSL File"].configure(state="readonly")
            self._aggiorna_thumbnail(None); self._carica_records()
            messagebox.showinfo("File eliminato",f"✅ File PNG eliminato.\nSpazio: {_dimensione_leggibile(bl)}.")
        else:
            messagebox.showerror("Errore",f"Impossibile eliminare il file:\n{qsl_file}")

    def _pulizia_file_qsl(self):
        db_files={os.path.abspath(r[8]) for r in self.records if r[8]}
        dlg=DialogoPuliziaFile(self.root,db_files=db_files,output_dir=OUTPUT_DIR,palette=self._p)
        if dlg.azione_eseguita: self._carica_records()

    def _statistiche_spazio(self):
        db_files={os.path.abspath(r[8]) for r in self.records if r[8]}
        esistenti_db={p for p in db_files if os.path.isfile(p)}
        mancanti_db=db_files-esistenti_db
        bytes_db=sum(_dimensione_file(p) for p in esistenti_db)
        files_disco=set()
        if os.path.isdir(OUTPUT_DIR):
            files_disco={os.path.abspath(os.path.join(OUTPUT_DIR,f))
                         for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".jpg")}
        orfani=files_disco-db_files
        bytes_disco=sum(_dimensione_file(p) for p in files_disco)
        bytes_orf=sum(_dimensione_file(p) for p in orfani)
        riga=lambda l,v: f"  {l:<32}{v}"
        msg="\n".join(["📊  Statistiche spazio file QSL","─"*46,
                       riga("Cartella output:",OUTPUT_DIR),"",
                       riga("Record nel DB con file:",f"{len(db_files)}"),
                       riga("  → presenti su disco:",f"{len(esistenti_db)}  ({_dimensione_leggibile(bytes_db)})"),
                       riga("  → percorso non trovato:",f"{len(mancanti_db)}"),"",
                       riga("File JPG su disco (totale):",f"{len(files_disco)}  ({_dimensione_leggibile(bytes_disco)})"),
                       riga("  → referenziati nel DB:",f"{len(files_disco&db_files)}"),
                       riga("  → orfani (non nel DB):",f"{len(orfani)}  ({_dimensione_leggibile(bytes_orf)})")])
        messagebox.showinfo("Statistiche spazio",msg)

    # ══════════════════════════════════════════
    # DUPLICATI
    # ══════════════════════════════════════════
    def _trova_duplicati(self) -> list:
        bucket=defaultdict(list)
        for rec in self.records:
            call=(rec[1] or "").upper().strip(); data=(rec[2] or "").strip(); ora=(rec[3] or "").strip()[:4]
            if call: bucket[(call,data,ora)].append(rec[0])
        return [ids for ids in bucket.values() if len(ids)>1]

    def _gestisci_duplicati(self):
        gruppi=self._trova_duplicati()
        if not gruppi: messagebox.showinfo("Duplicati","Nessun duplicato trovato."); return
        totale_eccesso=sum(len(g)-1 for g in gruppi)
        messagebox.showinfo("Duplicati trovati",
                            f"Trovati {len(gruppi)} gruppi ({totale_eccesso} in eccesso su {len(self.records)}).")
        records_map={r[0]:r for r in self.records}
        DialogoDuplicati(self.root,gruppi=gruppi,records_map=records_map,
                         on_elimina_cb=self._cancella_ids,palette=self._p)
        self._carica_records()

    def _elimina_duplicati_auto(self):
        gruppi=self._trova_duplicati()
        if not gruppi: messagebox.showinfo("Duplicati","Nessun duplicato trovato."); return
        totale_eccesso=sum(len(g)-1 for g in gruppi)
        if not messagebox.askyesno("Eliminazione automatica duplicati",
                                    f"Trovati {len(gruppi)} gruppi.\n"
                                    f"Verranno eliminati {totale_eccesso} record in eccesso.\n\n"
                                    f"Priorità: email ➜ qsl_file ➜ inviato ➜ nome ➜ qth ➜ grid.\n\nContinuare?"): return
        def _punteggio(rec):
            score=0
            if rec[7]:  score+=4
            if rec[8] and os.path.exists(rec[8]): score+=3
            elif rec[8]: score+=1
            if rec[9]:  score+=2
            if rec[10]: score+=1
            if rec[11]: score+=1
            if rec[12]: score+=1
            return score
        records_map={r[0]:r for r in self.records}; da_eliminare=[]
        for gruppo in gruppi:
            ordinati=sorted(gruppo,key=lambda rid:_punteggio(records_map[rid]),reverse=True)
            da_eliminare.extend(ordinati[1:])
        self._cancella_ids(da_eliminare)
        messagebox.showinfo("Eliminazione completata",
                            f"✅ Eliminati {len(da_eliminare)} record duplicati.\n"
                            f"Conservati {len(gruppi)} record (uno per gruppo).")

    # ══════════════════════════════════════════
    # HAMQTH
    # ══════════════════════════════════════════
    def _cerca_hamqth(self):
        if not hamqth_client:
            messagebox.showerror("HamQTH non configurato","Aggiungi [HAMQTH] nel config.ini."); return
        if not self.selected_id:
            messagebox.showwarning("Attenzione","Seleziona prima un record."); return
        call=self.entries["CALL"].get().strip()
        if not call: messagebox.showwarning("Attenzione","Il campo CALL è vuoto."); return
        self.root.configure(cursor="watch"); self.root.update()
        try: dati=hamqth_client.cerca_nominativo(call)
        except Exception as e:
            self.root.configure(cursor=""); messagebox.showerror("Errore HamQTH",str(e)); return
        self.root.configure(cursor="")
        if dati is None: messagebox.showinfo("HamQTH",f"{call} non trovato."); return
        for key,lbl in self.hamqth_labels.items():
            lbl.configure(text=dati.get(key,"—") or "—",foreground=self._p["accent"])
        suggerimenti={}
        if not self.entries["Email"].get().strip() and dati.get("email"):
            suggerimenti["email"]=("Email",dati["email"])
        if not self.entries["Nome"].get().strip() and dati.get("nick"):
            suggerimenti["name"]=("Nome",dati["nick"])
        if not self.entries["QTH"].get().strip() and dati.get("qth"):
            suggerimenti["qth"]=("QTH",dati["qth"])
        if not self.entries["Grid"].get().strip() and dati.get("grid"):
            suggerimenti["grid"]=("Grid",dati["grid"])
        if suggerimenti:
            testo="\n".join(f"  {l}: {v}" for _,(l,v) in suggerimenti.items())
            if messagebox.askyesno("Dati trovati su HamQTH",
                                    f"Dati mancanti per {call}:\n\n{testo}\n\nSalvare nel database?"):
                for db_key,(label,value) in suggerimenti.items():
                    self.entries[label].configure(state="normal")
                    self.entries[label].delete(0,tk.END); self.entries[label].insert(0,value)
                    if label in ("Nome","QTH","Grid"): self.entries[label].configure(state="readonly")
                conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
                for db_key,(_,value) in suggerimenti.items():
                    cur.execute(f"UPDATE qsl_records SET {db_key}=? WHERE id=?",(value,self.selected_id))
                conn.commit(); conn.close(); self._carica_records()

    def _aggiorna_tutti_hamqth(self):
        if not hamqth_client:
            messagebox.showerror("HamQTH non configurato","Aggiungi [HAMQTH] nel config.ini."); return
        da_aggiornare=[r for r in self.records if not r[10] or not r[11] or not r[12] or not r[7]]
        if not da_aggiornare:
            messagebox.showinfo("Aggiornamento","Tutti i record hanno già nome, QTH, grid ed email."); return
        calls_uniche=list(dict.fromkeys(r[1] for r in da_aggiornare if r[1]))
        if not messagebox.askyesno("Aggiornamento batch",
                                    f"{len(da_aggiornare)} record incompleti "
                                    f"({len(calls_uniche)} callsign). Avviare la ricerca?"): return
        prog=tk.Toplevel(self.root); prog.title("Aggiornamento HamQTH…")
        prog.geometry("450x160"); prog.resizable(False,False); prog.configure(bg=self._p["bg"])
        ttk.Label(prog,text="Ricerca HamQTH in corso…").pack(pady=10)
        pvar=tk.DoubleVar()
        ttk.Progressbar(prog,variable=pvar,maximum=len(calls_uniche)).pack(fill=tk.X,padx=20)
        lbl_s=ttk.Label(prog,text=""); lbl_s.pack(pady=5)
        cache={}; arricchiti=0; non_trovati=[]
        conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
        for i,call in enumerate(calls_uniche):
            lbl_s.configure(text=f"Ricerca {i+1}/{len(calls_uniche)}: {call}")
            pvar.set(i+1); prog.update()
            if call not in cache:
                try: cache[call]=hamqth_client.cerca_nominativo(call)
                except Exception: cache[call]=None
            dati=cache[call]
            if dati is None: non_trovati.append(call); continue
            for rec in [r for r in da_aggiornare if r[1]==call]:
                cur.execute("UPDATE qsl_records SET email=?,name=?,qth=?,grid=? WHERE id=?",
                            (dati.get("email") if not rec[7]  else rec[7],
                             dati.get("nick")  if not rec[10] else rec[10],
                             dati.get("qth")   if not rec[11] else rec[11],
                             dati.get("grid")  if not rec[12] else rec[12],rec[0]))
                arricchiti+=1
        conn.commit(); conn.close()
        prog.destroy(); self._carica_records()
        ris=f"✅ Aggiornati: {arricchiti}\n❓ Non trovati: {len(non_trovati)}"
        if non_trovati: ris+="\n\n"+", ".join(non_trovati)
        messagebox.showinfo("Risultato aggiornamento",ris)

    def _stato_sessione_hamqth(self):
        if not hamqth_client: messagebox.showinfo("HamQTH","Non configurato nel config.ini."); return
        if hamqth_client.session_id:
            eta=int(time.time()-hamqth_client.session_time); resto=max(0,3600-eta)
            messagebox.showinfo("Sessione HamQTH",
                                f"Attiva ✅\nUtente: {hamqth_client.username}\n"
                                f"Scade tra: {resto//60}m {resto%60}s")
        else: messagebox.showinfo("Sessione HamQTH","Nessuna sessione attiva.")

    # ══════════════════════════════════════════
    # ANTEPRIMA
    # ══════════════════════════════════════════
    def _aggiorna_thumbnail(self,file_path):
        if file_path and os.path.exists(file_path):
            try:
                img=Image.open(file_path); img.thumbnail((220,160))
                photo=ImageTk.PhotoImage(img)
                self.thumb_label.configure(image=photo,text="")
                self.thumb_label.image=photo; return
            except Exception: pass
        self.thumb_label.configure(image="",text="Nessuna immagine selezionata")
        self.thumb_label.image=None

    def _mostra_anteprima(self):
        if not self.selected_id:
            messagebox.showwarning("Attenzione","Seleziona un record prima."); return
        qsl_file=self.entries["QSL File"].get().strip()
        if not qsl_file or not os.path.exists(qsl_file):
            messagebox.showerror("Errore","File QSL non trovato."); return
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.lift(); return
        self.preview_window=tk.Toplevel(self.root)
        self.preview_window.title(f"Anteprima — {os.path.basename(qsl_file)}")
        self.preview_window.geometry("820x620"); self.preview_window.configure(bg=self._p["bg"])
        try:
            img=Image.open(qsl_file); img.thumbnail((800,580))
            photo=ImageTk.PhotoImage(img)
            lbl=ttk.Label(self.preview_window,image=photo)
            lbl.image=photo; lbl.pack(expand=True,fill=tk.BOTH,padx=10,pady=10)
        except Exception as e:
            ttk.Label(self.preview_window,text=f"Errore: {e}").pack()

    # ══════════════════════════════════════════
    # SALVATAGGIO E FILE QSL
    # ══════════════════════════════════════════
    def _salva_modifiche(self):
        if not self.selected_id:
            messagebox.showwarning("Seleziona record","Seleziona un record prima di salvare."); return
        conn=sqlite3.connect(DB_FILE)
        conn.execute("UPDATE qsl_records SET call=?,qso_date=?,time_on=?,mode=?,band=?,rst_sent=?,email=?,qsl_file=? WHERE id=?",
                     (self.entries["CALL"].get().strip(),self.entries["Data QSO"].get().strip(),
                      self.entries["Ora QSO"].get().strip(),self.entries["Modalità"].get().strip(),
                      self.entries["Banda"].get().strip(),self.entries["RST"].get().strip(),
                      self.entries["Email"].get().strip(),self.entries["QSL File"].get().strip(),
                      self.selected_id))
        conn.commit(); conn.close()
        messagebox.showinfo("Salvato","Modifiche salvate con successo.")
        self._carica_records()

    def _seleziona_file_qsl(self):
        if not self.selected_id:
            messagebox.showwarning("Seleziona record","Seleziona un record prima."); return
        path=filedialog.askopenfilename(title="Seleziona file JPG",filetypes=[("JPG files","*.jpg *.jpeg"),("PNG files","*.png"),("Tutti i file","*.*")])
        if path:
            self.entries["QSL File"].delete(0,tk.END); self.entries["QSL File"].insert(0,path)
            self._aggiorna_thumbnail(path); self._salva_modifiche()

    # ══════════════════════════════════════════
    # EMAIL
    # ══════════════════════════════════════════
    def _invia_email_click(self):
        if not self.selected_id:
            messagebox.showwarning("Attenzione","Seleziona un record prima."); return
        email=self.entries["Email"].get().strip(); call=self.entries["CALL"].get().strip()
        qso_date=self.entries["Data QSO"].get().strip(); qsl_file=self.entries["QSL File"].get().strip()
        if not email: messagebox.showerror("Errore","Il campo Email è vuoto."); return
        if not qsl_file or not os.path.exists(qsl_file):
            messagebox.showerror("Errore","File QSL non trovato."); return
        data_fmt=_data_per_email(qso_date); oggetto_default,testo_default=_componi_testo_email(call,data_fmt)
        dlg=DialogoEmail(self.root,oggetto_default=oggetto_default,testo_default=testo_default,
                         destinatario=email,titolo=f"Componi email per {call}",palette=self._p)
        oggetto,testo=dlg.risultato
        if oggetto is None: return
        try:
            self._invia_email(email,oggetto,testo,qsl_file)
            self._segna_come_inviato(self.selected_id)
            messagebox.showinfo("Email inviata",f"Email inviata con successo a {email}.")
            self._carica_records()
        except Exception as e: messagebox.showerror("Errore invio",str(e))

    def _invia_tutti_pending(self):
        pending=[r for r in self.records if not r[9]]
        if not pending: messagebox.showinfo("Nessun record","Non ci sono record da inviare."); return
        validi=[r for r in pending if r[7] and r[8] and os.path.exists(r[8])]
        invalidi=len(pending)-len(validi)
        if not validi: messagebox.showerror("Errore","Nessun record con email e file QSL valido."); return
        oggetto_tmpl_it="QSL Card per {CALL} - {DATE}"
        testo_tmpl_it=("Caro/a {CALL},\n\nTi invio la QSL per il collegamento del {DATE}.\n\n"
                       "Cordiali saluti e 73 de IZ8GCH GL.\n\nSpero di rivederti sulla mia frequenza!")
        messagebox.showinfo("Invio multiplo",
                            f"📬 Stai per inviare {len(validi)} email"
                            +(f"  ({invalidi} ignorati)" if invalidi else "")
                            +"\n\nUsa {CALL} e {DATE} come segnaposto.")
        dlg=DialogoEmail(self.root,oggetto_default=oggetto_tmpl_it,testo_default=testo_tmpl_it,
                         destinatario=f"{len(validi)} destinatari",
                         titolo="Componi messaggio per invio multiplo",palette=self._p)
        oggetto_tmpl,testo_tmpl=dlg.risultato
        if oggetto_tmpl is None: return
        usa_auto=(oggetto_tmpl==oggetto_tmpl_it and testo_tmpl==testo_tmpl_it)
        if not messagebox.askyesno("Conferma",f"Stai per inviare {len(validi)} email.\nConfermi?"): return
        prog=tk.Toplevel(self.root); prog.title("Invio in corso…")
        prog.geometry("400x150"); prog.resizable(False,False); prog.configure(bg=self._p["bg"])
        ttk.Label(prog,text="Invio email in corso…").pack(pady=10)
        pvar=tk.DoubleVar()
        ttk.Progressbar(prog,variable=pvar,maximum=len(validi)).pack(fill=tk.X,padx=20)
        lbl_s=ttk.Label(prog,text=""); lbl_s.pack(pady=5)
        inviati=0; errori=[]
        for i,rec in enumerate(validi):
            call=rec[1]; email=rec[7]; qsl_file=rec[8]; data=rec[2]
            data_fmt=_data_per_email(data)
            if usa_auto: oggetto,testo=_componi_testo_email(call,data_fmt)
            else:
                oggetto=oggetto_tmpl.replace("{CALL}",call).replace("{DATE}",data_fmt)
                testo=testo_tmpl.replace("{CALL}",call).replace("{DATE}",data_fmt)
            try:
                self._invia_email(email,oggetto,testo,qsl_file)
                self._segna_come_inviato(rec[0]); inviati+=1
            except Exception as e: errori.append(f"{call} ({email}): {e}")
            pvar.set(i+1); lbl_s.configure(text=f"Inviato {i+1}/{len(validi)}: {call}"); prog.update()
        prog.destroy(); self._carica_records()
        ris=f"✅ Inviati: {inviati}"
        if errori: ris+=f"\n❌ Errori: {len(errori)}\n"+"\n".join(errori[:5])
        messagebox.showinfo("Risultato invio",ris)

    def _invia_email(self,a,oggetto,testo,allegato):
        import ssl as _ssl
        msg=EmailMessage()
        msg["From"]=SMTP_CONF["user"]; msg["To"]=a; msg["Subject"]=oggetto
        msg.set_content(testo)
        with open(allegato,"rb") as f:
            msg.add_attachment(f.read(),maintype="image",subtype="png",
                               filename=os.path.basename(allegato))
        porta=int(SMTP_CONF["port"])
        if porta==465:
            ctx=_ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_CONF["server"],porta,context=ctx,timeout=20) as smtp:
                smtp.login(SMTP_CONF["user"],SMTP_CONF["password"]); smtp.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_CONF["server"],porta,timeout=20) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
                smtp.login(SMTP_CONF["user"],SMTP_CONF["password"]); smtp.send_message(msg)

    def _segna_come_inviato(self,record_id):
        conn=sqlite3.connect(DB_FILE)
        conn.execute("UPDATE qsl_records SET sent=1 WHERE id=?",(record_id,))
        conn.commit(); conn.close()

    # ══════════════════════════════════════════
    # INFO
    # ══════════════════════════════════════════
    def _info_app(self):
        editor_s="✅ disponibile" if EDITOR_DISPONIBILE else "❌ non trovato"
        modello_s=os.path.basename(self.modello_path) if self.modello_attivo else "nessuno (legacy)"
        tema_s="🌙 Scuro" if self._tema_nome=="scuro" else "☀ Chiaro"
        messagebox.showinfo("Informazioni",
                            f"Gestione Record QSL  v4.3\nIZ8GCH\n\n"
                            f"Python + Tkinter + Pillow\n"
                            f"qsl_editor2_tema.py: {editor_s}\n"
                            f"Modello attivo: {modello_s}\n"
                            f"Export: {self._export_w}×{self._export_h}px @{self._export_dpi}DPI\n"
                            f"Tema UI: {tema_s}\n\n"
                            f"v4.3: integrazione completa con qsl_editor2_tema\n"
                            f"  • Dialog DPI prima di ogni generazione\n"
                            f"  • Verifica/ridimensionamento sfondo al caricamento modello\n"
                            f"  • bg_img passato a genera_qsl (nessuna riapertura dal disco)\n"
                            f"  • Rispetto esatto delle regole del modello JSON")


# ══════════════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    GestoreQSL(root)
    root.mainloop()
