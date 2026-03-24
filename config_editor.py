"""
ADIMAIL — Editor Configurazione  IZ8GCH
========================================
Gestione interattiva del file config.ini:
  • Auto-rilevamento server SMTP dall'indirizzo email
  • Test connessione SMTP in tempo reale
  • Configurazione accesso HamQTH
  • Stile coerente con il launcher ADIMAIL (dark navy)
"""

import os
import sys
import ssl
import smtplib
import threading
import configparser
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import platform

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE PROVIDER SMTP
# ══════════════════════════════════════════════════════════════════════════════
# Ogni entry: dominio → (server, porta_tls, porta_ssl, nome_provider, note)
SMTP_DB = {
    # ── Google ────────────────────────────────────────────────────────────────
    "gmail.com":          ("smtp.gmail.com",        587, 465, "Gmail (Google)",
                           "Richiede 'Password per le app' se 2FA attiva.\n"
                           "https://myaccount.google.com/apppasswords"),
    "googlemail.com":     ("smtp.gmail.com",        587, 465, "Gmail (Google)", ""),

    # ── Microsoft / Outlook ───────────────────────────────────────────────────
    "outlook.com":        ("smtp-mail.outlook.com", 587, 465, "Outlook.com",
                           "Usa la tua password Microsoft o una App Password."),
    "hotmail.com":        ("smtp-mail.outlook.com", 587, 465, "Hotmail (Microsoft)", ""),
    "live.com":           ("smtp-mail.outlook.com", 587, 465, "Live (Microsoft)",   ""),
    "live.it":            ("smtp-mail.outlook.com", 587, 465, "Live.it (Microsoft)",""),
    "msn.com":            ("smtp-mail.outlook.com", 587, 465, "MSN (Microsoft)",    ""),

    # ── Yahoo ─────────────────────────────────────────────────────────────────
    "yahoo.com":          ("smtp.mail.yahoo.com",   587, 465, "Yahoo Mail",
                           "Richiede App Password dalla pagina sicurezza account."),
    "yahoo.it":           ("smtp.mail.yahoo.com",   587, 465, "Yahoo Mail IT",      ""),
    "yahoo.co.uk":        ("smtp.mail.yahoo.com",   587, 465, "Yahoo Mail UK",      ""),
    "ymail.com":          ("smtp.mail.yahoo.com",   587, 465, "Yahoo Mail",         ""),

    # ── Libero / ItaliaOnLine ─────────────────────────────────────────────────
    "libero.it":          ("smtp.libero.it",        465, 465, "Libero Mail",
                           "Porta 465 con SSL. Abilita SMTP nelle impostazioni account."),
    "inwind.it":          ("smtp.libero.it",        465, 465, "Inwind (Libero)",    ""),
    "iol.it":             ("smtp.libero.it",        465, 465, "IOL (Libero)",       ""),

    # ── Tiscali ───────────────────────────────────────────────────────────────
    "tiscali.it":         ("smtp.tiscali.it",       465, 465, "Tiscali Mail",
                           "Porta 465 SSL. Verifica le impostazioni sul pannello Tiscali."),

    # ── Alice / TIM / Telecom ─────────────────────────────────────────────────
    "alice.it":           ("smtp.alice.it",         465, 465, "Alice (TIM)",
                           "Usa 465 SSL. Potrebbe richiedere autenticazione di terze parti."),
    "tim.it":             ("smtp.tim.it",           465, 465, "TIM Mail",           ""),
    "telecomitalia.it":   ("smtp.tim.it",           465, 465, "Telecom Italia",     ""),

    # ── Virgilio / Matrix ─────────────────────────────────────────────────────
    "virgilio.it":        ("smtp.virgilio.it",      465, 465, "Virgilio Mail",      ""),
    "email.it":           ("smtp.email.it",         465, 465, "Email.it",           ""),

    # ── FastWebNet ────────────────────────────────────────────────────────────
    "fastwebnet.it":      ("smtp.fastwebnet.it",    587, 465, "FastWebNet",         ""),

    # ── Aruba ─────────────────────────────────────────────────────────────────
    "aruba.it":           ("smtps.aruba.it",        465, 465, "Aruba Mail",
                           "Porta 465 SSL. Abilita SMTP autenticato nel pannello."),
    "pec.it":             ("smtps.aruba.it",        465, 465, "Aruba PEC",          ""),

    # ── iCloud ────────────────────────────────────────────────────────────────
    "icloud.com":         ("smtp.mail.me.com",      587, 587, "iCloud Mail",
                           "Richiede App-Specific Password da appleid.apple.com"),
    "me.com":             ("smtp.mail.me.com",      587, 587, "iCloud Mail (me)",   ""),
    "mac.com":            ("smtp.mail.me.com",      587, 587, "iCloud Mail (mac)",  ""),

    # ── ProtonMail Bridge ─────────────────────────────────────────────────────
    "protonmail.com":     ("127.0.0.1",             1025, 1025,"ProtonMail Bridge",
                           "Richiede ProtonMail Bridge installato in locale."),
    "proton.me":          ("127.0.0.1",             1025, 1025,"ProtonMail Bridge", ""),

    # ── Zoho ──────────────────────────────────────────────────────────────────
    "zoho.com":           ("smtp.zoho.com",         587, 465, "Zoho Mail",          ""),
    "zohomail.com":       ("smtp.zoho.com",         587, 465, "Zoho Mail",          ""),

    # ── GMX ───────────────────────────────────────────────────────────────────
    "gmx.com":            ("mail.gmx.com",          587, 465, "GMX Mail",           ""),
    "gmx.de":             ("mail.gmx.net",          587, 465, "GMX (DE)",           ""),
    "gmx.net":            ("mail.gmx.net",          587, 465, "GMX Net",            ""),

    # ── Web.de ────────────────────────────────────────────────────────────────
    "web.de":             ("smtp.web.de",           587, 465, "Web.de",             ""),

    # ── Tutanota ──────────────────────────────────────────────────────────────
    "tutanota.com":       ("mail.tutanota.com",     587, 465, "Tutanota",
                           "SMTP non supportato nativamente. Usa API o Bridge."),
    "tuta.io":            ("mail.tutanota.com",     587, 465, "Tuta.io",            ""),

    # ── Fascia operatori italiani ─────────────────────────────────────────────
    "wind.it":            ("smtp.wind.it",          587, 465, "Wind Mail",          ""),
    "vodafone.it":        ("smtp.vodafone.it",      587, 465, "Vodafone Mail",      ""),
    "tin.it":             ("smtp.tin.it",           465, 465, "TIN (TIM)",          ""),
}

# Porte e comportamento preferito per ogni porta
PORTA_INFO = {
    587:  ("STARTTLS", "Raccomandato — negozia TLS in chiaro poi cifra"),
    465:  ("SSL/TLS",  "SSL immediato (più vecchio ma ampiamente supportato)"),
    25:   ("PLAIN",    "Non cifrato — sconsigliato"),
    1025: ("BRIDGE",   "Connessione locale (Bridge app)"),
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNZIONI HELPER
# ══════════════════════════════════════════════════════════════════════════════
def dominio_da_email(email: str) -> str:
    """Estrae il dominio dall'indirizzo email."""
    email = email.strip().lower()
    if "@" in email:
        return email.split("@", 1)[1]
    return ""


def rileva_smtp(email: str) -> dict | None:
    """
    Cerca il provider SMTP in base al dominio dell'email.
    Ritorna un dict con i dati o None se non trovato.
    """
    dominio = dominio_da_email(email)
    if not dominio:
        return None
    # ricerca esatta
    if dominio in SMTP_DB:
        server, porta_tls, porta_ssl, nome, note = SMTP_DB[dominio]
        return dict(server=server, porta=porta_tls, porta_ssl=porta_ssl,
                    nome=nome, note=note, dominio=dominio)
    # ricerca per suffisso (es. mail.azienda.it → *.it)
    parti = dominio.split(".")
    for n in range(1, len(parti)):
        suffisso = ".".join(parti[n:])
        for chiave, val in SMTP_DB.items():
            if chiave.endswith("." + suffisso) or chiave == suffisso:
                server, porta_tls, porta_ssl, nome, note = val
                return dict(server=server, porta=porta_tls, porta_ssl=porta_ssl,
                            nome=nome, note=note, dominio=dominio)
    return None


def carica_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE, encoding="utf-8")
    return cfg


def salva_config(cfg: configparser.ConfigParser):
    """Salva il configuration file con gestione errori"""
    try:
        # Crea la directory se non esiste
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # Backup del file esistente
        if os.path.exists(CONFIG_FILE):
            backup_file = CONFIG_FILE + ".backup"
            try:
                import shutil
                shutil.copy2(CONFIG_FILE, backup_file)
            except Exception:
                pass  # Il backup non è critico
        
        # Debug: stampa sezioni prima del salvataggio
        print(f"[DEBUG] Sezioni da salvare: {list(cfg.sections())}")
        if 'DEFAULTS' in cfg:
            print(f"[DEBUG] DEFAULTS: {dict(cfg['DEFAULTS'])}")
        
        # Salva il nuovo config
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
            f.flush()  # Forza la scrittura su disco
            os.fsync(f.fileno())  # Sincronizzazione filesystem
        
        print(f"[DEBUG] Config salvato in: {CONFIG_FILE}")
        
        # Verifica immediata del salvataggio
        cfg_check = configparser.ConfigParser()
        cfg_check.read(CONFIG_FILE)
        if 'DEFAULTS' in cfg_check:
            print(f"[DEBUG] Verifica DEFAULTS dopo salvataggio: {dict(cfg_check['DEFAULTS'])}")
        else:
            print("[DEBUG] DEFAULTS non trovato dopo salvataggio!")
        
        return True
        
    except Exception as e:
        print(f"[ERRORE] Salvataggio config: {e}")
        raise e


