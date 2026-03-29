#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ADIF Mapping Manager
Gestisce le mappature dei campi ADIF in una tabella SQLite
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import configparser
import re
import os
from datetime import datetime

class ADIFMappingManager:
    def __init__(self, root):
        self.root = root
        self.root.title("ADIF Mapping Manager")
        self.root.geometry("1000x700")
        
        # Database file
        self.db_file = "qsl_records.db"
        
        # Initialize database
        self.init_mapping_table()
        
        # Current mapping data
        self.current_mapping = {}
        self.current_file = ""
        
        # Setup UI
        self.setup_ui()
        
        # Load existing mappings
        self.load_mappings_list()
    
    def ensure_adif_mappings_table(self):
        """Ensure adif_mappings table exists"""
        try:
            conn = sqlite3.connect(self.db_file)
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

    def init_mapping_table(self):
        """Initialize adif_mappings table in qsl_records.db"""
        return self.ensure_adif_mappings_table()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="File ADIF", padding="5")
        file_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(file_frame, text="Carica File ADIF", command=self.load_adif_file).pack(side=tk.LEFT, padx=(0, 5))
        self.file_label = ttk.Label(file_frame, text="Nessun file caricato")
        self.file_label.pack(side=tk.LEFT, padx=5)
        
        # Mapping selection
        mapping_frame = ttk.LabelFrame(main_frame, text="Selezione Mappatura", padding="5")
        mapping_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(mapping_frame, text="File ADIF:").pack(side=tk.LEFT, padx=(0, 5))
        self.mapping_combo = ttk.Combobox(mapping_frame, width=30, state="readonly")
        self.mapping_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.mapping_combo.bind("<<ComboboxSelected>>", self.on_mapping_selected)
        
        ttk.Button(mapping_frame, text="Nuova Mappatura", command=self.create_new_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(mapping_frame, text="Elimina Mappatura", command=self.delete_mapping).pack(side=tk.LEFT, padx=5)
        
        # ADIF Sample
        sample_frame = ttk.LabelFrame(main_frame, text="Campione Record ADIF", padding="5")
        sample_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.adif_text = tk.Text(sample_frame, height=8, width=80, wrap=tk.WORD)
        self.adif_text.pack(fill=tk.BOTH, expand=True)
        
        # Mapping area
        mapping_frame = ttk.LabelFrame(main_frame, text="Mappatura Campi", padding="5")
        mapping_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Headers
        ttk.Label(mapping_frame, text="Campo Database", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(mapping_frame, text="Campo ADIF", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(mapping_frame, text="Valore Esempio", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=2, padx=5, pady=5)
        
        # Scrollable frame for mappings
        canvas = tk.Canvas(mapping_frame, height=300)
        scrollbar = ttk.Scrollbar(mapping_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=3, sticky=(tk.N, tk.S))
        
        # Database fields
        self.db_fields = [
            'callsign', 'call', 'qsl_date', 'qso_date', 'date',
            'qsl_time', 'time_on', 'time', 'operator_name', 'name',
            'qth', 'grid_locator', 'grid', 'band', 'mode',
            'comments', 'rst_sent', 'email', 'qsl_file', 'stato', 'qsl_status',
            'sent', 'source', 'power', 'frequency_num', 'rst_received',
            'nick', 'country', 'adif', 'itu', 'cq', 'adr_name',
            'adr_street1', 'adr_city', 'adr_zip', 'adr_country',
            'lotw', 'eqsl', 'qsldirect', 'latitude', 'longitude',
            'continent', 'utc_offset', 'picture', 'iota', 'qsl_via'
        ]
        
        # Mapping entries
        self.mapping_entries = {}
        self.value_labels = {}
        
        for i, db_field in enumerate(self.db_fields):
            # Database field label
            ttk.Label(scrollable_frame, text=db_field).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            
            # ADIF field entry
            adif_var = tk.StringVar()
            adif_entry = ttk.Entry(scrollable_frame, textvariable=adif_var, width=20)
            adif_entry.grid(row=i, column=1, padx=5, pady=2)
            self.mapping_entries[db_field] = adif_var
            
            # Example value label
            value_label = ttk.Label(scrollable_frame, text="", foreground="gray")
            value_label.grid(row=i, column=2, padx=5, pady=2, sticky=tk.W)
            self.value_labels[db_field] = value_label
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Salva Mappatura", command=self.save_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Auto Mappatura", command=self.auto_map).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pulisci Mappature", command=self.clear_mappings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Usa questa Mappatura", command=self.use_mapping).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
    
    def load_adif_file(self):
        """Load ADIF file and show sample"""
        file_path = filedialog.askopenfilename(
            title="Seleziona file ADIF",
            filetypes=[("ADIF files", "*.adi *.adif"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Find first record
                records = re.split(r'<EOR>', content, flags=re.IGNORECASE)
                valid_records = [r for r in records if "<CALL:" in r.upper()]
                
                if valid_records:
                    self.adif_sample = valid_records[0]
                    self.adif_text.delete(1.0, tk.END)
                    self.adif_text.insert(1.0, self.adif_sample)
                    self.current_file = os.path.basename(file_path)
                    self.file_label.config(text=self.current_file)
                    
                    # Parse fields
                    self.parse_adif_fields()
                    self.update_example_values()
                else:
                    messagebox.showwarning("Attenzione", "Nessun record valido trovato nel file ADIF")
                    
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile leggere il file: {e}")
    
    def parse_adif_fields(self):
        """Parse ADIF fields from sample"""
        self.parsed_fields = {}
        matches = re.findall(r'<(\w+):(\d+)[^>]*>([^<]*)', self.adif_sample, re.IGNORECASE)
        for field, length, value in matches:
            self.parsed_fields[field.upper()] = value.strip()
    
    def update_example_values(self):
        """Update example value labels"""
        for db_field, value_label in self.value_labels.items():
            adif_field = self.mapping_entries[db_field].get().upper()
            if adif_field in self.parsed_fields:
                value_label.config(text=self.parsed_fields[adif_field])
            else:
                value_label.config(text="")
    
    def load_mappings_list(self):
        """Load list of existing mappings"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT file_name, mapping_date 
            FROM adif_mappings 
            ORDER BY mapping_date DESC
        ''')
        
        mappings = cursor.fetchall()
        conn.close()
        
        # Update combobox
        mapping_list = [f"{file} ({date})" for file, date in mappings]
        self.mapping_combo['values'] = mapping_list
    
    def on_mapping_selected(self, event):
        """Handle mapping selection"""
        selection = self.mapping_combo.get()
        if not selection:
            return
        
        # Extract file name from selection
        file_name = selection.split(' (')[0]
        self.current_file = file_name
        self.file_label.config(text=file_name)
        
        # Load mapping for this file
        self.load_mapping(file_name)
    
    def load_mapping(self, file_name):
        """Load mapping for specific file"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT db_field, adif_field 
            FROM adif_mappings 
            WHERE file_name = ?
        ''', (file_name,))
        
        mappings = cursor.fetchall()
        conn.close()
        
        # Clear current mapping
        self.clear_mappings()
        
        # Set mapping values
        for db_field, adif_field in mappings:
            if db_field in self.mapping_entries:
                self.mapping_entries[db_field].set(adif_field)
        
        self.update_example_values()
    
    def create_new_mapping(self):
        """Create new mapping for current file"""
        if not self.current_file:
            messagebox.showwarning("Attenzione", "Carica prima un file ADIF")
            return
        
        # Clear current mapping
        self.clear_mappings()
        
        # Set current file in combo
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.mapping_combo.set(f"{self.current_file} ({date_str})")
    
    def save_mapping(self):
        """Save current mapping to database"""
        if not self.current_file:
            messagebox.showwarning("Attenzione", "Carica prima un file ADIF")
            return
        
        # Get mapping date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # Delete existing mapping for this file
            cursor.execute('DELETE FROM adif_mappings WHERE file_name = ?', (self.current_file,))
            
            # Insert new mappings
            for db_field, entry in self.mapping_entries.items():
                adif_field = entry.get().strip()
                if adif_field:  # Only save non-empty mappings
                    cursor.execute('''
                        INSERT INTO adif_mappings (file_name, mapping_date, db_field, adif_field)
                        VALUES (?, ?, ?, ?)
                    ''', (self.current_file, date_str, db_field, adif_field))
            
            conn.commit()
            messagebox.showinfo("Successo", f"Mappatura salvata per {self.current_file}")
            
            # Refresh mappings list
            self.load_mappings_list()
            
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Errore", f"Impossibile salvare la mappatura: {e}")
        finally:
            conn.close()
    
    def delete_mapping(self):
        """Delete selected mapping"""
        selection = self.mapping_combo.get()
        if not selection:
            messagebox.showwarning("Attenzione", "Seleziona una mappatura da eliminare")
            return
        
        file_name = selection.split(' (')[0]
        
        if messagebox.askyesno("Conferma", f"Eliminare la mappatura per {file_name}?"):
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            try:
                cursor.execute('DELETE FROM adif_mappings WHERE file_name = ?', (file_name,))
                conn.commit()
                messagebox.showinfo("Successo", f"Mappatura eliminata per {file_name}")
                
                # Refresh mappings list
                self.load_mappings_list()
                
                # Clear current mapping
                self.clear_mappings()
                
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Errore", f"Impossibile eliminare la mappatura: {e}")
            finally:
                conn.close()
    
    def auto_map(self):
        """Auto-map common fields"""
        auto_mappings = {
            'callsign': 'CALL',
            'call': 'CALL', 
            'qsl_date': 'QSO_DATE',
            'qso_date': 'QSO_DATE',
            'date': 'QSO_DATE',
            'qsl_time': 'TIME_ON',
            'time_on': 'TIME_ON',
            'time': 'TIME_ON',
            'operator_name': 'NAME',
            'name': 'NAME',
            'qth': 'QTH',
            'grid_locator': 'GRIDSQUARE',
            'grid': 'GRIDSQUARE',
            'band': 'BAND',
            'mode': 'MODE',
            'comments': 'COMMENT',
            'rst_sent': 'RST_SENT',
            'email': 'EMAIL',
            'power': 'TX_PWR',
            'frequency_num': 'FREQ',
            'rst_received': 'RST_RCVD',
            'nick': 'NAME',
            'country': 'COUNTRY',
            'adif': 'ADIF',
            'itu': 'ITUZ',
            'cq': 'CQZ',
            'latitude': 'LAT',
            'longitude': 'LON'
        }
        
        for db_field, adif_field in auto_mappings.items():
            if adif_field in self.parsed_fields:
                self.mapping_entries[db_field].set(adif_field)
        
        self.update_example_values()
        messagebox.showinfo("Auto Mappatura", "Mappatura automatica completata")
    
    def clear_mappings(self):
        """Clear all mapping entries"""
        for db_field, entry in self.mapping_entries.items():
            entry.set("")
        self.update_example_values()
    
    def use_mapping(self):
        """Set this mapping as active for import"""
        if not self.current_file:
            messagebox.showwarning("Attenzione", "Seleziona o crea una mappatura")
            return
        
        # Save current mapping if not saved
        selection = self.mapping_combo.get()
        if not selection or self.current_file not in selection:
            self.save_mapping()
        
        # Set as active mapping in config
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        if not config.has_section('ADIF_SETTINGS'):
            config.add_section('ADIF_SETTINGS')
        
        config.set('ADIF_SETTINGS', 'active_mapping_file', self.current_file)
        
        with open('config.ini', 'w') as f:
            config.write(f)
        
        messagebox.showinfo("Successo", f"Mappatura per {self.current_file} impostata come attiva")
        
        # Close window
        self.root.destroy()

def get_active_mapping():
    """Get the currently active mapping from database"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    if config.has_section('ADIF_SETTINGS') and config.has_option('ADIF_SETTINGS', 'active_mapping_file'):
        active_file = config.get('ADIF_SETTINGS', 'active_mapping_file')
        
        conn = sqlite3.connect('qsl_records.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT db_field, adif_field 
            FROM adif_mappings 
            WHERE file_name = ?
        ''', (active_file,))
        
        mappings = cursor.fetchall()
        conn.close()
        
        return dict(mappings)
    
    return {}

def main():
    root = tk.Tk()
    app = ADIFMappingManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
