# ADIMAIL - Manuale d'Uso Completo
**Versione 4.3 - Sistema QSL Avanzato**

---

## 📋 Indice

1. [Introduzione](#1-introduzione)
2. [Installazione e Configurazione](#2-installazione-e-configurazione)
3. [Config Editor Avanzato](#3-config-editor-avanzato)
4. [Sistema Moduli Dinamici](#4-sistema-moduli-dinamici)
5. [qsl_records - Gestione Record](#5-qsl_records---gestione-record)
6. [qsl_editor2_tema - Editor Modelli](#6-qsl_editor2_tema---editor-modelli)
7. [creatore_tema - Import ADIF](#7-creatore_tema---import-adif)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Introduzione

ADIMAIL è un sistema completo per la gestione delle cartoline QSL digitali, progettato per radioamatori. Il sistema include:

- **Gestione Record QSL**: Database completo con interfaccia grafica
- **Editor Modelli**: Creazione e modifica di layout QSL personalizzati
- **Import ADIF**: Importazione automatica da log vari programmi
- **Sistema Configurazione**: Gestione centralizzata delle impostazioni
- **Moduli Dinamici**: Architettura estensibile per funzionalità aggiuntive

### Novità Versione 4.3

- ✅ **Modello JSON Default**: Caricamento automatico del modello predefinito
- ✅ **Moduli Dinamici**: Aggiunta moduli Python personalizzati
- ✅ **Config Editor Potenziato**: Gestione avanzata configurazione
- ✅ **Allineamento Automatico**: Campi allineati intelligentemente
- ✅ **Sistema Robusto**: Salvataggio affidabile con backup

---

## 2. Installazione e Configurazione

### 2.1 Requisiti di Sistema

- Python 3.8 o superiore
- Librerie: `tkinter`, `PIL/Pillow`, `configparser`
- Sistema operativo: Linux, Windows, macOS

### 2.2 Installazione

```bash
# Clona o scarica il progetto
cd qsl_sou

# Installa le dipendenze
pip install pillow

# Avvia il launcher principale
python3 main.py
```

### 2.3 Struttura Directory

```
qsl_sou/
├── main.py                    # Launcher principale
├── config.ini                 # File configurazione
├── qsl_records.db            # Database QSL
├── qsl_models/               # Modelli JSON
├── qsl_output/               # QSL generate
├── config_editor.py          # Editor configurazione
├── qsl_records_tema.py       # Gestione record
├── qsl_editor2_tema.py       # Editor modelli
└── creatore_tema.py          # Import ADIF
```

---

## 3. Config Editor Avanzato

Il Config Editor (`config_editor.py`) è il centro di controllo del sistema, ora potenziato con nuove funzionalità.

### 3.1 Accesso

Dal launcher principale:
```
⚙  Configurazione (config.ini)
```

### 3.2 Sezioni Configurazione

#### **3.2.1 SMTP - Email**
- **Server SMTP**: Configurazione server email
- **Porta**: 587 (TLS) o 465 (SSL)
- **Credenziali**: Username e password
- **Test Connessione**: Verifica in tempo reale

#### **3.2.2 HamQTH - Lookup Online**
- **Credenziali HamQTH**: Account per lookup automatici
- **Abilita/Disabilita**: Controllo integrazione

#### **3.2.3 UI - Tema**
- **Tema Scuro/Chiaro**: Personalizzazione interfaccia

#### **3.2.4 Moduli Python - NUOVO**
Gestione dinamica dei moduli del sistema:

**Moduli Standard (non rimovibili):**
- `creatore` - Import ADIF → PNG
- `records` - Gestione email e record
- `editor` - Editor modelli QSL
- `config` - Configurazione

**Moduli Extra (aggiungibili):**
- Aggiungi moduli Python personalizzati
- Percorsi completi supportati
- Rinomina e rimuovi moduli extra

#### **3.2.5 Modello JSON Default - NUOVO**
Seleziona il modello QSL predefinito:
- **Sfoglia**: Selezione file JSON
- **Percorso Completo**: Supporta path assoluti
- **Default Automatico**: Caricato all'avvio

#### **3.2.6 Percorsi Programmi**
Configura i file log dei vari programmi:
- **JTDX**: File log JTDX
- **WSJT-X**: File log WSJT-X
- **MHSV**: File log MHSV
- **DECODIUM**: File log Decodium

### 3.3 Funzionalità Avanzate

#### **3.3.1 Aggiunta Moduli Python**
1. Clicca **"+ Testo"** o **"+ Campo DB"**
2. **Sfoglia file Python**: Seleziona il file .py
3. **Nome chiave**: Suggerito automaticamente dal nome file
4. **Controllo duplicati**: Validazione in tempo reale
5. **Conferma**: Aggiunge al menu launcher

#### **3.3.2 Gestione Moduli**
- **✏️ Rinomina**: Modifica nome chiave modulo
- **✖️ Rimuovi**: Elimina moduli extra (non standard)
- **📂 Sfoglia**: Cambia file associato

#### **3.3.3 Salvataggio Affidabile**
- **Backup Automatico**: File .backup creato prima modifiche
- **Encoding UTF-8**: Supporto caratteri internazionali
- **Flush/FileSync**: Scrittura immediata su disco
- **Debug Output**: Tracciamento operazioni

---

## 4. Sistema Moduli Dinamici

Il sistema ora supporta moduli Python personalizzati che appaiono dinamicamente nel menu.

### 4.1 Come Funziona

1. **Configurazione**: Moduli definiti in `config.ini` sezione `[MODULES]`
2. **Caricamento**: Launcher legge configurazione all'avvio
3. **Menu Dinamico**: Voci menu create automaticamente
4. **Avvio**: Subprocess Python per moduli esterni

### 4.2 Aggiunta Modulo Personalizzato

#### **4.2.1 Metodo 1: Config Editor**
1. Apri `config_editor.py`
2. Vai sezione **"Moduli Python"**
3. Clicca **"+ Testo"** o **"+ Campo DB"**
4. Seleziona file Python
5. Inserisci nome chiave
6. Conferma

#### **4.2.2 Metodo 2: Manuale**
Edita `config.ini`:
```ini
[MODULES]
creatore = creatore_tema.py
records = qsl_records_tema.py
editor = qsl_editor2_tema.py
config = config_editor.py
mio_modulo = /percorso/completo/mio_modulo.py
```

### 4.3 Struttura Modulo Personalizzato

```python
#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox

class MioModulo:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mio Modulo Personalizzato")
        self._costruisci_ui()
        
    def _costruisci_ui(self):
        tk.Label(self.root, text="Il mio modulo personalizzato").pack()
        tk.Button(self.root, text="OK", command=self.root.quit).pack()
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MioModulo()
    app.run()
```

### 4.4 Best Practices

- **Percorsi Completi**: Usa path assoluti per affidabilità
- **Error Handling**: Gestisci eccezioni gracefully
- **Logging**: Usa print() per debug output
- **Interfaccia**: Segui stile ADIMAIL (temi scuri/chiari)

---

## 5. qsl_records - Gestione Record

Il cuore del sistema per la gestione delle cartoline QSL.

### 5.1 Avvio

Dal launcher:
```
📧  Gestione email e record
```

### 5.2 Interfaccia Principale

#### **5.2.1 Barra Stato Modello**
Mostra il modello QSL attivo:
- **✅ Modello**: nome_file.json — campi — aree — sfondo
- **⚠ Nessun modello**: Modalità legacy attiva
- **📂 Carica modello**: Seleziona file JSON
- **🖊 Apri Editor**: Modifica modello corrente

#### **5.2.2 Pannello Filtri**
Filtra record per:
- **Call**: Nominativo radioamatore
- **Band**: Banda operativa
- **Mode**: Modalità trasmissione
- **Date Range**: Periodo temporale
- **QSL Sent/Received**: Stato cartolina

#### **5.2.3 Tabella Record**
Colonne principali:
- **ID**: Identificativo univoco
- **Call**: Nominativo
- **Date**: Data QSO
- **Band**: Banda
- **Mode**: Modalità
- **QSL Sent**: Stato invio
- **QSL Received**: Stato ricezione
- **QSL File**: Path immagine

### 5.3 Modello JSON Default - NUOVO

#### **5.3.1 Caricamento Automatico**
All'avvio, `qsl_records` carica automaticamente:
1. Legge `config.ini` sezione `[DEFAULTS]`
2. Carica `modello_json` se configurato
3. Prepara sfondo e campi
4. Aggiorna barra stato

#### **5.3.2 Impostazione Automatica**
Quando carichi un modello:
1. **Menu → Modello QSL → Carica modello JSON…**
2. Seleziona file JSON
3. Viene **automaticamente impostato come default**
4. Salva in `config.ini` per prossimi avvii

#### **5.3.3 Vantaggi**
- **Coerenza**: Stesso modello per tutte le sessioni
- **Produttività**: Nessuna selezione manuale necessaria
- **Centralizzazione**: Configurazione condivisa tra moduli

### 5.4 Operazioni Record

#### **5.4.1 Aggiunta Record**
1. Clicca **"+ Aggiungi"**
2. Compila campi:
   - **Call**: Nominativo (obbligatorio)
   - **Date**: Data QSO
   - **Time**: Ora QSO
   - **Band**: Banda
   - **Mode**: Modalità
   - **RST Sent/Received**: Segnali
   - **Notes**: Note aggiuntive
3. **💾 Salva**: Conferma inserimento

#### **5.4.2 Modifica Record**
1. Seleziona record dalla tabella
2. Modifica campi nel pannello destro
3. **💾 Salva**: Applica modifiche
4. **🗑 Elimina**: Rimuovi record

#### **5.4.3 Import ADIF**
1. **📥 Import ADIF**: Seleziona file .adi/.adif
2. Parsing automatico campi
3. Aggiunta massima record
4. **Conflitti**: Gestione duplicati

### 5.5 Gestione QSL

#### **5.5.1 Generazione QSL**
1. Seleziona record (singolo o multipli)
2. **🎨 Genera QSL**: Apre dialog opzioni
   - **DPI**: 300 (stampa), 150 (bassa), 96 (digitale)
   - **Bleed**: Margine di stampa (mm)
   - **Dimensioni**: 900×600 px (fisso)
3. **Conferma**: Genera file PNG

#### **5.5.2 Email QSL**
1. Seleziona record con QSL generata
2. **📧 Email**: Apre dialog composizione
3. **Destinatario**: Email automatica da database
4. **Allegati**: QSL PNG incluse
5. **Invio**: Tramite SMTP configurato

#### **5.5.3 HamQTH Lookup**
1. Seleziona record
2. **🔎 HamQTH**: Lookup automatico
3. **Dati Aggiuntivi**: QTH Locator, coordinate
4. **Integrazione**: Aggiorna record automaticamente

### 5.6 Pulizia File

#### **5.6.1 File Orfani**
- **Definizione**: PNG su disco non referenziati nel DB
- **Azione**: Elimina file orfani
- **Spazio**: Libera spazio disco

#### **5.6.2 File Referenziati**
- **Definizione**: PNG referenziati nel DB
- **Azione**: Elimina tutti i file PNG
- **Database**: Record mantengono riferimento nullo

---

## 6. qsl_editor2_tema - Editor Modelli

Editor visuale avanzato per la creazione di layout QSL personalizzati.

### 6.1 Avvio

Dal launcher:
```
🎨  Editor visuale modelli QSL
```

O da `qsl_records`:
```
🖊 Apri Editor
```

### 6.2 Interfaccia

#### **6.2.1 Area Principale**
- **Canvas**: Anteprima QSL con zoom
- **Pannello Sinistro**: Proprietà campo selezionato
- **Pannello Destro**: Lista campi e rettangoli

#### **6.2.2 Barra Menu**
- **File**: Carica/Salva modello, Carica sfondo
- **Vista**: Zoom, griglia, tema
- **Modello QSL**: Aggiungi campi, apri qsl_records
- **Genera**: Anteprima, genera QSL

### 6.3 Creazione Modello

#### **6.3.1 Sfondo**
1. **File → Carica Sfondo…**
2. Seleziona immagine PNG/JPG
3. **Dimensioni**: Verifica compatibilità 900×600px
4. **Ridimensionamento**: Opzionale se dimensioni diverse

#### **6.3.2 Campi Testo - MIGLIORATO**
**Nuove funzionalità v4.3:**

**Dimensione Default 75px:**
- Nuovi campi creati con dimensione adeguata
- Leggibilità ottimale per QSL standard
- Modificabile tramite spinbox (1-2000px)

**Allineamento Automatico:**
- **Alto**: Allinea Y al primo campo della riga superiore
- **Sinistra**: Allinea X al primo campo della riga corrente
- **Coerenza**: Layout ordinato automaticamente

**Aggiunta Campi:**
1. **"+ Testo"**: Campo testo libero
2. **"+ Campo DB"**: Campo database (call, date, band, etc.)
3. **Posizionamento**: Automatico rispetto al primo campo
4. **Proprietà**: Font, dimensione, colore, adattamento

#### **6.3.3 Proprietà Campo**
- **Testo**: Contenuto (libero o DB)
- **Font**: Arial, Times, Courier, etc.
- **Dimensione**: 75px default, modificabile
- **Colore**: Selettore colore
- **Adatta Larghezza**: Auto-ridimensiona se testo troppo lungo
- **Max Larghezza**: Percentuale larghezza massima

#### **6.3.4 Rettangoli Aree**
- **Aggiungi**: Aree rettangolari per organizzazione
- **Dimensionamento**: Maniglia ridimensionamento
- **Spostamento**: Drag & drop
- **Colore**: Personalizzabile

### 6.4 Salvataggio Modello - NUOVO

#### **6.4.1 Salvataggio Automatico Default**
Quando salvi un modello:
1. **File → Salva Modello…**
2. Seleziona percorso e nome
3. **✅ Impostato come modello default**: Conferma
4. **Automaticamente**: Salvato in `config.ini`

#### **6.4.2 Caricamento Automatico Default**
Quando carichi un modello:
1. **File → Carica Modello…**
2. Seleziona file JSON
3. **✅ Impostato come modello default**: Conferma
4. **Automaticamente**: Aggiornato in `config.ini`

#### **6.4.3 Vantaggi**
- **Coerenza**: Stesso modello in tutti i moduli
- **Produttività**: Nessuna riconfigurazione necessaria
- **Centralizzazione**: Condivisione configurazione

### 6.5 Generazione QSL

#### **6.5.1 Anteprima**
1. **Genera → Anteprima**
2. **Record Corrente**: Usa record di test
3. **Dialog Esportazione**: DPI, bleed, dimensioni
4. **Visualizzazione**: Anteprima finale

#### **6.5.2 Generazione Definitiva**
1. **Genera → Genera QSL**
2. **Record**: Seleziona da database qsl_records
3. **Opzioni**: Stessa dialog esportazione
4. **Output**: File PNG in `qsl_output/`

### 6.6 Funzionalità Avanzate

#### **6.6.1 Zoom e Navigazione**
- **Rotella Mouse**: Zoom in/out
- **Pan**: Click + drag sul canvas
- **Fit**: Adatta alla finestra
- **100%**: Zoom reale

#### **6.6.2 Allineamenti**
- **Altezza**: Allinea tutti i campi alla stessa Y
- **Sinistra**: Allinea tutti i campi alla stessa X
- **Riferimento**: Primo campo come riferimento

#### **6.6.3 Temi**
- **Scuro**: Tema scuro predefinito
- **Chiaro**: Tema chiaro alternativo
- **Persistenza**: Salvato in config.ini

---

## 7. creatore_tema - Import ADIF

Strumento per l'importazione automatica dei log ADIF da vari programmi.

### 7.1 Avvio

Dal launcher:
```
📥  Import ADIF → PNG
```

### 7.2 Configurazione Percorsi

#### **7.2.1 Programmi Supportati**
- **JTDX**: Log JTDX
- **WSJT-X**: Log WSJT-X  
- **MHSV**: Log MHSV
- **DECODIUM**: Log Decodium

#### **7.2.2 Configurazione**
1. **File → Configura Percorsi…**
2. Seleziona file log per ogni programma
3. **Salva**: Percorsi salvati in config.ini
4. **Auto-rilevamento**: Suggerimenti automatici

### 7.3 Importazione ADIF

#### **7.3.1 Processo**
1. **Seleziona File**: Sfoglia file .adi/.adif
2. **Parsing**: Analisi record ADIF
3. **Filtraggio**: Solo QSL complete
4. **Database**: Inserimento in qsl_records.db

#### **7.3.2 Campi Mappati**
- **CALL**: Nominativo
- **QSO_DATE**: Data QSO
- **TIME_ON**: Ora QSO
- **BAND**: Banda
- **MODE**: Modalità
- **RST_SENT**: RST inviato
- **RST_RCVD**: RST ricevuto
- **QSL_SENT**: Stato invio QSL
- **QSL_RCVD**: Stato ricezione QSL

#### **7.3.3 Gestione Duplicati**
- **Call + Date + Time**: Chiave univoca
- **Skip**: Ignora record esistenti
- **Update**: Aggiorna record esistenti
- **Append**: Aggiungi solo nuovi

### 7.4 Generazione QSL

#### **7.4.1 Batch Processing**
1. **Seleziona Record**: Filtra per criteri
2. **Genera Massivo**: Processa tutti i record
3. **Dialog DPI**: Impostazioni esportazione
4. **Progresso**: Barra avanzamento
5. **Output**: QSL in `qsl_output/`

#### **7.4.2 Opzioni**
- **Solo QSL Sent**: Filtra per stato invio
- **Solo QSL Received**: Filtra per stato ricezione
- **Range Date**: Periodo temporale
- **Band/Mode**: Filtri tecnici

### 7.5 HamQTH Integration

#### **7.5.1 Lookup Automatico**
1. **Configura HamQTH**: Credenziali in config.ini
2. **Batch Lookup**: Processa tutti i record
3. **Dati Aggiuntivi**: QTH locator, coordinate, griglia
4. **Update**: Aggiornamento automatico database

#### **7.5.2 Rate Limiting**
- **HamQTH Limits**: 30 richieste/minuto
- **Delay Automatico**: Rispetta limiti
- **Retry**: Gestione errori temporanei

---

## 8. Troubleshooting

### 8.1 Problemi Comuni

#### **8.1.1 Config Non Salvato**
**Sintomi**: Modifiche config non persistenti
**Soluzioni**:
- Verifica permessi scrittura file
- Controlla console per errori `[ERRORE] Salvataggio config`
- Riavvia config_editor

#### **8.1.2 Modello Non Caricato**
**Sintomi**: qsl_records non carica modello default
**Soluzioni**:
- Verifica percorso in `config.ini` sezione `[DEFAULTS]`
- Controlla esistenza file modello
- Verifica console per `[ATTENZIONE] Modello default non trovato`

#### **8.1.3 Modulo Non Appare nel Menu**
**Sintomi**: Modulo aggiunto non visibile nel launcher
**Soluzioni**:
- Riavvia launcher per ricaricare config
- Verifica sintassi `config.ini` sezione `[MODULES]`
- Controlla percorso file modulo esista

#### **8.1.4 Font Non Leggibili**
**Sintomi**: Testo QSL troppo piccolo/grande
**Soluzioni**:
- Aumenta dimensione campo in qsl_editor2_tema
- Usa dimensione 75px per nuovi campi
- Verifica DPI esportazione (300 consigliato)

### 8.2 Debug e Logging

#### **8.2.1 Console Output**
Il sistema usa output console per debug:
- `[INFO]`: Operazioni riuscite
- `[ATTENZIONE]**: Warning non critici
- `[ERRORE]`: Errori gravi
- `[DEBUG]`: Informazioni dettagliate

#### **8.2.2 File Log**
Non implementato di default, ma puoi aggiungere:
```python
import logging
logging.basicConfig(filename='adimail.log', level=logging.INFO)
```

### 8.3 Backup e Recovery

#### **8.3.1 Config Backup**
Automatico su ogni salvataggio:
- `config.ini.backup`: Backup ultimo stato
- Manuale: copia file prima modifiche importanti

#### **8.3.2 Database Backup**
```bash
# Backup database QSL
cp qsl_records.db qsl_records_backup.db
```

#### **8.3.3 Modelli Backup**
```bash
# Backup directory modelli
tar -czf qsl_models_backup.tar.gz qsl_models/
```

### 8.4 Performance

#### **8.4.1 Database Ottimizzazione**
- **Indici**: Già presenti su campi principali
- **Vacuum**: Esegui periodicamente per compattazione
- **Limit**: Usa filtri per ridurre record caricati

#### **8.4.2 Immagini QSL**
- **Compressione**: PNG già ottimizzati
- **Cache**: qsl_records mantiene cache sfondi
- **Batch**: Usa generazione massiva per molti record

### 8.5 Supporto

#### **8.5.1 Informazioni Necessarie**
Per richieste supporto, includi:
- Versione Python: `python3 --version`
- Sistema operativo: `uname -a`
- Errori console completi
- File config problematico

#### **8.5.2 Comunità**
- Forum radioamatori locali
- GitHub issues (se disponibile)
- Gruppi WhatsApp/Telegram radioamatori

---

## 📚 Appendice

### A. Riferimenti Rapidi

#### **A.1 File Configurazione**
```
config.ini
├── [SMTP]          - Configurazione email
├── [HAMQTH]        - Credenziali HamQTH
├── [UI]            - Tema interfaccia
├── [MODULES]       - Moduli Python
├── [DEFAULTS]      - Modello JSON default
└── [PROGRAM_PATHS] - Percorsi log programmi
```

#### **A.2 Comandi Utili**
```bash
# Avvio launcher
python3 main.py

# Avvio singolo modulo
python3 qsl_records_tema.py
python3 qsl_editor2_tema.py
python3 creatore_tema.py
python3 config_editor.py

# Verifica database
sqlite3 qsl_records.db ".tables"
sqlite3 qsl_records.db "SELECT COUNT(*) FROM qsl_records"
```

#### **A.3 Dimensioni Standard**
- **QSL Fisico**: 148×105 mm
- **Digitale**: 900×600 px @ 300 DPI
- **Bassa Qualità**: 900×600 px @ 150 DPI
- **Email/Web**: 900×600 px @ 96 DPI

### B. Glossario

- **ADIF**: Amateur Data Interchange Format
- **QSL**: Cartolina di conferma contatto radio
- **DPI**: Dots Per Inch (punti per pollice)
- **JSON**: JavaScript Object Notation
- **DB**: Database
- **UI**: User Interface (interfaccia utente)

### C. Sviluppo e Estensioni

#### **C.1 Struttura Modulo**
Vedi Sezione 4.3 per template modulo personalizzato.

#### **C.2 Temi Personalizzati**
Modifica `TEMI` in ogni modulo per aggiungere temi.

#### **C.3 Campi Database Personalizzati**
Aggiungi a `CAMPI_DB` in qsl_editor2_tema.py.

---

**Fine Manuale - Versione 4.3**

*Per supporto e aggiornamenti, controlla la documentazione online e i commit del progetto.*