# ══════════════════════════════════════════════════════════════════════════════
# TEST CONNESSIONE SMTP (thread separato)
# ══════════════════════════════════════════════════════════════════════════════
def test_smtp(server, porta, user, password, callback):
    """Testa la connessione SMTP; chiama callback(ok: bool, msg: str)."""
    def _run():
        try:
            if porta == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(server, porta, context=ctx, timeout=10) as s:
                    s.login(user, password)
            else:
                with smtplib.SMTP(server, porta, timeout=10) as s:
                    s.ehlo()
                    s.starttls()
                    s.ehlo()
                    s.login(user, password)
            callback(True, "✅  Connessione riuscita! Credenziali verificate.")
        except smtplib.SMTPAuthenticationError:
            callback(False, "❌  Autenticazione fallita.\n"
                            "Controlla email, password o abilita l'accesso app.")
        except smtplib.SMTPConnectError as e:
            callback(False, f"❌  Impossibile connettersi a {server}:{porta}\n{e}")
        except TimeoutError:
            callback(False, f"❌  Timeout connessione a {server}:{porta}")
        except Exception as e:
            callback(False, f"❌  Errore: {e}")
    threading.Thread(target=_run, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# PALETTE & STILE
# ══════════════════════════════════════════════════════════════════════════════
P = {
    "bg":          "#0d1f2d",
    "bg_panel":    "#111e2c",
    "bg_alt":      "#0a1520",
    "bg_input":    "#0f1e2e",
    "fg":          "#c8d8e8",
    "fg_dim":      "#4a6a80",
    "fg_bright":   "#e8f4fd",
    "accent":      "#4a9eca",
    "accent2":     "#2e6da4",
    "green":       "#4caf82",
    "red":         "#e05555",
    "yellow":      "#e0b050",
    "warn_fg":     "#ff9800",
    "warn_bg":     "#8a4000",
    "sep":         "#1a3a5c",
    "lf_fg":       "#4a9eca",
    "entry_hl":    "#1a4a72",
    "btn_save":    "#1a4a72",
    "btn_test":    "#1a5c2a",
    "btn_cancel":  "#3a2a1a",
}


def _style_entry(e: tk.Entry | tk.Text):
    e.configure(
        bg=P["bg_input"], fg=P["fg_bright"],
        insertbackground=P["accent"],
        selectbackground=P["accent2"],
        selectforeground="#ffffff",
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=P["sep"],
        highlightcolor=P["accent"])


def _lbl(parent, text, bold=False, dim=False, size=9):
    fg = P["fg_dim"] if dim else P["fg"]
    font = ("Courier", size, "bold") if bold else ("Courier", size)
    return tk.Label(parent, text=text, bg=P["bg_panel"],
                    fg=fg, font=font, anchor="w")


def _sep(parent):
    f = tk.Frame(parent, bg=P["sep"], height=1)
    f.pack(fill="x", padx=12, pady=6)
    return f


# ══════════════════════════════════════════════════════════════════════════════
# APPLICAZIONE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
class ConfigEditor:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ADIMAIL — Configurazione  IZ8GCH")
        self.root.geometry("780x700")
        self.root.minsize(680, 580)
        self.root.configure(bg=P["bg"])

        self._smtp_rilevato   = None   # dict con dati SMTP rilevati
        self._test_in_corso   = False

        self._init_ttk_style()
        self._costruisci_ui()
        self._carica_da_file()

    # ── TTK Style ────────────────────────────────────────────────────────────
    def _init_ttk_style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".",
                    background=P["bg_panel"], foreground=P["fg"],
                    fieldbackground=P["bg_input"],
                    troughcolor=P["bg_alt"],
                    selectbackground=P["accent2"],
                    selectforeground="#ffffff")
        s.configure("TFrame",     background=P["bg_panel"])
        s.configure("TLabel",     background=P["bg_panel"], foreground=P["fg"],
                    font=("Courier", 9))
        s.configure("TLabelframe", background=P["bg_panel"],
                    foreground=P["lf_fg"])
        s.configure("TLabelframe.Label",
                    background=P["bg_panel"], foreground=P["lf_fg"],
                    font=("Courier", 9, "bold"))
        s.configure("TNotebook",  background=P["bg"])
        s.configure("TNotebook.Tab",
                    background=P["bg_alt"], foreground=P["fg_dim"],
                    padding=[14, 5], font=("Courier", 9))
        s.map("TNotebook.Tab",
              background=[("selected", P["bg_panel"])],
              foreground=[("selected", P["accent"])])
        s.configure("TScrollbar",
                    background=P["bg_alt"], troughcolor=P["bg"],
                    arrowcolor=P["fg_dim"])
        s.configure("TCheckbutton",
                    background=P["bg_panel"], foreground=P["fg"],
                    font=("Courier", 9))
        s.map("TCheckbutton",
              background=[("active", P["bg_panel"])],
              foreground=[("active", P["accent"])])
        self.root.configure(bg=P["bg"])

    # ══════════════════════════════════════════════════════════════════════════
    # COSTRUZIONE UI
    # ══════════════════════════════════════════════════════════════════════════
    def _costruisci_ui(self):
        # ── Intestazione ─────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=P["bg_alt"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Frame(hdr, bg=P["accent"], width=4).pack(side="left", fill="y")

        tk.Label(hdr, text="⚙  ADIMAIL — Configurazione",
                 bg=P["bg_alt"], fg=P["accent"],
                 font=("Georgia", 14, "bold")).pack(
            side="left", padx=16, pady=12)

        tk.Label(hdr, text=f"  {CONFIG_FILE}",
                 bg=P["bg_alt"], fg=P["fg_dim"],
                 font=("Courier", 8)).pack(side="right", padx=16)

        # ── Notebook ─────────────────────────────────────────────────────────
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        self._tab_smtp   = ttk.Frame(nb)
        self._tab_hamqth = ttk.Frame(nb)
        self._tab_ui     = ttk.Frame(nb)

        nb.add(self._tab_smtp,   text="  📧  Email / SMTP  ")
        nb.add(self._tab_hamqth, text="  📡  HamQTH  ")
        nb.add(self._tab_ui,     text="  🎨  Interfaccia  ")

        self._build_tab_smtp()
        self._build_tab_hamqth()
        self._build_tab_ui()

        # ── Barra azioni ─────────────────────────────────────────────────────
        self._build_action_bar()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB SMTP
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_smtp(self):
        p = self._tab_smtp
        p.configure(style="TFrame")

        canvas = tk.Canvas(p, bg=P["bg_panel"], highlightthickness=0)
        sb     = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=P["bg_panel"])
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas(e):
            canvas.itemconfig(win, width=e.width)

        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", _on_canvas)

        def _scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        self._build_smtp_content(inner)

    def _build_smtp_content(self, p):
        pad = {"padx": 16, "pady": 4}

        # ── Sezione 1: Credenziali ────────────────────────────────────────────
        _lbl(p, "━━  CREDENZIALI  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             bold=True, size=9).pack(anchor="w", padx=16, pady=(16, 4))

        # Email
        frm_em = tk.Frame(p, bg=P["bg_panel"]); frm_em.pack(fill="x", **pad)
        _lbl(frm_em, "Indirizzo email:").pack(anchor="w")
        self._var_email = tk.StringVar()
        e_email = tk.Entry(frm_em, textvariable=self._var_email,
                           font=("Courier", 11), width=44)
        _style_entry(e_email)
        e_email.pack(fill="x", pady=(2, 0), ipady=5)
        self._var_email.trace_add("write", self._on_email_cambia)

        # Password
        frm_pw = tk.Frame(p, bg=P["bg_panel"]); frm_pw.pack(fill="x", **pad)
        _lbl(frm_pw, "Password  (o App Password):").pack(anchor="w")
        frm_pw2 = tk.Frame(frm_pw, bg=P["bg_panel"]); frm_pw2.pack(fill="x")
        self._var_password = tk.StringVar()
        self._e_pass = tk.Entry(frm_pw2, textvariable=self._var_password,
                                show="●", font=("Courier", 11), width=38)
        _style_entry(self._e_pass)
        self._e_pass.pack(side="left", fill="x", expand=True, ipady=5)
        self._var_mostra_pw = tk.BooleanVar(value=False)
        tk.Checkbutton(frm_pw2, text="mostra",
                       variable=self._var_mostra_pw,
                       command=self._toggle_pw,
                       bg=P["bg_panel"], fg=P["fg_dim"],
                       selectcolor=P["bg_alt"],
                       activebackground=P["bg_panel"],
                       font=("Courier", 8),
                       cursor="hand2").pack(side="left", padx=8)

        # Badge auto-detect
        frm_badge = tk.Frame(p, bg=P["bg_panel"])
        frm_badge.pack(fill="x", padx=16, pady=(2, 0))
        self._lbl_badge = tk.Label(
            frm_badge, text="",
            bg=P["bg_panel"], fg=P["fg_dim"],
            font=("Courier", 8), anchor="w")
        self._lbl_badge.pack(anchor="w")

        # ── Sezione 2: Server SMTP (auto o manuale) ───────────────────────────
        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=(10, 6))
        _lbl(p, "━━  SERVER SMTP  (auto-rilevato · modificabile)  ━━━━",
             bold=True, size=9).pack(anchor="w", padx=16, pady=(0, 4))

        frm_srv = tk.Frame(p, bg=P["bg_panel"]); frm_srv.pack(fill="x", **pad)
        _lbl(frm_srv, "Server SMTP:").pack(anchor="w")
        self._var_server = tk.StringVar()
        e_srv = tk.Entry(frm_srv, textvariable=self._var_server,
                         font=("Courier", 10), width=44)
        _style_entry(e_srv)
        e_srv.pack(fill="x", pady=(2, 0), ipady=4)

        # Porta con selettore rapido
        frm_porta = tk.Frame(p, bg=P["bg_panel"]); frm_porta.pack(fill="x", **pad)
        frm_porta_l = tk.Frame(frm_porta, bg=P["bg_panel"])
        frm_porta_l.pack(side="left", fill="x", expand=True)
        _lbl(frm_porta_l, "Porta:").pack(anchor="w")
        frm_porta_r = tk.Frame(frm_porta, bg=P["bg_panel"])
        frm_porta_r.pack(side="left", fill="x", expand=True, padx=(12, 0))
        _lbl(frm_porta_r, "Modalità:").pack(anchor="w")

        self._var_porta = tk.StringVar(value="587")
        frm_p2 = tk.Frame(frm_porta_l, bg=P["bg_panel"])
        frm_p2.pack(fill="x")
        e_porta = tk.Entry(frm_p2, textvariable=self._var_porta,
                           font=("Courier", 10), width=7)
        _style_entry(e_porta)
        e_porta.pack(side="left", ipady=4)
        self._var_porta.trace_add("write", lambda *_: self._aggiorna_badge_porta())

        # Bottoni porta rapida
        for porta in (587, 465, 25):
            tk.Button(frm_p2, text=str(porta),
                      bg=P["bg_alt"], fg=P["fg_dim"],
                      activebackground=P["accent"], activeforeground="#fff",
                      relief=tk.FLAT, font=("Courier", 8),
                      cursor="hand2", padx=5,
                      command=lambda p=porta: self._var_porta.set(str(p))
                      ).pack(side="left", padx=2)

        self._lbl_modalita = tk.Label(frm_porta_r, text="—",
                                       bg=P["bg_panel"], fg=P["fg_dim"],
                                       font=("Courier", 9), anchor="w")
        self._lbl_modalita.pack(anchor="w", pady=(4, 0))

        # ── Pannello info provider (appare dopo rilevamento) ──────────────────
        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=(10, 6))
        _lbl(p, "━━  INFORMAZIONI PROVIDER RILEVATO  ━━━━━━━━━━━━━━━",
             bold=True, size=9).pack(anchor="w", padx=16, pady=(0, 4))

        self._frm_provider = tk.Frame(p, bg=P["bg_alt"],
                                       relief=tk.FLAT,
                                       highlightthickness=1,
                                       highlightbackground=P["sep"])
        self._frm_provider.pack(fill="x", padx=16, pady=4)

        self._lbl_provider_nome = tk.Label(
            self._frm_provider, text="  Nessun provider rilevato",
            bg=P["bg_alt"], fg=P["fg_dim"],
            font=("Courier", 10, "bold"), anchor="w")
        self._lbl_provider_nome.pack(fill="x", padx=12, pady=(10, 2))

        self._lbl_provider_info = tk.Label(
            self._frm_provider, text="",
            bg=P["bg_alt"], fg=P["fg"],
            font=("Courier", 8), anchor="w", justify="left", wraplength=580)
        self._lbl_provider_info.pack(fill="x", padx=12, pady=(0, 4))

        self._lbl_provider_note = tk.Label(
            self._frm_provider, text="",
            bg=P["bg_alt"], fg=P["yellow"],
            font=("Courier", 8, "italic"), anchor="w", justify="left", wraplength=580)
        self._lbl_provider_note.pack(fill="x", padx=12, pady=(0, 10))

        # ── Test connessione ──────────────────────────────────────────────────
        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=(10, 6))

        frm_test = tk.Frame(p, bg=P["bg_panel"])
        frm_test.pack(fill="x", padx=16, pady=4)

        self._btn_test = tk.Button(
            frm_test, text="🔌  Testa Connessione SMTP",
            bg=P["btn_test"], fg=P["fg_bright"],
            activebackground="#2a7a3a", activeforeground="#fff",
            relief=tk.FLAT, font=("Courier", 10, "bold"),
            cursor="hand2", padx=14, pady=6,
            command=self._testa_smtp)
        self._btn_test.pack(side="left")

        self._lbl_test = tk.Label(
            frm_test, text="",
            bg=P["bg_panel"], fg=P["fg_dim"],
            font=("Courier", 9), anchor="w", wraplength=480, justify="left")
        self._lbl_test.pack(side="left", padx=12)

        # Progresso test
        self._frm_progresso = tk.Frame(p, bg=P["bg_panel"])
        self._frm_progresso.pack(fill="x", padx=16, pady=(0, 8))
        self._lbl_progresso = tk.Label(
            self._frm_progresso, text="",
            bg=P["bg_panel"], fg=P["fg_dim"],
            font=("Courier", 8), anchor="w")
        self._lbl_progresso.pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB HAMQTH
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_hamqth(self):
        p = self._tab_hamqth

        # Decorazione top
        tk.Frame(p, bg=P["accent"], height=3).pack(fill="x")

        tk.Label(p, text="📡  HamQTH — Banca dati callsign",
                 bg=P["bg_panel"], fg=P["accent"],
                 font=("Georgia", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 2))

        tk.Label(p,
                 text="HamQTH è una banca dati di callsign radioamatoriali.\n"
                      "Le credenziali permettono di arricchire i record QSL\n"
                      "con nome, QTH, grid locator ed email degli operatori.",
                 bg=P["bg_panel"], fg=P["fg"],
                 font=("Courier", 9), justify="left", anchor="w").pack(
            anchor="w", padx=16, pady=(0, 12))

        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=4)

        # Utente
        frm_u = tk.Frame(p, bg=P["bg_panel"]); frm_u.pack(fill="x", padx=16, pady=6)
        _lbl(frm_u, "Utente HamQTH  (callsign):").pack(anchor="w")
        self._var_hqth_user = tk.StringVar()
        e_u = tk.Entry(frm_u, textvariable=self._var_hqth_user,
                       font=("Courier", 11), width=30)
        _style_entry(e_u)
        e_u.pack(anchor="w", pady=(2, 0), ipady=5)

        # Password HamQTH
        frm_hp = tk.Frame(p, bg=P["bg_panel"]); frm_hp.pack(fill="x", padx=16, pady=6)
        _lbl(frm_hp, "Password HamQTH:").pack(anchor="w")
        frm_hp2 = tk.Frame(frm_hp, bg=P["bg_panel"]); frm_hp2.pack(fill="x")
        self._var_hqth_pass = tk.StringVar()
        self._e_hqth_pass = tk.Entry(frm_hp2, textvariable=self._var_hqth_pass,
                                      show="●", font=("Courier", 11), width=28)
        _style_entry(self._e_hqth_pass)
        self._e_hqth_pass.pack(side="left", ipady=5)
        self._var_mostra_hqth = tk.BooleanVar(value=False)
        tk.Checkbutton(frm_hp2, text="mostra",
                       variable=self._var_mostra_hqth,
                       command=self._toggle_hqth_pw,
                       bg=P["bg_panel"], fg=P["fg_dim"],
                       selectcolor=P["bg_alt"],
                       activebackground=P["bg_panel"],
                       font=("Courier", 8),
                       cursor="hand2").pack(side="left", padx=8)

        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=(16, 8))

        # Info
        frm_link = tk.Frame(p, bg=P["bg_alt"],
                             highlightthickness=1,
                             highlightbackground=P["sep"])
        frm_link.pack(fill="x", padx=16, pady=4)

        tk.Label(frm_link,
                 text="ℹ  Registrati gratuitamente su https://www.hamqth.com/\n"
                      "   Il tuo callsign è l'username di accesso.\n"
                      "   Senza credenziali l'arricchimento automatico è disabilitato.",
                 bg=P["bg_alt"], fg=P["fg"],
                 font=("Courier", 8), justify="left", anchor="w").pack(
            padx=12, pady=10)

        # Abilita/disabilita sezione
        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=(12, 4))
        self._var_hqth_abilitato = tk.BooleanVar(value=True)
        ttk.Checkbutton(p,
                        text="  Abilita ricerca HamQTH durante importazione ADIF",
                        variable=self._var_hqth_abilitato).pack(
            anchor="w", padx=16, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB UI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_ui(self):
        p = self._tab_ui

        tk.Frame(p, bg=P["accent"], height=3).pack(fill="x")

        tk.Label(p, text="🎨  Preferenze Interfaccia",
                 bg=P["bg_panel"], fg=P["accent"],
                 font=("Georgia", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 2))

        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=8)

        # Tema
        frm_t = tk.Frame(p, bg=P["bg_panel"]); frm_t.pack(fill="x", padx=16, pady=6)
        _lbl(frm_t, "Tema interfaccia:").pack(anchor="w")
        self._var_tema = tk.StringVar(value="scuro")
        for val, lab in [("scuro", "🌙  Scuro"), ("chiaro", "☀  Chiaro")]:
            tk.Radiobutton(frm_t, text=lab, variable=self._var_tema, value=val,
                           bg=P["bg_panel"], fg=P["fg"],
                           selectcolor=P["bg_alt"],
                           activebackground=P["bg_panel"],
                           activeforeground=P["accent"],
                           font=("Courier", 9),
                           cursor="hand2").pack(anchor="w", padx=8, pady=2)

        tk.Frame(p, bg=P["sep"], height=1).pack(fill="x", padx=16, pady=8)

        # Sezioni collassabili
        self._collapsed_sections = {}
        
        # Sezione Moduli Python
        self._crea_sezione_collassabile(p, "MODULI PYTHON", "modules")
        
        # Sezione Files ADIF
        self._crea_sezione_collassabile(p, "FILES ADIF", "adif")
        
        # Sezione Installazione Moduli
        self._crea_sezione_collassabile(p, "INSTALLAZIONE MODULI", "install")

    # ── Sfoglia path ──────────────────────────────────────────────────────────
    def _sfoglia_path(self, var: tk.StringVar):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Seleziona file ADIF",
            filetypes=[("ADIF files", "*.adi *.adif"), ("Tutti", "*.*")])
        if path:
            var.set(path)

    def _sfoglia_py_file(self, var: tk.StringVar):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Seleziona file Python",
            filetypes=[("Python files", "*.py"), ("Tutti", "*.*")])
        if path:
            # Salva il percorso completo per evitare duplicazioni
            var.set(path)

    # ══════════════════════════════════════════════════════════════════════════
    # SEZIONI COLLASSABILI
    # ══════════════════════════════════════════════════════════════════════════
    def _crea_sezione_collassabile(self, parent, titolo, section_id):
        """Crea una sezione collassabile con freccia"""
        # Container principale
        container = tk.Frame(parent, bg=P["bg_panel"])
        container.pack(fill="x", padx=16, pady=4)
        
        # Header con freccia e titolo
        header = tk.Frame(container, bg=P["bg_panel"])
        header.pack(fill="x")
        
        # Freccia (cliccabile)
        arrow_var = tk.StringVar(value="▼")
        arrow_btn = tk.Label(header, textvariable=arrow_var,
                           bg=P["bg_panel"], fg=P["accent"],
                           font=("Courier", 10, "bold"),
                           cursor="hand2")
        arrow_btn.pack(side="left", padx=(0, 8))
        
        # Titolo
        title_label = tk.Label(header, text=f"━━  {titolo}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                             bg=P["bg_panel"], fg=P["accent"],
                             font=("Courier", 9, "bold"))
        title_label.pack(side="left")
        
        # Frame content (nascosto/mostrato)
        content_frame = tk.Frame(container, bg=P["bg_panel"])
        
        # Inizialmente collassato
        self._collapsed_sections[section_id] = {
            'collapsed': False,
            'arrow': arrow_var,
            'content': content_frame
        }
        
        # Toggle al click sulla freccia o sul titolo
        def toggle_section(event=None):
            state = self._collapsed_sections[section_id]
            state['collapsed'] = not state['collapsed']
            
            if state['collapsed']:
                state['arrow'].set("▶")
                content_frame.pack_forget()
            else:
                state['arrow'].set("▼")
                content_frame.pack(fill="x", pady=(8, 0))
                # Popola il contenuto solo quando viene espanso
                if section_id == "modules":
                    self._popola_sezione_moduli(content_frame)
                elif section_id == "adif":
                    self._popola_sezione_adif(content_frame)
                elif section_id == "install":
                    self._popola_sezione_installazione(content_frame)
        
        arrow_btn.bind("<Button-1>", toggle_section)
        title_label.bind("<Button-1>", toggle_section)
        
        # Espandi automaticamente all'avvio
        toggle_section()
    
    def _popola_sezione_moduli(self, parent):
        """Popola dinamicamente la sezione moduli Python"""
        # Inizializza il dizionario se non esiste
        if not hasattr(self, '_var_modules'):
            self._var_modules = {}
        
        # Carica i moduli dal config o usa default
        moduli_config = self._get_moduli_config()
        
        # Container per i moduli
        modules_container = tk.Frame(parent, bg=P["bg_panel"])
        modules_container.pack(fill="x")
        
        # Pulsante per aggiungere nuovo modulo
        add_frame = tk.Frame(modules_container, bg=P["bg_panel"])
        add_frame.pack(fill="x", pady=(0, 8))
        
        tk.Button(add_frame, text="+ Aggiungi Modulo",
                  bg=P["accent"], fg="#fff",
                  activebackground=P["bg_alt"], activeforeground="#fff",
                  relief=tk.FLAT, font=("Courier", 9, "bold"),
                  cursor="hand2", padx=8, pady=4,
                  command=self._aggiungi_modulo).pack(side="right")
        
        # Frame per i moduli esistenti
        self._modules_frame = tk.Frame(modules_container, bg=P["bg_panel"])
        self._modules_frame.pack(fill="x")
        
        # Crea i campi per i moduli esistenti
        for chiave, (nome_file, descrizione) in moduli_config.items():
            self._crea_campo_modulo(self._modules_frame, chiave, nome_file, descrizione)
        
        # Aggiungi campo per modello JSON default
        self._crea_campo_modello_json(modules_container)
    
    def _popola_sezione_adif(self, parent):
        """Popola la sezione files ADIF"""
        # Inizializza il dizionario se non esiste
        if not hasattr(self, '_var_paths'):
            self._var_paths = {}
        
        programmi = [
            ("JTDX",     "JTDX"),
            ("WSJTX",    "WSJT-X"),
            ("MHSV",     "MHSV"),
            ("DECODIUM", "Decodium"),
        ]
        
        for chiave, nome in programmi:
            frm = tk.Frame(parent, bg=P["bg_panel"]); frm.pack(fill="x", pady=3)
            _lbl(frm, f"{nome}:").pack(anchor="w")
            frm2 = tk.Frame(frm, bg=P["bg_panel"]); frm2.pack(fill="x")
            var = tk.StringVar()
            self._var_paths[chiave] = var
            e = tk.Entry(frm2, textvariable=var, font=("Courier", 8), width=50)
            _style_entry(e)
            e.pack(side="left", fill="x", expand=True, ipady=3)
            tk.Button(frm2, text="📂",
                      bg=P["bg_alt"], fg=P["fg_dim"],
                      activebackground=P["accent"], activeforeground="#fff",
                      relief=tk.FLAT, cursor="hand2",
                      command=lambda v=var: self._sfoglia_path(v)
                      ).pack(side="left", padx=3)
    
    def _popola_sezione_installazione(self, parent):
        """Popola la sezione installazione moduli OCR"""
        # Container principale
        install_container = tk.Frame(parent, bg=P["bg_panel"])
        install_container.pack(fill="x")
        
        # Info OCR
        info_frame = tk.Frame(install_container, bg=P["bg_alt"],
                             highlightthickness=1,
                             highlightbackground=P["sep"])
        info_frame.pack(fill="x", pady=(0, 12))
        
        tk.Label(info_frame,
                 text="🔍  MODULI OCR PER ESTRAZIONE LOCATOR\n\n"
                      "Per abilitare l'estrazione automatica dei locator Maidenhead\n"
                      "dalle immagini delle mappe, sono necessari due componenti:\n\n"
                      "1. Tesseract OCR (motore di riconoscimento testo)\n"
                      "2. Pytesseract (interfaccia Python per Tesseract)\n\n"
                      "Questi moduli permettono di 'leggere' i locator scritti\n"
                      "sulle immagini delle mappe e calcolare le distanze automaticamente.",
                 bg=P["bg_alt"], fg=P["fg"],
                 font=("Courier", 9), justify="left", anchor="w").pack(
            padx=12, pady=12)
        
        # Stato installazione
        status_frame = tk.Frame(install_container, bg=P["bg_panel"])
        status_frame.pack(fill="x", pady=(0, 12))
        
        tk.Label(status_frame, text="STATO INSTALLAZIONE:",
                bg=P["bg_panel"], fg=P["accent"],
                font=("Courier", 10, "bold")).pack(anchor="w")
        
        # Controlla Tesseract
        self._lbl_tesseract_status = tk.Label(status_frame, text="Controllo Tesseract...",
                                            bg=P["bg_panel"], fg=P["fg_dim"],
                                            font=("Courier", 9))
        self._lbl_tesseract_status.pack(anchor="w", padx=(20, 0), pady=2)
        
        # Controlla Pytesseract
        self._lbl_pytesseract_status = tk.Label(status_frame, text="Controllo Pytesseract...",
                                               bg=P["bg_panel"], fg=P["fg_dim"],
                                               font=("Courier", 9))
        self._lbl_pytesseract_status.pack(anchor="w", padx=(20, 0), pady=2)
        
        # Bottoni installazione
        btn_frame = tk.Frame(install_container, bg=P["bg_panel"])
        btn_frame.pack(fill="x", pady=(0, 8))
        
        # Pulsante installazione Tesseract
        self._btn_install_tesseract = tk.Button(
            btn_frame, text="📦 Installa Tesseract OCR",
            bg=P["btn_test"], fg=P["fg_bright"],
            activebackground="#2a7a3a", activeforeground="#fff",
            relief=tk.FLAT, font=("Courier", 9, "bold"),
            cursor="hand2", padx=12, pady=6,
            command=self._install_tesseract)
        self._btn_install_tesseract.pack(side="left", padx=(0, 8))
        
        # Pulsante installazione Pytesseract
        self._btn_install_pytesseract = tk.Button(
            btn_frame, text="🐍 Installa Pytesseract",
            bg=P["btn_test"], fg=P["fg_bright"],
            activebackground="#2a7a3a", activeforeground="#fff",
            relief=tk.FLAT, font=("Courier", 9, "bold"),
            cursor="hand2", padx=12, pady=6,
            command=self._install_pytesseract)
        self._btn_install_pytesseract.pack(side="left", padx=(0, 8))
        
        # Pulsante verifica
        tk.Button(btn_frame, text="🔄 Verifica Installazione",
                 bg=P["accent"], fg="#fff",
                 activebackground="#3a7e9e", activeforeground="#fff",
                 relief=tk.FLAT, font=("Courier", 9, "bold"),
                 cursor="hand2", padx=12, pady=6,
                 command=self._verifica_installazione_ocr).pack(side="left")
        
        # Area output comandi
        output_frame = tk.Frame(install_container, bg=P["bg_panel"])
        output_frame.pack(fill="x", pady=(8, 0))
        
        tk.Label(output_frame, text="OUTPUT COMANDI:",
                bg=P["bg_panel"], fg=P["accent"],
                font=("Courier", 10, "bold")).pack(anchor="w")
        
        self._text_output = tk.Text(output_frame, height=8, width=70,
                                   bg=P["bg_input"], fg=P["fg_bright"],
                                   font=("Courier", 8), wrap=tk.WORD)
        _style_entry(self._text_output)
        self._text_output.pack(fill="x", pady=4)
        
        # Scrollbar per il testo
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", 
                                command=self._text_output.yview)
        scrollbar.pack(side="right", fill="y")
        self._text_output.configure(yscrollcommand=scrollbar.set)
        
        # Verifica installazione all'avvio
        self._verifica_installazione_ocr()
    
    def _verifica_installazione_ocr(self):
        """Verifica lo stato di installazione dei moduli OCR"""
        self._clear_output()
        self._append_output("🔍 Verifica installazione moduli OCR...\n")
        
        # Verifica Tesseract
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.split('\n')[0] if result.stdout else "Installato"
                self._lbl_tesseract_status.config(
                    text=f"✅ Tesseract: {version}", fg=P["green"])
                self._btn_install_tesseract.config(state=tk.DISABLED)
                self._append_output(f"✅ Tesseract OCR trovato: {version}\n")
            else:
                self._lbl_tesseract_status.config(
                    text="❌ Tesseract: Non installato", fg=P["red"])
                self._btn_install_tesseract.config(state=tk.NORMAL)
                self._append_output("❌ Tesseract OCR non trovato\n")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._lbl_tesseract_status.config(
                text="❌ Tesseract: Non installato", fg=P["red"])
            self._btn_install_tesseract.config(state=tk.NORMAL)
            self._append_output("❌ Tesseract OCR non trovato\n")
        
        # Verifica Pytesseract
        try:
            import pytesseract
            self._lbl_pytesseract_status.config(
                text="✅ Pytesseract: Installato", fg=P["green"])
            self._btn_install_pytesseract.config(state=tk.DISABLED)
            self._append_output("✅ Pytesseract installato correttamente\n")
        except ImportError:
            self._lbl_pytesseract_status.config(
                text="❌ Pytesseract: Non installato", fg=P["red"])
            self._btn_install_pytesseract.config(state=tk.NORMAL)
            self._append_output("❌ Pytesseract non installato\n")
        except Exception as e:
            self._lbl_pytesseract_status.config(
                text=f"⚠️ Pytesseract: Errore - {str(e)}", fg=P["yellow"])
            self._btn_install_pytesseract.config(state=tk.NORMAL)
            self._append_output(f"⚠️ Errore Pytesseract: {e}\n")
        
        self._append_output("\n🏁 Verifica completata!")
    
    def _install_tesseract(self):
        """Installa Tesseract OCR in base al sistema operativo"""
        self._clear_output()
        self._append_output("📦 Inizio installazione Tesseract OCR...\n")
        
        system = platform.system().lower()
        
        if system == "linux":
            # Prova con apt (Debian/Ubuntu)
            if self._check_command_exists("apt"):
                self._append_output("🐧 Sistema Linux rilevato, utilizzo apt...")
                self._run_command_with_sudo(["apt", "update"], "Aggiornamento repository...")
                self._run_command_with_sudo(["apt", "install", "-y", "tesseract-ocr"], 
                                          "Installazione Tesseract OCR...")
            elif self._check_command_exists("dnf"):
                self._append_output("🐧 Sistema Linux rilevato, utilizzo dnf...")
                self._run_command_with_sudo(["dnf", "install", "-y", "tesseract"], 
                                          "Installazione Tesseract OCR...")
            elif self._check_command_exists("yum"):
                self._append_output("🐧 Sistema Linux rilevato, utilizzo yum...")
                self._run_command_with_sudo(["yum", "install", "-y", "tesseract"], 
                                          "Installazione Tesseract OCR...")
            else:
                self._append_output("❌ Gestore pacchetti non riconosciuto.\n"
                                   "Installa manualmente Tesseract OCR:\n"
                                   "Ubuntu/Debian: sudo apt-get install tesseract-ocr\n"
                                   "Fedora: sudo dnf install tesseract\n"
                                   "CentOS: sudo yum install tesseract")
        
        elif system == "windows":
            self._append_output("🪟 Sistema Windows rilevato.\n"
                              "Per installare Tesseract OCR su Windows:\n"
                              "1. Scarica da: https://github.com/UB-Mannheim/tesseract/wiki\n"
                              "2. Esegui l'installer\n"
                              "3. Assicurati di aggiungere Tesseract al PATH di sistema")
        
        elif system == "darwin":
            self._append_output("🍎 Sistema macOS rilevato, utilizzo Homebrew...")
            if self._check_command_exists("brew"):
                self._run_command(["brew", "install", "tesseract"], 
                                "Installazione Tesseract OCR...")
            else:
                self._append_output("❌ Homebrew non trovato.\n"
                                   "Installa Homebrew con: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        
        else:
            self._append_output(f"❌ Sistema operativo {system} non supportato automaticamente.")
        
        # Verifica dopo l'installazione
        self._append_output("\n🔄 Verifica post-installazione...")
        self.root.after(2000, self._verifica_installazione_ocr)
    
    def _install_pytesseract(self):
        """Installa Pytesseract"""
        self._clear_output()
        self._append_output("🐍 Inizio installazione Pytesseract...\n")
        
        try:
            # Prova con pip
            self._run_command([sys.executable, "-m", "pip", "install", "pytesseract"], 
                            "Installazione Pytesseract con pip...")
            
            # Se fallisce, prova con --break-system-packages
            self._append_output("⚠️ Tentativo con --break-system-packages...")
            self._run_command([sys.executable, "-m", "pip", "install", "--break-system-packages", "pytesseract"], 
                            "Installazione Pytesseract con --break-system-packages...")
            
        except Exception as e:
            self._append_output(f"❌ Errore durante l'installazione: {e}\n"
                              f"Prova manualmente:\n"
                              f"pip install pytesseract\n"
                              f"oppure:\n"
                              f"pip install --break-system-packages pytesseract")
        
        # Verifica dopo l'installazione
        self._append_output("\n🔄 Verifica post-installazione...")
        self.root.after(2000, self._verifica_installazione_ocr)
    
    def _check_command_exists(self, command):
        """Verifica se un comando esiste nel sistema"""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _run_command(self, cmd, description=""):
        """Esegue un comando e mostra l'output"""
        if description:
            self._append_output(f"📋 {description}")
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True,
                                     universal_newlines=True)
            
            # Leggi l'output in tempo reale
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self._append_output(output.strip())
            
            return_code = process.poll()
            if return_code == 0:
                self._append_output("✅ Completato con successo!")
            else:
                self._append_output(f"❌ Errore (codice: {return_code})")
                
        except Exception as e:
            self._append_output(f"❌ Errore esecuzione: {e}")
    
    def _run_command_with_sudo(self, cmd, description=""):
        """Esegue un comando con sudo"""
        if description:
            self._append_output(f"📋 {description}")
        
        try:
            # Su Linux, usa gksudo/kdesudo se disponibili, altrimenti sudo normale
            if self._check_command_exists("gksudo"):
                cmd_with_sudo = ["gksudo"] + cmd
            elif self._check_command_exists("kdesudo"):
                cmd_with_sudo = ["kdesudo"] + cmd
            else:
                cmd_with_sudo = ["sudo"] + cmd
                self._append_output("⚠️ Verrà richiesta la password di sudo...")
            
            self._run_command(cmd_with_sudo, "")
            
        except Exception as e:
            self._append_output(f"❌ Errore esecuzione sudo: {e}")
    
    def _clear_output(self):
        """Pulisce l'area di output"""
        self._text_output.delete(1.0, tk.END)
    
    def _append_output(self, text):
        """Aggiunge testo all'area di output"""
        self._text_output.insert(tk.END, text + "\n")
        self._text_output.see(tk.END)
        self._text_output.update_idletasks()
        self.root.update_idletasks()
    
    def _get_moduli_config(self):
        """Carica la configurazione dei moduli dal file config"""
        config = configparser.ConfigParser()
        moduli_default = {
            "creatore": ("creatore_tema.py", "📥  Import ADIF → PNG"),
            "records": ("qsl_records_tema.py", "📧  Gestione email e record"),
            "editor": ("qsl_editor2_tema.py", "🎨  Editor modelli QSL"),
            "config": ("config_editor.py", "⚙  Configurazione")
        }
        
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if "MODULES" in config:
                # Combina default con quelli nel config
                result = moduli_default.copy()
                for chiave, nome_file in config["MODULES"].items():
                    if chiave in result:
                        # Mantieni la descrizione di default
                        result[chiave] = (nome_file, result[chiave][1])
                    else:
                        # Nuovo modulo, descrizione generica
                        result[chiave] = (nome_file, f"🔧  {chiave.title()}")
                return result
        
        return moduli_default
    
    def _crea_campo_modulo(self, parent, chiave, nome_file, descrizione):
        """Crea un campo per un singolo modulo"""
        frm = tk.Frame(parent, bg=P["bg_panel"]); frm.pack(fill="x", pady=3)
        
        # Header con descrizione e pulsanti
        header_frm = tk.Frame(frm, bg=P["bg_panel"])
        header_frm.pack(fill="x")
        
        tk.Label(header_frm, text=f"{descrizione}:",
                bg=P["bg_panel"], fg=P["fg"],
                font=("Courier", 9)).pack(side="left")
        
        # Frame per pulsanti azione
        btn_frame = tk.Frame(header_frm, bg=P["bg_panel"])
        btn_frame.pack(side="right")
        
        # Pulsante rinomina (per tutti)
        tk.Button(btn_frame, text="✏️",
                  bg=P["accent"], fg="#fff",
                  activebackground="#3a7e9e", activeforeground="#fff",
                  relief=tk.FLAT, font=("Courier", 8, "bold"),
                  cursor="hand2", padx=4, pady=2,
                  command=lambda k=chiave: self._rinomina_modulo(k)).pack(side="left", padx=2)
        
        # Pulsante rimuovi (solo per moduli non default)
        moduli_default = ["creatore", "records", "editor", "config"]
        if chiave not in moduli_default:
            tk.Button(btn_frame, text="✖",
                      bg=P["warn_bg"], fg=P["warn_fg"],
                      activebackground="#8a4000", activeforeground="#fff",
                      relief=tk.FLAT, font=("Courier", 8, "bold"),
                      cursor="hand2", padx=4, pady=2,
                      command=lambda k=chiave: self._rimuovi_modulo(k)).pack(side="left", padx=2)
        
        # Campo input
        frm2 = tk.Frame(frm, bg=P["bg_panel"]); frm2.pack(fill="x")
        var = tk.StringVar(value=nome_file)
        self._var_modules[chiave] = var
        e = tk.Entry(frm2, textvariable=var, font=("Courier", 8), width=60)
        _style_entry(e)
        e.pack(side="left", fill="x", expand=True, ipady=3)
        tk.Button(frm2, text="📂",
                  bg=P["bg_alt"], fg=P["fg_dim"],
                  activebackground=P["accent"], activeforeground="#fff",
                  relief=tk.FLAT, cursor="hand2",
                  command=lambda v=var: self._sfoglia_py_file(v)
                  ).pack(side="left", padx=3)
    
    def _aggiungi_modulo(self):
        """Aggiunge un nuovo modulo dinamico con ricerca"""
        # Dialog per inserire nome chiave
        dialog = tk.Toplevel(self.root)
        dialog.title("Aggiungi Modulo")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=P["bg"])
        
        tk.Label(dialog, text="Nome chiave modulo:",
                bg=P["bg"], fg=P["fg"],
                font=("Courier", 10)).pack(pady=(10, 5))
        
        key_entry = tk.Entry(dialog, font=("Courier", 10))
        key_entry.pack(padx=20, fill="x")
        key_entry.focus()
        
        # Frame per ricerca
        search_frame = tk.Frame(dialog, bg=P["bg"])
        search_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(search_frame, text="Cerca file Python:",
                bg=P["bg"], fg=P["fg"],
                font=("Courier", 9)).pack(anchor="w")
        
        path_var = tk.StringVar()
        path_entry = tk.Entry(search_frame, textvariable=path_var, font=("Courier", 8))
        path_entry.pack(fill="x", pady=(5, 0))
        
        def browse_file():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Seleziona file Python",
                filetypes=[("Python files", "*.py"), ("Tutti", "*.*")])
            if path:
                # Salva il percorso completo
                path_var.set(path)
                # Suggerisci il nome chiave dal nome file
                if not key_entry.get():
                    nome_file = os.path.basename(path)
                    chiave_suggerita = os.path.splitext(nome_file)[0].lower()
                    key_entry.delete(0, tk.END)
                    key_entry.insert(0, chiave_suggerita)
        
        tk.Button(search_frame, text="📂 Sfoglia",
                  bg=P["bg_alt"], fg=P["fg"],
                  activebackground=P["accent"], activeforeground="#fff",
                  relief=tk.FLAT, cursor="hand2",
                  command=browse_file).pack(anchor="w", pady=(5, 0))
        
        # Label per messaggi di errore
        error_label = tk.Label(dialog, text="", bg=P["bg"], fg=P["warn_fg"],
                              font=("Courier", 8))
        error_label.pack(pady=5)
        
        def verifica_chiave():
            chiave = key_entry.get().strip().lower()
            if chiave in self._var_modules:
                error_label.configure(text=f"⚠ Chiave '{chiave}' già presente!")
                return False
            elif not chiave:
                error_label.configure(text="⚠ Inserire una chiave valida!")
                return False
            else:
                error_label.configure(text="")
                return True
        
        key_entry.bind("<KeyRelease>", lambda e: verifica_chiave())
        key_entry.bind("<Return>", lambda e: conferma())
        
        def conferma():
            chiave = key_entry.get().strip().lower()
            nome_file_completo = path_var.get().strip()
            
            if not chiave or not nome_file_completo:
                messagebox.showwarning("Dati incompleti", 
                                     "Inserire sia chiave che file!", 
                                     parent=dialog)
                return
                
            if chiave in self._var_modules:
                messagebox.showwarning("Chiave duplicata", 
                                     f"La chiave '{chiave}' esiste già!", 
                                     parent=dialog)
                return
            
            descrizione = f"🔧  {chiave.title()}"
            self._crea_campo_modulo(self._modules_frame, chiave, nome_file_completo, descrizione)
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=P["bg"])
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="OK", command=conferma,
                  bg=P["accent"], fg="#fff",
                  relief=tk.FLAT, padx=15).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Annulla", command=dialog.destroy,
                  bg=P["bg_alt"], fg=P["fg"],
                  relief=tk.FLAT, padx=15).pack(side="left", padx=5)
    
    def _crea_campo_modello_json(self, parent):
        """Crea campo per selezionare modello JSON default"""
        # Separatore
        tk.Frame(parent, bg=P["sep"], height=1).pack(fill="x", pady=8)
        
        # Frame per modello JSON
        frm = tk.Frame(parent, bg=P["bg_panel"])
        frm.pack(fill="x", pady=4)
        
        tk.Label(frm, text="📄  Modello JSON default:",
                bg=P["bg_panel"], fg=P["fg"],
                font=("Courier", 9)).pack(anchor="w")
        
        frm2 = tk.Frame(frm, bg=P["bg_panel"])
        frm2.pack(fill="x")
        
        self._var_modello_json = tk.StringVar()
        e = tk.Entry(frm2, textvariable=self._var_modello_json, font=("Courier", 8), width=50)
        _style_entry(e)
        e.pack(side="left", fill="x", expand=True, ipady=3)
        
        tk.Button(frm2, text="📂",
                  bg=P["bg_alt"], fg=P["fg_dim"],
                  activebackground=P["accent"], activeforeground="#fff",
                  relief=tk.FLAT, cursor="hand2",
                  command=self._sfoglia_modello_json
                  ).pack(side="left", padx=3)
    
    def _sfoglia_modello_json(self):
        """Apre il dialog per selezionare modello JSON"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Seleziona modello JSON",
            initialdir="qsl_models",
            filetypes=[("JSON files", "*.json"), ("Tutti", "*.*")])
        if path:
            # Salva il percorso completo invece di solo il nome file
            self._var_modello_json.set(path)
            print(f"[DEBUG] Modello JSON selezionato: {path}")
    
    def _rinomina_modulo(self, chiave):
        """Rinomina una chiave modulo"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Rinomina Modulo")
        dialog.geometry("350x150")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=P["bg"])
        
        tk.Label(dialog, text=f"Nuovo nome per '{chiave}':",
                bg=P["bg"], fg=P["fg"],
                font=("Courier", 10)).pack(pady=10)
        
        entry = tk.Entry(dialog, font=("Courier", 10))
        entry.pack(padx=20, fill="x")
        entry.insert(0, chiave)
        entry.select_range(0, tk.END)
        entry.focus()
        
        error_label = tk.Label(dialog, text="", bg=P["bg"], fg=P["warn_fg"],
                              font=("Courier", 8))
        error_label.pack(pady=5)
        
        def verifica_nuovo():
            nuova_chiave = entry.get().strip().lower()
            if nuova_chiave in self._var_modules and nuova_chiave != chiave:
                error_label.configure(text=f"⚠ '{nuova_chiave}' già usata!")
                return False
            elif not nuova_chiave:
                error_label.configure(text="⚠ Nome non valido!")
                return False
            else:
                error_label.configure(text="")
                return True
        
        entry.bind("<KeyRelease>", lambda e: verifica_nuovo())
        
        def conferma():
            nuova_chiave = entry.get().strip().lower()
            if not nuova_chiave or nuova_chiave == chiave:
                dialog.destroy()
                return
                
            if nuova_chiave in self._var_modules:
                messagebox.showwarning("Duplicato", 
                                     f"La chiave '{nuova_chiave}' esiste già!", 
                                     parent=dialog)
                return
            
            # Rinomina
            valore = self._var_modules[chiave].get()
            del self._var_modules[chiave]
            self._var_modules[nuova_chiave] = tk.StringVar(value=valore)
            
            # Ricostruisci la sezione
            self._modules_frame.destroy()
            self._modules_frame = tk.Frame(self._modules_frame.master, bg=P["bg_panel"])
            self._modules_frame.pack(fill="x")
            
            moduli_config = self._get_moduli_config()
            for k, (nome_file, descrizione) in moduli_config.items():
                if k == nuova_chiave:
                    # Aggiorna descrizione
                    descrizione = f"🔧  {nuova_chiave.title()}"
                self._crea_campo_modulo(self._modules_frame, k, nome_file, descrizione)
            
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=P["bg"])
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="OK", command=conferma,
                  bg=P["accent"], fg="#fff",
                  relief=tk.FLAT, padx=15).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Annulla", command=dialog.destroy,
                  bg=P["bg_alt"], fg=P["fg"],
                  relief=tk.FLAT, padx=15).pack(side="left", padx=5)
        
        entry.bind("<Return>", lambda e: conferma())
    
    def _rimuovi_modulo(self, chiave):
        """Rimuove un modulo dinamico"""
        if messagebox.askyesno("Rimuovi Modulo", 
                              f"Rimuovere il modulo '{chiave}'?",
                              parent=self.root):
            del self._var_modules[chiave]
            # Ricostruisci la sezione
            self._modules_frame.destroy()
            self._modules_frame = tk.Frame(self._modules_frame.master, bg=P["bg_panel"])
            self._modules_frame.pack(fill="x")
            
            moduli_config = self._get_moduli_config()
            for k, (nome_file, descrizione) in moduli_config.items():
                if k != chiave:  # Salta quello rimosso
                    self._crea_campo_modulo(self._modules_frame, k, nome_file, descrizione)

    # ══════════════════════════════════════════════════════════════════════════
    # BARRA AZIONI
    # ══════════════════════════════════════════════════════════════════════════
    def _build_action_bar(self):
        bar = tk.Frame(self.root, bg=P["bg_alt"], height=54)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        tk.Frame(bar, bg=P["sep"], height=1).pack(fill="x", side="top")

        # Pulsanti destra
        tk.Button(bar, text="✖  Chiudi",
                  bg=P["btn_cancel"], fg=P["fg"],
                  activebackground="#5a3a2a", activeforeground="#fff",
                  relief=tk.FLAT, font=("Courier", 10),
                  cursor="hand2", padx=14, pady=6,
                  command=self.root.destroy).pack(side="right", padx=8, pady=8)

        tk.Button(bar, text="💾  Salva config.ini",
                  bg=P["btn_save"], fg=P["fg_bright"],
                  activebackground="#2a6ab4", activeforeground="#fff",
                  relief=tk.FLAT, font=("Courier", 10, "bold"),
                  cursor="hand2", padx=14, pady=6,
                  command=self._salva).pack(side="right", padx=4, pady=8)

        tk.Button(bar, text="🔄  Ricarica da file",
                  bg=P["bg_panel"], fg=P["fg_dim"],
                  activebackground=P["bg_panel"], activeforeground=P["accent"],
                  relief=tk.FLAT, font=("Courier", 9),
                  cursor="hand2", padx=10, pady=6,
                  command=self._carica_da_file).pack(side="left", padx=8, pady=8)

        # Stato salvataggio
        self._lbl_stato = tk.Label(bar, text="",
                                    bg=P["bg_alt"], fg=P["fg_dim"],
                                    font=("Courier", 8))
        self._lbl_stato.pack(side="left", padx=8)

    # ══════════════════════════════════════════════════════════════════════════
    # LOGICA: AUTO-RILEVAMENTO SMTP
    # ══════════════════════════════════════════════════════════════════════════
    def _on_email_cambia(self, *_):
        email  = self._var_email.get().strip()
        dati   = rileva_smtp(email)
        self._smtp_rilevato = dati

        if dati:
            # Popola automaticamente
            self._var_server.set(dati["server"])
            self._var_porta.set(str(dati["porta"]))

            # Badge
            self._lbl_badge.configure(
                text=f"✔  Provider rilevato: {dati['nome']}",
                fg=P["green"])

            # Pannello info
            modalita, descr_modalita = PORTA_INFO.get(
                dati["porta"], ("?", ""))
            modalita_ssl, descr_ssl = PORTA_INFO.get(
                dati["porta_ssl"], ("?", ""))

            info = (f"  Provider  : {dati['nome']}\n"
                    f"  Dominio   : {dati['dominio']}\n"
                    f"  Server    : {dati['server']}\n"
                    f"  Porta TLS : {dati['porta']}  → {modalita}  —  {descr_modalita}\n"
                    f"  Porta SSL : {dati['porta_ssl']}  → {modalita_ssl}")

            self._lbl_provider_nome.configure(
                text=f"  ✔  {dati['nome']}",
                fg=P["green"])
            self._lbl_provider_info.configure(text=info)
            self._lbl_provider_note.configure(
                text=f"  ⚠  {dati['note']}" if dati["note"] else "")

        elif email and "@" in email:
            dominio = dominio_da_email(email)
            self._lbl_badge.configure(
                text=f"⚠  Dominio '{dominio}' non nel database — inserisci server manualmente",
                fg=P["yellow"])
            self._lbl_provider_nome.configure(
                text=f"  ⚠  Dominio sconosciuto: {dominio}",
                fg=P["yellow"])
            self._lbl_provider_info.configure(
                text="  Inserisci manualmente server e porta nel campo sottostante.")
            self._lbl_provider_note.configure(text="")
        else:
            self._lbl_badge.configure(text="", fg=P["fg_dim"])
            self._lbl_provider_nome.configure(
                text="  Nessun provider rilevato", fg=P["fg_dim"])
            self._lbl_provider_info.configure(text="")
            self._lbl_provider_note.configure(text="")

        self._aggiorna_badge_porta()

    def _aggiorna_badge_porta(self, *_):
        try:
            porta = int(self._var_porta.get())
        except ValueError:
            self._lbl_modalita.configure(text="—", fg=P["fg_dim"])
            return
        if porta in PORTA_INFO:
            modalita, descr = PORTA_INFO[porta]
            self._lbl_modalita.configure(
                text=f"{modalita}  —  {descr}",
                fg=P["accent"])
        else:
            self._lbl_modalita.configure(
                text=f"Porta {porta} (non standard)", fg=P["yellow"])

    # ══════════════════════════════════════════════════════════════════════════
    # TEST SMTP
    # ══════════════════════════════════════════════════════════════════════════
    def _testa_smtp(self):
        if self._test_in_corso:
            return
        server   = self._var_server.get().strip()
        email    = self._var_email.get().strip()
        password = self._var_password.get()
        try:
            porta = int(self._var_porta.get())
        except ValueError:
            self._lbl_test.configure(
                text="❌  Porta non valida.", fg=P["red"])
            return

        if not server or not email or not password:
            self._lbl_test.configure(
                text="⚠  Compila email, password e server prima del test.",
                fg=P["yellow"])
            return

        self._test_in_corso = True
        self._btn_test.configure(state="disabled", text="⏳  Test in corso…")
        self._lbl_test.configure(text="Connessione in corso…", fg=P["fg_dim"])
        self._anima_progresso(0)

        def _callback(ok, msg):
            self._test_in_corso = False
            self.root.after(0, lambda: self._btn_test.configure(
                state="normal", text="🔌  Testa Connessione SMTP"))
            self.root.after(0, lambda: self._lbl_progresso.configure(text=""))
            self.root.after(0, lambda: self._lbl_test.configure(
                text=msg, fg=P["green"] if ok else P["red"]))

        test_smtp(server, porta, email, password, _callback)

    def _anima_progresso(self, step):
        if not self._test_in_corso:
            return
        dots = "·" * (step % 4 + 1)
        self._lbl_progresso.configure(
            text=f"  {dots}  Connessione a {self._var_server.get()}:{self._var_porta.get()} …")
        self.root.after(400, lambda: self._anima_progresso(step + 1))

    # ══════════════════════════════════════════════════════════════════════════
    # TOGGLE PASSWORD
    # ══════════════════════════════════════════════════════════════════════════
    def _toggle_pw(self):
        self._e_pass.configure(
            show="" if self._var_mostra_pw.get() else "●")

    def _toggle_hqth_pw(self):
        self._e_hqth_pass.configure(
            show="" if self._var_mostra_hqth.get() else "●")

    # ══════════════════════════════════════════════════════════════════════════
    # CARICA DA FILE
    # ══════════════════════════════════════════════════════════════════════════
    def _carica_da_file(self):
        cfg = carica_config()

        # SMTP
        smtp = cfg["SMTP"] if "SMTP" in cfg else {}
        self._var_email.set(smtp.get("User", ""))
        self._var_password.set(smtp.get("Password", ""))
        self._var_server.set(smtp.get("Server", ""))
        self._var_porta.set(smtp.get("Port", "587"))

        # HamQTH
        hqth = cfg["HAMQTH"] if "HAMQTH" in cfg else {}
        self._var_hqth_user.set(hqth.get("User", ""))
        self._var_hqth_pass.set(hqth.get("Password", ""))
        self._var_hqth_abilitato.set(
            hqth.get("enabled", "true").lower() != "false")

        # UI
        ui = cfg["UI"] if "UI" in cfg else {}
        self._var_tema.set(ui.get("tema", "scuro"))

        # MODULES
        modules = cfg["MODULES"] if "MODULES" in cfg else {}
        # Carica solo se le variabili dei moduli sono già state create
        if hasattr(self, '_var_modules'):
            for chiave in ("creatore", "records", "editor", "config"):
                if chiave in self._var_modules:
                    self._var_modules[chiave].set(modules.get(chiave, ""))
            # Carica anche i moduli extra dinamici
            for chiave, nome_file in modules.items():
                if chiave not in ("creatore", "records", "editor", "config"):
                    if chiave in self._var_modules:
                        self._var_modules[chiave].set(nome_file)
        
        # DEFAULTS
        defaults = cfg["DEFAULTS"] if "DEFAULTS" in cfg else {}
        if hasattr(self, '_var_modello_json'):
            self._var_modello_json.set(defaults.get("modello_json", ""))

        # PROGRAM_PATHS
        pp = cfg["PROGRAM_PATHS"] if "PROGRAM_PATHS" in cfg else {}
        # Carica solo se le variabili dei path sono già state create
        if hasattr(self, '_var_paths'):
            for chiave in ("JTDX", "WSJTX", "MHSV", "DECODIUM"):
                if chiave in self._var_paths:
                    self._var_paths[chiave].set(pp.get(chiave, ""))

        # Aggiorna il pannello provider se c'è già un'email
        self._on_email_cambia()
        self._aggiorna_badge_porta()

        esiste = os.path.exists(CONFIG_FILE)
        self._lbl_stato.configure(
            text=f"  📂  Caricato da: {CONFIG_FILE}" if esiste
            else f"  ℹ  File non trovato — verrà creato al salvataggio",
            fg=P["fg_dim"])

    # ══════════════════════════════════════════════════════════════════════════
    # SALVA
    # ══════════════════════════════════════════════════════════════════════════
    def _salva(self):
        email    = self._var_email.get().strip()
        server   = self._var_server.get().strip()
        password = self._var_password.get()
        porta    = self._var_porta.get().strip()

        # Validazione minima
        if not email:
            messagebox.showwarning("Campo mancante",
                                   "Inserisci l'indirizzo email.", parent=self.root)
            return
        if "@" not in email:
            messagebox.showwarning("Email non valida",
                                   "L'indirizzo email non sembra valido.", parent=self.root)
            return
        if not server:
            messagebox.showwarning("Campo mancante",
                                   "Inserisci il server SMTP.\n"
                                   "Se non viene rilevato automaticamente,\n"
                                   "contatta il tuo provider email.", parent=self.root)
            return
        if not porta.isdigit():
            messagebox.showwarning("Porta non valida",
                                   "La porta SMTP deve essere un numero.", parent=self.root)
            return

        cfg = carica_config()

        # SMTP
        if "SMTP" not in cfg:
            cfg["SMTP"] = {}
        cfg["SMTP"]["Server"]   = server
        cfg["SMTP"]["Port"]     = porta
        cfg["SMTP"]["User"]     = email
        cfg["SMTP"]["Password"] = password

        # HamQTH
        hqth_user = self._var_hqth_user.get().strip()
        hqth_pass = self._var_hqth_pass.get()
        if hqth_user or hqth_pass:
            if "HAMQTH" not in cfg:
                cfg["HAMQTH"] = {}
            cfg["HAMQTH"]["User"]     = hqth_user
            cfg["HAMQTH"]["Password"] = hqth_pass
            cfg["HAMQTH"]["enabled"]  = (
                "true" if self._var_hqth_abilitato.get() else "false")
        elif "HAMQTH" in cfg:
            # rimuove la sezione se entrambi i campi sono vuoti
            del cfg["HAMQTH"]

        # UI
        if "UI" not in cfg:
            cfg["UI"] = {}
        cfg["UI"]["tema"] = self._var_tema.get()

        # PROGRAM_PATHS
        if hasattr(self, '_var_paths'):
            pp_vals = {k: v.get().strip() for k, v in self._var_paths.items()}
            if any(pp_vals.values()):
                if "PROGRAM_PATHS" not in cfg:
                    cfg["PROGRAM_PATHS"] = {}
                for k, v in pp_vals.items():
                    cfg["PROGRAM_PATHS"][k] = v
            elif "PROGRAM_PATHS" in cfg:
                del cfg["PROGRAM_PATHS"]

        # MODULES
        mod_vals = {k: v.get().strip() for k, v in self._var_modules.items()}
        if any(mod_vals.values()):
            if "MODULES" not in cfg:
                cfg["MODULES"] = {}
            for k, v in mod_vals.items():
                cfg["MODULES"][k] = v
        elif "MODULES" in cfg:
            del cfg["MODULES"]
        
        # DEFAULTS
        if hasattr(self, '_var_modello_json'):
            modello_val = self._var_modello_json.get().strip()
            if modello_val:
                if "DEFAULTS" not in cfg:
                    cfg["DEFAULTS"] = {}
                cfg["DEFAULTS"]["modello_json"] = modello_val
                print(f"[DEBUG] Salvataggio modello_json: {modello_val}")
            elif "DEFAULTS" in cfg and "modello_json" in cfg["DEFAULTS"]:
                del cfg["DEFAULTS"]["modello_json"]
                print("[DEBUG] Rimozione modello_json dal config")
                # Rimuovi sezione DEFAULTS se vuota
                if not cfg["DEFAULTS"]:
                    del cfg["DEFAULTS"]
                    print("[DEBUG] Rimozione sezione DEFAULTS vuota")
            else:
                print("[DEBUG] modello_json vuoto, nessuna azione")

        try:
            success = salva_config(cfg)
            if success:
                self._lbl_stato.configure(
                    text=f"  ✔  Salvato: {CONFIG_FILE}",
                    fg=P["green"])
                # Reset colore dopo 4 secondi
                self.root.after(4000, lambda: self._lbl_stato.configure(
                    text=f"  📂  {CONFIG_FILE}", fg=P["fg_dim"]))
            else:
                raise Exception("Salvataggio fallito")
        except Exception as e:
            print(f"[ERRORE] Salvataggio config: {e}")
            messagebox.showerror("Errore salvataggio",
                                 f"Impossibile scrivere il file:\n{e}",
                                 parent=self.root)


# ══════════════════════════════════════════════════════════════════════════════
# FUNZIONE DI AVVIO (usabile come modulo dal launcher)
# ══════════════════════════════════════════════════════════════════════════════
def apri_editor_config(parent=None):
    """Apre l'editor come finestra Toplevel se parent è fornito, altrimenti come root."""
    if parent:
        win = tk.Toplevel(parent)
        win.grab_set()
        ConfigEditor(win)
        win.wait_window()
    else:
        root = tk.Tk()
        ConfigEditor(root)
        root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    ConfigEditor(root)
    root.mainloop()
