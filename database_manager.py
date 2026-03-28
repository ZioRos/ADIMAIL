#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Optional, Tuple

class DatabaseManager:
    """Gestore di database SQLite esterni con interfaccia grafica"""
    
    def __init__(self, root=None):
        """Inizializza il gestore database"""
        self.root = root
        self.connection = None
        self.cursor = None
        self.current_db_path = None
        self.current_table = None
        self.table_data = []
        self.column_names = []
        
        # Variabili per l'interfaccia
        self.db_path_var = tk.StringVar()
        self.table_var = tk.StringVar()
        self.query_var = tk.StringVar()
        
    def create_connection_ui(self, parent_frame):
        """Crea l'interfaccia per la connessione al database"""
        # Frame principale per connessione
        conn_frame = ttk.LabelFrame(parent_frame, text="Connessione Database", padding="10")
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Riga 1: Selezione database
        ttk.Label(conn_frame, text="Database:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        
        db_entry = ttk.Entry(conn_frame, textvariable=self.db_path_var, width=50)
        db_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
        
        ttk.Button(conn_frame, text="📂 Sfoglia", 
                  command=self.browse_database).grid(row=0, column=2, padx=(0, 10), pady=5)
        ttk.Button(conn_frame, text="🔗 Connetti", 
                  command=self.connect_to_database).grid(row=0, column=3, pady=5)
        
        # Riga 2: Selezione tabella
        ttk.Label(conn_frame, text="Tabella:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        
        self.table_combo = ttk.Combobox(conn_frame, textvariable=self.table_var, 
                                       state="readonly", width=30)
        self.table_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=5)
        self.table_combo.bind("<<ComboboxSelected>>", self.on_table_selected)
        
        ttk.Button(conn_frame, text="📊 Carica Dati", 
                  command=self.load_table_data).grid(row=1, column=2, columnspan=2, pady=5)
        
        # Riga 3: Query personalizzata
        ttk.Label(conn_frame, text="Query SQL:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        
        query_entry = ttk.Entry(conn_frame, textvariable=self.query_var, width=50)
        query_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
        
        ttk.Button(conn_frame, text="▶️ Esegui", 
                  command=self.execute_custom_query).grid(row=2, column=2, pady=5)
        ttk.Button(conn_frame, text="🔄 Refresh", 
                  command=self.refresh_tables).grid(row=2, column=3, pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Nessuna connessione")
        ttk.Label(conn_frame, textvariable=self.status_var, 
                 font=("Courier", 9)).grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        conn_frame.columnconfigure(1, weight=1)
        
    def create_data_viewer_ui(self, parent_frame):
        """Crea l'interfaccia per visualizzare i dati"""
        # Frame per visualizzazione dati
        data_frame = ttk.LabelFrame(parent_frame, text="Dati Tabella", padding="10")
        data_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame per controlli
        controls_frame = ttk.Frame(data_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Conteggio record
        self.record_count_var = tk.StringVar(value="0 record")
        ttk.Label(controls_frame, textvariable=self.record_count_var, 
                 font=("Courier", 10, "bold")).pack(side=tk.LEFT)
        
        # Pulsanti azione
        ttk.Button(controls_frame, text="📥 Esporta CSV", 
                  command=self.export_to_csv).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(controls_frame, text="🔄 Ricarica", 
                  command=self.reload_data).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Treeview per dati
        columns_frame = ttk.Frame(data_frame)
        columns_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(columns_frame, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(columns_frame, orient=tk.HORIZONTAL)
        
        # Treeview
        self.data_tree = ttk.Treeview(columns_frame, 
                                     yscrollcommand=v_scrollbar.set,
                                     xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.config(command=self.data_tree.yview)
        h_scrollbar.config(command=self.data_tree.xview)
        
        # Grid layout
        self.data_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.rowconfigure(0, weight=1)
        
        # Menu contestuale
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copia Valore", command=self.copy_cell_value)
        self.context_menu.add_command(label="Copia Riga", command=self.copy_row)
        
        self.data_tree.bind("<Button-3>", self.show_context_menu)
        self.data_tree.bind("<Double-1>", self.on_row_double_click)
        
    def browse_database(self):
        """Apre il dialogo per selezionare un database SQLite"""
        file_path = filedialog.askopenfilename(
            title="Seleziona Database SQLite",
            filetypes=[("Database SQLite", "*.sqlite *.db *.sqlite3"), 
                      ("Tutti i file", "*.*")]
        )
        
        if file_path:
            self.db_path_var.set(file_path)
            
    def connect_to_database(self):
        """Connette al database SQLite selezionato"""
        db_path = self.db_path_var.get().strip()
        
        if not db_path:
            messagebox.showwarning("Attenzione", "Seleziona un database SQLite!")
            return
            
        if not os.path.exists(db_path):
            messagebox.showerror("Errore", f"Il database non esiste:\n{db_path}")
            return
            
        try:
            # Chiudi connessione precedente
            if self.connection:
                self.connection.close()
                
            # Nuova connessione
            self.connection = sqlite3.connect(db_path)
            self.cursor = self.connection.cursor()
            self.current_db_path = db_path
            
            # Carica tabelle
            self.load_tables()
            
            self.status_var.set(f"Connesso a: {os.path.basename(db_path)}")
            messagebox.showinfo("Successo", "Connessione al database stabilita!")
            
        except Exception as e:
            self.status_var.set(f"Errore connessione: {str(e)}")
            messagebox.showerror("Errore Connessione", f"Impossibile connettersi al database:\n{e}")
            
    def load_tables(self):
        """Carica la lista delle tabelle dal database"""
        if not self.connection:
            return
            
        try:
            # Query per ottenere le tabelle
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            
            tables = [row[0] for row in self.cursor.fetchall()]
            
            # Aggiorna combobox
            self.table_combo['values'] = tables
            
            if tables:
                self.table_combo.current(0)
                self.table_var.set(tables[0])
            else:
                self.table_var.set("")
                
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare le tabelle:\n{e}")
            
    def refresh_tables(self):
        """Ricarica la lista delle tabelle"""
        self.load_tables()
        self.status_var.set("Tabelle aggiornate")
        
    def on_table_selected(self, event=None):
        """Gestisce la selezione di una tabella"""
        if self.table_var.get():
            self.load_table_data()
            
    def load_table_data(self):
        """Carica i dati dalla tabella selezionata"""
        if not self.connection or not self.table_var.get():
            return
            
        table_name = self.table_var.get()
        
        try:
            # Query per ottenere i dati
            query = f"SELECT * FROM {table_name}"
            self.cursor.execute(query)
            
            self.table_data = self.cursor.fetchall()
            
            # Ottieni nomi colonne
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = self.cursor.fetchall()
            self.column_names = [col[1] for col in columns_info]
            
            # Aggiorna treeview
            self.update_treeview()
            
            # Aggiorna stato
            self.record_count_var.set(f"{len(self.table_data)} record")
            self.status_var.set(f"Caricata tabella: {table_name}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare i dati:\n{e}")
            self.status_var.set(f"Errore caricamento: {str(e)}")
            
    def execute_custom_query(self):
        """Esegue una query SQL personalizzata"""
        if not self.connection:
            messagebox.showwarning("Attenzione", "Connettiti prima a un database!")
            return
            
        query = self.query_var.get().strip()
        
        if not query:
            messagebox.showwarning("Attenzione", "Inserisci una query SQL!")
            return
            
        try:
            self.cursor.execute(query)
            
            # Determina se è una query SELECT
            if query.upper().startswith('SELECT') or query.upper().startswith('WITH'):
                self.table_data = self.cursor.fetchall()
                
                # Ottieni nomi colonne dalla descrizione del cursore
                self.column_names = [description[0] for description in self.cursor.description]
                
                # Aggiorna treeview
                self.update_treeview()
                
                # Aggiorna stato
                self.record_count_var.set(f"{len(self.table_data)} record")
                self.status_var.set(f"Query eseguita: {len(self.table_data)} righe")
            else:
                # Query di modifica (INSERT, UPDATE, DELETE)
                self.connection.commit()
                affected_rows = self.cursor.rowcount
                messagebox.showinfo("Successo", f"Query eseguita! Righe modificate: {affected_rows}")
                self.status_var.set(f"Query eseguita: {affected_rows} righe modificate")
                
                # Ricarica le tabelle se potrebbe essere cambiata la struttura
                if any(keyword in query.upper() for keyword in ['CREATE', 'DROP', 'ALTER']):
                    self.load_tables()
                    
        except Exception as e:
            messagebox.showerror("Errore Query", f"Errore nell'esecuzione della query:\n{e}")
            self.status_var.set(f"Errore query: {str(e)}")
            
    def update_treeview(self):
        """Aggiorna il treeview con i dati correnti"""
        # Pulisci treeview
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
            
        # Configura colonne
        if self.column_names:
            self.data_tree['columns'] = self.column_names
            
            # Prima colonna (tree column)
            self.data_tree['show'] = 'headings'
            
            # Configura intestazioni
            for col in self.column_names:
                self.data_tree.heading(col, text=col)
                self.data_tree.column(col, width=100, anchor=tk.W)
                
            # Aggiungi dati
            for row in self.table_data:
                # Converti None in stringa vuota per visualizzazione
                display_row = ['' if val is None else str(val) for val in row]
                self.data_tree.insert('', tk.END, values=display_row)
                
    def reload_data(self):
        """Ricarica i dati della tabella corrente"""
        if self.current_table:
            self.load_table_data()
            self.status_var.set("Dati ricaricati")
            
    def export_to_csv(self):
        """Esporta i dati correnti in formato CSV"""
        if not self.table_data:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare!")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Esporta Dati in CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                import csv
                
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Scrivi intestazioni
                    writer.writerow(self.column_names)
                    
                    # Scrivi dati
                    for row in self.table_data:
                        writer.writerow(row)
                        
                messagebox.showinfo("Successo", f"Dati esportati in:\n{file_path}")
                self.status_var.set(f"Esportato: {len(self.table_data)} record")
                
            except Exception as e:
                messagebox.showerror("Errore Esportazione", f"Impossibile esportare i dati:\n{e}")
                
    def show_context_menu(self, event):
        """Mostra il menu contestuale"""
        item = self.data_tree.identify_row(event.y)
        if item:
            self.data_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
            
    def copy_cell_value(self):
        """Copia il valore della cella selezionata"""
        selected_items = self.data_tree.selection()
        if selected_items:
            item = selected_items[0]
            column = self.data_tree.identify_column(self.data_tree.winfo_pointerx() - self.data_tree.winfo_rootx())
            if column != '#0':
                col_index = int(column[1:]) - 1
                values = self.data_tree.item(item)['values']
                if col_index < len(values):
                    self.root.clipboard_clear()
                    self.root.clipboard_append(str(values[col_index]))
                    
    def copy_row(self):
        """Copia l'intera riga selezionata"""
        selected_items = self.data_tree.selection()
        if selected_items:
            item = selected_items[0]
            values = self.data_tree.item(item)['values']
            row_text = '\t'.join(str(v) for v in values)
            self.root.clipboard_clear()
            self.root.clipboard_append(row_text)
            
    def on_row_double_click(self, event):
        """Gestisce il doppio click su una riga"""
        selected_items = self.data_tree.selection()
        if selected_items:
            item = selected_items[0]
            values = self.data_tree.item(item)['values']
            
            # Crea finestra di dettaglio
            self.show_row_details(values)
            
    def show_row_details(self, values):
        """Mostra i dettagli di una riga in una finestra separata"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title("Dettagli Riga")
        detail_window.geometry("400x300")
        
        # Frame con scrollbar
        frame = ttk.Frame(detail_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Text widget per dettagli
        text_widget = tk.Text(frame, wrap=tk.WORD, font=("Courier", 10))
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Popola con dettagli
        for i, (col_name, value) in enumerate(zip(self.column_names, values)):
            text_widget.insert(tk.END, f"{col_name}: {value}\n")
            
        text_widget.config(state=tk.DISABLED)
        
    def close_connection(self):
        """Chiude la connessione al database"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
            self.current_db_path = None
            self.current_table = None
            self.table_data = []
            self.column_names = []
            
            # Pulisci interfaccia
            self.db_path_var.set("")
            self.table_var.set("")
            self.query_var.set("")
            self.table_combo['values'] = []
            
            # Pulisci treeview
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
                
            self.status_var.set("Connessione chiusa")
            self.record_count_var.set("0 record")

def create_database_manager_window():
    """Crea una finestra standalone per il gestore database"""
    root = tk.Tk()
    root.title("Database Manager - SQLite")
    root.geometry("1000x600")
    
    # Crea gestore
    db_manager = DatabaseManager(root)
    
    # Crea interfaccia
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Frame superiore per connessione
    conn_container = ttk.Frame(main_frame)
    conn_container.pack(fill=tk.X, pady=(0, 10))
    db_manager.create_connection_ui(conn_container)
    
    # Frame inferiore per dati
    data_container = ttk.Frame(main_frame)
    data_container.pack(fill=tk.BOTH, expand=True)
    db_manager.create_data_viewer_ui(data_container)
    
    # Menu
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # Menu File
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Connetti Database", command=db_manager.connect_to_database)
    file_menu.add_command(label="Esporta CSV", command=db_manager.export_to_csv)
    file_menu.add_separator()
    file_menu.add_command(label="Esci", command=root.quit)
    
    # Menu Database
    db_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Database", menu=db_menu)
    db_menu.add_command(label="Ricarica Tabelle", command=db_manager.refresh_tables)
    db_menu.add_command(label="Ricarica Dati", command=db_manager.reload_data)
    db_menu.add_command(label="Chiudi Connessione", command=db_manager.close_connection)
    
    # Gestisci chiusura finestra
    def on_closing():
        db_manager.close_connection()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    return root, db_manager

if __name__ == "__main__":
    root, db_manager = create_database_manager_window()
    root.mainloop()
