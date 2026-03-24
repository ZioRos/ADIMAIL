#!/usr/bin/env python3
"""
Calcolatore distanze per stazioni QSL
======================================
Calcola la distanza in km e miglia tra la tua stazione e quelle presenti nel log
utilizzando le coordinate Maidenhead (grid locator) dal database.
"""

import sqlite3
import math
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import configparser
from PIL import Image, ImageDraw, ImageTk, ImageFont
import re

# Verifica disponibilità OCR
try:
    import pytesseract
    TESSERACT_INSTALLED = True
    print("Pytesseract importato correttamente")
except ImportError:
    TESSERACT_INSTALLED = False
    print("Pytesseract non installato. Le funzionalità OCR saranno disabilitate.")
except Exception as e:
    TESSERACT_INSTALLED = False
    print(f"Errore durante l'importazione di pytesseract: {e}. Le funzionalità OCR saranno disabilitate.")

class GridDistanceCalculator:
    """Calcolatore distanze basato su coordinate Maidenhead"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Calcolatore Distanze QSL - ADIMAIL")
        self.root.geometry("1200x700")
        
        # Database path
        self.db_path = "/home/ros/Scrivania/qsl2/qsl_records.db"
        
        # Config path
        self.config_path = "/home/ros/ADIMAIL/config.ini"
        
        # Variabili
        self.my_grid_var = tk.StringVar(value="JN00AA")
        self.show_map_var = tk.BooleanVar(value=False)
        self.selected_station = None
        self.all_stations_coords = []
        self.distance_unit_var = tk.StringVar(value="km")
        self.map_image_path = None
        self.show_all_connections_var = tk.BooleanVar(value=True)
        self.zoom_level = 1.0
        self.map_offset_x = 0
        self.map_offset_y = 0
        self.map_locators = []  # Locator estratti dalla mappa
        
        self._load_config()
        self._create_widgets()
        self._load_grids()
    
    def _create_widgets(self):
        """Crea l'interfaccia grafica"""
        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configura grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Titolo
        title_label = ttk.Label(main_frame, text="Calcolatore Distanze QSL", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Frame per input
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # Input grid locator
        ttk.Label(input_frame, text="Il tuo Grid Locator:").pack(side=tk.LEFT, padx=(0, 10))
        grid_entry = ttk.Entry(input_frame, textvariable=self.my_grid_var, width=15)
        grid_entry.pack(side=tk.LEFT, padx=(0, 20))
        
        # Unità di distanza
        ttk.Label(input_frame, text="Unità:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Radiobutton(input_frame, text="Km", variable=self.distance_unit_var, value="km").pack(side=tk.LEFT)
        ttk.Radiobutton(input_frame, text="Miles", variable=self.distance_unit_var, value="miles").pack(side=tk.LEFT, padx=(0, 20))
        
        # Checkbox per opzioni mappa
        ttk.Checkbutton(input_frame, text="Mostra Mappa", 
                       variable=self.show_map_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(input_frame, text="Mostra Tutti i Collegamenti", 
                       variable=self.show_all_connections_var).pack(side=tk.LEFT, padx=(0, 20))
        
        # Pulsanti
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Calcola Distanze", 
                  command=self.calculate_distances).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Carica Grid dal Database", 
                  command=self.load_my_grid_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Salva Config", 
                  command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Carica Mappa", 
                  command=self.load_map_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Estrai Locator Mappa", 
                  command=self.extract_locators_from_map).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Info Mappa", 
                  command=self.show_map_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pulisci Risultati", 
                  command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Salva Mappa", 
                  command=self.save_map).pack(side=tk.LEFT, padx=5)
        
        # Frame per risultati e mappa
        results_frame = ttk.Frame(main_frame)
        results_frame.grid(row=3, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(1, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Area risultati (testo)
        text_frame = ttk.Frame(results_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        ttk.Label(text_frame, text="Risultati:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # Frame per la lista e il dettaglio
        list_frame = ttk.Frame(text_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Lista delle stazioni (selezionabili)
        self.stations_listbox = tk.Listbox(list_frame, height=15)
        self.stations_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.stations_listbox.bind('<<ListboxSelect>>', self.on_station_select)
        
        # Scrollbar per la lista
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.stations_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stations_listbox.config(yscrollcommand=scrollbar.set)
        
        # Area dettagli stazione selezionata
        detail_frame = ttk.Frame(text_frame)
        detail_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(detail_frame, text="Dettagli Stazione:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.detail_text = tk.Text(detail_frame, height=5, width=60)
        self.detail_text.pack(fill=tk.X)
        self.detail_text.config(state=tk.DISABLED)
        
        # Area mappa
        self.map_frame = ttk.Frame(results_frame)
        self.map_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        ttk.Label(self.map_frame, text="Mappa Distanze:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # Frame per controlli zoom
        zoom_frame = ttk.Frame(self.map_frame)
        zoom_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(zoom_frame, text="Zoom -", command=self.zoom_out, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT, padx=(10, 2))
        self.zoom_label = ttk.Label(zoom_frame, text="100%")
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom +", command=self.zoom_in, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Reset", command=self.reset_zoom, width=8).pack(side=tk.LEFT, padx=(10, 2))
        
        # Canvas con scrollbar per mappa zoomabile
        canvas_frame = ttk.Frame(self.map_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.map_canvas = tk.Canvas(canvas_frame, bg='#1E3A5F', width=600, height=400)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.map_canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.map_canvas.xview)
        self.map_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for scrollbars
        self.map_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Mouse events for panning
        self.map_canvas.bind("<Button-1>", self.on_map_click)
        self.map_canvas.bind("<B1-Motion>", self.on_map_drag)
        self.map_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        
        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def maidenhead_to_latlon(self, grid):
        """Converte Maidenhead grid in coordinate lat/lon"""
        if len(grid) < 2:
            return None, None
        
        # Prima lettera (campo)
        field = grid[0].upper()
        field_lon = (ord(field) - ord('A')) * 20 - 180
        field_lat = (ord(field) - ord('A')) * 10 - 90
        
        if len(grid) >= 3:
            # Seconda lettera (campo)
            field2 = grid[1].upper()
            field_lon += (ord(field2) - ord('A')) * 2
            field_lat += (ord(field2) - ord('A')) * 1
        
        if len(grid) >= 4:
            # Primo numero (quadrato)
            try:
                square = int(grid[2])
                field_lon += square * 5/60  # 5 minuti di longitudine
                field_lat += square * 2.5/60  # 2.5 minuti di latitudine
            except ValueError:
                pass
        
        if len(grid) >= 5:
            # Terza lettera (sottquadrato)
            try:
                subsquare = grid[3].upper()
                field_lon += (ord(subsquare) - ord('A')) * 30/3600  # 30 secondi
                field_lat += (ord(subsquare) - ord('A')) * 15/3600  # 15 secondi
            except (IndexError, ValueError):
                pass
        
        if len(grid) >= 6:
            # Secondo numero (sottquadrato esteso)
            try:
                extended = int(grid[4])
                field_lon += extended * 2.5/3600  # 2.5 secondi
                field_lat += extended * 1.25/3600  # 1.25 secondi
            except (IndexError, ValueError):
                pass
        
        return field_lat, field_lon
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calcola la distanza tra due punti usando la formula Haversine"""
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None, None
        
        # Converti in radianti
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Formula Haversine
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Raggio terrestre in km
        r = 6371.0
        
        distance_km = c * r
        distance_miles = distance_km * 0.621371
        
        return distance_km, distance_miles
    
    def _load_grids(self):
        """Carica i grid locator dal database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT call, grid, qth FROM qsl_records WHERE grid IS NOT NULL AND grid != '' ORDER BY call")
            self.stations = cursor.fetchall()
            
            conn.close()
            self.status_var.set(f"Caricate {len(self.stations)} stazioni dal database")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare i dati dal database:\n{e}")
            self.stations = []
    
    def load_my_grid_from_db(self):
        """Carica il grid locator più comune dal database come tua posizione"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Cerca il grid locator più frequente (potrebbe essere il tuo)
            cursor.execute("""
                SELECT grid, COUNT(*) as count 
                FROM qsl_records 
                WHERE grid IS NOT NULL AND grid != '' 
                GROUP BY grid 
                ORDER BY count DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                self.my_grid_var.set(result[0])
                self.status_var.set(f"Grid locator caricato: {result[0]}")
            else:
                messagebox.showinfo("Info", "Nessun grid locator trovato nel database")
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare il grid locator:\n{e}")
    
    def calculate_distances(self):
        """Calcola le distanze per tutte le stazioni usando il tuo locator come riferimento"""
        my_grid = self.my_grid_var.get().strip()
        if not my_grid:
            messagebox.showwarning("Attenzione", "Inserisci il tuo grid locator!")
            return
        
        self.my_lat, self.my_lon = self.maidenhead_to_latlon(my_grid)
        if self.my_lat is None:
            messagebox.showerror("Errore", "Grid locator non valido!")
            return
        
        total_distance_km = 0
        station_count = 0
        stations_with_coords = []
        
        # Pulisci lista precedente
        self.stations_listbox.delete(0, tk.END)
        
        # Combina stazioni dal database e locator della mappa
        all_stations = list(self.stations)  # Dal database
        
        # Aggiungi locator dalla mappa se presenti
        if hasattr(self, 'map_locators') and self.map_locators:
            for locator in self.map_locators:
                # Evita duplicati con le stazioni del database
                if not any(station[1] == locator for station in all_stations):
                    all_stations.append((f"MAP_{locator}", locator, ""))
        
        for call, grid, qth in all_stations:
            station_lat, station_lon = self.maidenhead_to_latlon(grid)
            if station_lat is None:
                continue
            
            # Calcola distanza dal TUO locator alla stazione
            distance_km, distance_miles = self.calculate_distance(
                self.my_lat, self.my_lon, station_lat, station_lon
            )
            
            if distance_km is not None:
                total_distance_km += distance_km
                station_count += 1
                stations_with_coords.append((call, grid, station_lat, station_lon, distance_km, qth))
                
                # Aggiungi alla lista
                distance_display = distance_km if self.distance_unit_var.get() == "km" else distance_miles
                unit_label = "km" if self.distance_unit_var.get() == "km" else "mi"
                list_entry = f"{call:<12} {grid:<8} {distance_display:8.2f} {unit_label}"
                self.stations_listbox.insert(tk.END, list_entry)
        
        # Salva tutte le coordinate per la mappa
        self.all_stations_coords = stations_with_coords
        
        if station_count > 0:
            self.status_var.set(f"Calcolate distanze da {my_grid} per {station_count} stazioni")
            
            # Disegna la mappa se richiesto
            if self.show_map_var.get():
                self.draw_world_map(self.my_lat, self.my_lon, stations_with_coords)
        else:
            self.status_var.set("Nessuna distanza calcolata")
    
    def clear_results(self):
        """Pulisce l'area dei risultati"""
        self.stations_listbox.delete(0, tk.END)
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.config(state=tk.DISABLED)
        self.map_canvas.delete("all")
        self.selected_station = None
        self.all_stations_coords = []
        self.status_var.set("Risultati puliti")
    
    def draw_world_map(self, my_lat, my_lon, stations):
        """Disegna il planisfero con le stazioni e le linee di distanza"""
        self.map_canvas.delete("all")
        
        # Dimensioni base del canvas
        base_width = 1200
        base_height = 600
        
        # Applica zoom
        canvas_width = int(base_width * self.zoom_level)
        canvas_height = int(base_height * self.zoom_level)
        
        # Carica immagine mappa se disponibile, altrimenti crea mappa Maidenhead
        if self.map_image_path and os.path.exists(self.map_image_path):
            try:
                img = Image.open(self.map_image_path).convert('RGB')
                img = img.resize((canvas_width, canvas_height), Image.LANCZOS)
            except Exception as e:
                print(f"Errore caricamento mappa: {e}")
                img = self._create_base_map(canvas_width, canvas_height)
        else:
            img = self._create_base_map(canvas_width, canvas_height)
        
        draw = ImageDraw.Draw(img)
        
        # Aggiungi overlay Maidenhead del proprio locator
        self.draw_maidenhead_overlay(draw, canvas_width, canvas_height, self.my_grid_var.get())
        
        # Converti coordinate e disegna
        my_x, my_y = self._latlon_to_canvas(my_lat, my_lon, canvas_width, canvas_height)
        
        # Disegna tutte le stazioni come punti piccoli (default)
        for call, grid, lat, lon, distance_km, qth in stations:
            station_x, station_y = self._latlon_to_canvas(lat, lon, canvas_width, canvas_height)
            
            # Punto piccolo per tutte le stazioni
            draw.ellipse([station_x-2, station_y-2, station_x+2, station_y+2], 
                         fill='#FFFF00', outline='#FF8800')
        
        # Disegna punto principale (la tua stazione)
        draw.ellipse([my_x-6, my_y-6, my_x+6, my_y+6], fill='red', outline='darkred', width=2)
        
        # Aggiungi etichetta
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            draw.text((my_x+10, my_y-8), "TU", fill='darkred', font=font)
        except:
            pass
        
        # Mostra tutti i collegamenti se richiesto
        if self.show_all_connections_var.get():
            for call, grid, lat, lon, distance_km, qth in stations:
                station_x, station_y = self._latlon_to_canvas(lat, lon, canvas_width, canvas_height)
                
                # Colore basato sulla distanza
                if distance_km < 500:
                    color = '#00FF00'  # Verde
                elif distance_km < 2000:
                    color = '#FFFF00'  # Giallo
                elif distance_km < 5000:
                    color = '#FF8800'  # Arancione
                else:
                    color = '#FF0000'  # Rosso
                
                # Disegna linea sottile
                draw.line([my_x, my_y, station_x, station_y], fill=color, width=1)
        
        # Se c'è una stazione selezionata, evidenziala
        if self.selected_station is not None and self.selected_station < len(stations):
            call, grid, lat, lon, distance_km, qth = stations[self.selected_station]
            station_x, station_y = self._latlon_to_canvas(lat, lon, canvas_width, canvas_height)
            
            # Colore basato sulla distanza
            if distance_km < 500:
                color = '#00FF00'  # Verde
            elif distance_km < 2000:
                color = '#FFFF00'  # Giallo
            elif distance_km < 5000:
                color = '#FF8800'  # Arancione
            else:
                color = '#FF0000'  # Rosso
            
            # Disegna linea spessa per la stazione selezionata
            draw.line([my_x, my_y, station_x, station_y], fill=color, width=3)
            
            # Disegna punto grande per la stazione selezionata
            draw.ellipse([station_x-5, station_y-5, station_x+5, station_y+5], 
                         fill=color, outline='black', width=2)
            
            # Aggiungi etichetta callsign
            try:
                from PIL import ImageFont
                font = ImageFont.load_default()
                draw.text((station_x+8, station_y-8), call, fill='black', font=font)
            except:
                pass
        
        # Converti in PhotoImage e mostra
        self.map_photo = ImageTk.PhotoImage(img)
        self.map_canvas.create_image(self.map_offset_x, self.map_offset_y, anchor=tk.NW, image=self.map_photo)
        
        # Aggiorna scroll region
        self.map_canvas.configure(scrollregion=self.map_canvas.bbox("all"))
        
        self.status_var.set(f"Mappa Maidenhead con {len(stations)} stazioni - Zoom: {int(self.zoom_level*100)}%")
    
    def zoom_in(self):
        """Aumenta lo zoom"""
        if self.zoom_level < 5.0:  # Max 5x zoom
            self.zoom_level *= 1.2
            self.update_zoom_display()
            self.redraw_map()
    
    def zoom_out(self):
        """Riduce lo zoom"""
        if self.zoom_level > 0.2:  # Min 0.2x zoom
            self.zoom_level /= 1.2
            self.update_zoom_display()
            self.redraw_map()
    
    def reset_zoom(self):
        """Resetta lo zoom al 100%"""
        self.zoom_level = 1.0
        self.map_offset_x = 0
        self.map_offset_y = 0
        self.update_zoom_display()
        self.redraw_map()
    
    def update_zoom_display(self):
        """Aggiorna il display del zoom"""
        self.zoom_label.config(text=f"{int(self.zoom_level*100)}%")
    
    def redraw_map(self):
        """Ridisegna la mappa con il nuovo zoom"""
        if hasattr(self, 'my_lat') and hasattr(self, 'my_lon') and self.all_stations_coords:
            self.draw_world_map(self.my_lat, self.my_lon, self.all_stations_coords)
    
    def on_map_click(self, event):
        """Inizia il drag della mappa"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def on_map_drag(self, event):
        """Esegue il drag della mappa"""
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        
        self.map_canvas.move("all", dx, dy)
        self.map_offset_x += dx
        self.map_offset_y += dy
        
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def on_mouse_wheel(self, event):
        """Gestisce zoom con rotella mouse"""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
    
    def extract_locators_from_map(self):
        """Estrae i locator Maidenhead visibili sulla mappa caricata"""
        if not self.map_image_path or not os.path.exists(self.map_image_path):
            messagebox.showwarning("Attenzione", "Carica prima un'immagine della mappa!")
            return
        
        if not TESSERACT_INSTALLED:
            messagebox.showerror("OCR Non Disponibile", 
                              "Pytesseract non è installato o non è accessibile.\n\n"
                              "Per installare:\n"
                              "pip install pytesseract\n\n"
                              "E assicurati che Tesseract OCR sia installato nel sistema:\n"
                              "Ubuntu/Debian: sudo apt-get install tesseract-ocr\n"
                              "Windows: Scarica da https://github.com/UB-Mannheim/tesseract/wiki\n"
                              "Mac: brew install tesseract")
            return
        
        try:
            # Carica l'immagine
            img = Image.open(self.map_image_path)
            
            # Converti in scala di grigi per migliorare l'OCR
            gray_img = img.convert('L')
            
            # Esegui OCR
            text = pytesseract.image_to_string(gray_img, config='--psm 6')
            
            # Estrai pattern di locator (es. JN28, AO45, etc.)
            locator_patterns = re.findall(r'\b[A-R]{2}\d{2}\b', text.upper())
            
            # Aggiungi anche pattern a 6 caratteri se presenti
            locator_patterns.extend(re.findall(r'\b[A-R]{2}\d{2}[A-X]{2}\b', text.upper()))
            
            # Rimuovi duplicati e ordina
            unique_locators = sorted(list(set(locator_patterns)))
            
            if unique_locators:
                self.map_locators = unique_locators
                
                # Aggiungi questi locator alla lista delle stazioni
                self.add_map_locators_to_stations()
                
                result_text = f"Trovati {len(unique_locators)} locator sulla mappa:\n\n"
                result_text += "\n".join(unique_locators[:20])  # Mostra primi 20
                if len(unique_locators) > 20:
                    result_text += f"\n... e altri {len(unique_locators) - 20}"
                
                messagebox.showinfo("Locator Estratti", result_text)
                self.status_var.set(f"Estratti {len(unique_locators)} locator dalla mappa")
            else:
                messagebox.showwarning("Nessun Locator", "Nessun locator Maidenhead trovato sull'immagine.")
                self.status_var.set("Nessun locator estratto")
                
        except Exception as e:
            messagebox.showerror("Errore Estrazione", f"Impossibile estrarre locator:\n{e}")
            print(f"Dettagli errore OCR: {e}")
    
    def add_map_locators_to_stations(self):
        """Aggiunge i locator estratti dalla mappa alla lista delle stazioni"""
        my_grid = self.my_grid_var.get().strip()
        if not my_grid:
            messagebox.showwarning("Attenzione", "Inserisci il tuo grid locator!")
            return
        
        my_lat, my_lon = self.maidenhead_to_latlon(my_grid)
        if my_lat is None:
            messagebox.showerror("Errore", "Grid locator non valido!")
            return
        
        # Crea una lista di stazioni dai locator della mappa
        map_stations = []
        for locator in self.map_locators:
            lat, lon = self.maidenhead_to_latlon(locator)
            if lat is not None:
                # Calcola distanza dal TUO locator al locator della mappa
                distance_km, distance_miles = self.calculate_distance(my_lat, my_lon, lat, lon)
                if distance_km is not None:
                    map_stations.append((f"MAP_{locator}", locator, lat, lon, distance_km, ""))
        
        # Aggiungi le stazioni della mappa a quelle esistenti
        self.all_stations_coords.extend(map_stations)
        
        # Aggiorna la lista visualizzata
        for call, grid, lat, lon, distance_km, qth in map_stations:
            distance_display = distance_km if self.distance_unit_var.get() == "km" else distance_km * 0.621371
            unit_label = "km" if self.distance_unit_var.get() == "km" else "mi"
            list_entry = f"{call:<12} {grid:<8} {distance_display:8.2f} {unit_label}"
            self.stations_listbox.insert(tk.END, list_entry)
        
        # Ridisegna la mappa
        if self.show_map_var.get():
            self.draw_world_map(my_lat, my_lon, self.all_stations_coords)
    
    def show_map_info(self):
        """Mostra informazioni sulle dimensioni della mappa"""
        info_text = """INFORMAZIONI MAPPA

Dimensioni Consigliate Immagine:
- Larghezza massima: 3600 pixel (6x zoom)
- Altezza massima: 1800 pixel (6x zoom)
- Formati supportati: PNG, JPG, JPEG, BMP, GIF, TIFF
- Aspect ratio ideale: 2:1 (mondo)

Zoom Disponibile:
- Minimo: 20% (0.2x)
- Massimo: 500% (5x)
- Rotella mouse: zoom in/out
- Click e drag: pan della mappa

Estrazione Locator:
- Usa "Estrai Locator Mappa" per OCR automatico
- Richiede: pip install pytesseract
- Richiede: Tesseract OCR installato
- Riconosce pattern come: JN28, AO45, etc.

Suggerimenti:
- Usa immagini ad alta risoluzione per migliori risultati
- Le mappe del mondo con proiezione Mercatore funzionano meglio
- Salva l'immagine come PNG per qualità massima
- I locator devono essere chiari e ben leggibili sull'immagine"""
        
        messagebox.showinfo("Info Mappa", info_text)
    
    def _create_base_map(self, width, height):
        """Crea la mappa base con grid Maidenhead"""
        img = Image.new('RGB', (width, height), '#1E3A5F')
        draw = ImageDraw.Draw(img)
        
        # Disegna griglia Maidenhead completa
        self._draw_maidenhead_grid(draw, width, height)
        
        # Aggiungi etichette dei campi principali
        self._add_maidenhead_labels(draw, width, height)
        
        return img
    
    def _draw_maidenhead_grid(self, draw, width, height):
        """Disegna la griglia completa dei Maidenhead locators"""
        # Campi (prime due lettere) - 20x10 gradi
        for lon_field in range(18):  # A-R (180° est)
            for lat_field in range(18):  # A-R (90° nord)
                # Coordinate del campo
                field_lon_start = lon_field * 20 - 180
                field_lat_start = lat_field * 10 - 90
                
                # Converti in coordinate canvas
                x1 = ((field_lon_start + 180) / 360) * width
                y1 = height - ((field_lat_start + 10 + 90) / 180) * height  # Corretto: y1 è in alto
                x2 = ((field_lon_start + 20 + 180) / 360) * width
                y2 = height - ((field_lat_start + 90) / 180) * height   # Corretto: y2 è in basso
                
                # Assicura che y1 <= y2 e x1 <= x2
                if y1 > y2:
                    y1, y2 = y2, y1
                if x1 > x2:
                    x1, x2 = x2, x1
                
                # Disegna bordo campo
                draw.rectangle([x1, y1, x2, y2], outline='#4A5568', width=1)
                
                # Disegna quadrati (secondo carattere numerico) - 2x1 gradi
                for square_lon in range(10):
                    for square_lat in range(10):
                        square_x1 = x1 + (square_lon * 2 / 20) * (x2 - x1)
                        square_y1 = y1 + (square_lat * 1 / 10) * (y2 - y1)
                        square_x2 = x1 + ((square_lon + 1) * 2 / 20) * (x2 - x1)
                        square_y2 = y1 + ((square_lat + 1) * 1 / 10) * (y2 - y1)
                        
                        # Disegna bordo quadrato (più sottile)
                        draw.rectangle([square_x1, square_y1, square_x2, square_y2], 
                                     outline='#2D3748', width=1)
        
        # Disegna linee principali più spesse (equatore, meridiani principali)
        # Equatore
        eq_y = height // 2
        draw.line([(0, eq_y), (width, eq_y)], fill='#E53E3E', width=2)
        
        # Meridiano di Greenwich
        greenwich_x = width // 2
        draw.line([(greenwich_x, 0), (greenwich_x, height)], fill='#E53E3E', width=2)
        
        # Antimeridiano
        anti_x = 0
        draw.line([(anti_x, 0), (anti_x, height)], fill='#E53E3E', width=2)
    
    def _add_maidenhead_labels(self, draw, width, height):
        """Aggiunge etichette dei campi Maidenhead"""
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            
            # Etichette dei campi longitudinali (sotto)
            for lon_field in range(0, 18, 2):  # Ogni 2 campi per non sovrapporre
                field_char = chr(ord('A') + lon_field)
                x = ((lon_field * 20 + 10 + 180) / 360) * width  # Centro del campo
                y = height - 5
                draw.text((x-3, y), field_char, fill='#F7FAFC', font=font)
            
            # Etichette dei campi latitudinali (a sinistra)
            for lat_field in range(0, 18, 2):  # Ogni 2 campi per non sovrapporre
                field_char = chr(ord('A') + lat_field)
                x = 5
                y = height - ((lat_field * 10 + 5 + 90) / 180) * height  # Centro del campo
                draw.text((x, y-3), field_char, fill='#F7FAFC', font=font)
                
        except:
            pass
    
    def draw_maidenhead_overlay(self, draw, width, height, my_grid):
        """Disegna overlay con evidenziazione del proprio campo Maidenhead"""
        if len(my_grid) < 2:
            return
        
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            
            # Estrai campo (prime 2 lettere)
            field = my_grid[:2].upper()
            field_lon = ord(field[0]) - ord('A')
            field_lat = ord(field[1]) - ord('A')
            
            # Coordinate del campo
            field_lon_start = field_lon * 20 - 180
            field_lat_start = field_lat * 10 - 90
            
            # Converti in coordinate canvas (corretto)
            x1 = ((field_lon_start + 180) / 360) * width
            y1 = height - ((field_lat_start + 10 + 90) / 180) * height  # y1 è in alto
            x2 = ((field_lon_start + 20 + 180) / 360) * width
            y2 = height - ((field_lat_start + 90) / 180) * height   # y2 è in basso
            
            # Assicura che y1 <= y2 e x1 <= x2
            if y1 > y2:
                y1, y2 = y2, y1
            if x1 > x2:
                x1, x2 = x2, x1
            
            # Evidenzia il proprio campo con rettangolo colorato
            draw.rectangle([x1, y1, x2, y2], outline='#10B981', width=3)
            
            # Aggiungi etichetta del campo
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            draw.text((cx-8, cy-5), field, fill='#10B981', font=font)
            
            # Se abbiamo più di 2 caratteri, evidenzia anche il quadrato
            if len(my_grid) >= 4:
                square_lon = int(my_grid[2])
                square_lat = int(my_grid[3])
                
                square_x1 = x1 + (square_lon * 2 / 20) * (x2 - x1)
                square_y1 = y1 + (square_lat * 1 / 10) * (y2 - y1)
                square_x2 = x1 + ((square_lon + 1) * 2 / 20) * (x2 - x1)
                square_y2 = y1 + ((square_lat + 1) * 1 / 10) * (y2 - y1)
                
                # Assicura che square_y1 <= square_y2
                if square_y1 > square_y2:
                    square_y1, square_y2 = square_y2, square_y1
                
                # Evidenzia il quadrato
                draw.rectangle([square_x1, square_y1, square_x2, square_y2], 
                             outline='#F59E0B', width=2)
                
                # Aggiungi etichetta del quadrato
                square_label = f"{my_grid[:2]}{my_grid[2:4]}"
                draw.text((square_x1+2, square_y1+2), square_label, fill='#F59E0B', font=font)
                
        except Exception as e:
            print(f"Errore overlay Maidenhead: {e}")
            pass
    
    def on_station_select(self, event):
        """Gestisce la selezione di una stazione dalla lista"""
        selection = self.stations_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        self.selected_station = index
        
        # Aggiorna dettagli stazione
        if index < len(self.all_stations_coords):
            call, grid, lat, lon, distance_km, qth = self.all_stations_coords[index]
            distance_miles = distance_km * 0.621371
            
            if self.distance_unit_var.get() == "km":
                distance_display = distance_km
                unit_label = "km"
            else:
                distance_display = distance_miles
                unit_label = "miles"
            
            # Ricalcola la distanza per assicurarsi che sia corretta
            my_grid = self.my_grid_var.get().strip()
            my_lat, my_lon = self.maidenhead_to_latlon(my_grid)
            if my_lat is not None:
                recalc_distance_km, recalc_distance_miles = self.calculate_distance(
                    my_lat, my_lon, lat, lon
                )
                if recalc_distance_km is not None:
                    distance_km = recalc_distance_km
                    distance_miles = recalc_distance_miles
                    distance_display = distance_km if self.distance_unit_var.get() == "km" else distance_miles
            
            detail_info = f"Callsign: {call}\n"
            detail_info += f"Grid: {grid}\n"
            detail_info += f"QTH: {qth if qth else 'N/A'}\n"
            detail_info += f"Distanza da {my_grid}: {distance_display:.2f} {unit_label}\n"
            detail_info += f"Coordinate: {lat:.4f}°, {lon:.4f}°"
            
            self.detail_text.config(state=tk.NORMAL)
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.insert(tk.END, detail_info)
            self.detail_text.config(state=tk.DISABLED)
        
        # Ridisegna la mappa se è attiva
        if self.show_map_var.get() and hasattr(self, 'my_lat') and hasattr(self, 'my_lon'):
            self.draw_world_map(self.my_lat, self.my_lon, self.all_stations_coords)
    
    def _draw_continents(self, draw, width, height):
        """Disegna contorni continenti semplificati ma più dettagliati"""
        # Ocean blue background
        draw.rectangle([0, 0, width, height], fill='#4A90E2')
        
        # Nord America - forma più realistica
        north_america = [
            (width*0.12, height*0.18), (width*0.18, height*0.15), (width*0.25, height*0.12),
            (width*0.32, height*0.15), (width*0.35, height*0.20), (width*0.38, height*0.25),
            (width*0.35, height*0.35), (width*0.30, height*0.40), (width*0.25, height*0.42),
            (width*0.20, height*0.45), (width*0.15, height*0.42), (width*0.12, height*0.35),
            (width*0.10, height*0.28), (width*0.12, height*0.18)
        ]
        draw.polygon(north_america, fill='#90EE90', outline='#228B22', width=2)
        
        # Sud America
        south_america = [
            (width*0.22, height*0.48), (width*0.25, height*0.45), (width*0.28, height*0.47),
            (width*0.30, height*0.52), (width*0.32, height*0.58), (width*0.30, height*0.65),
            (width*0.28, height*0.72), (width*0.25, height*0.78), (width*0.22, height*0.80),
            (width*0.20, height*0.75), (width*0.18, height*0.68), (width*0.18, height*0.60),
            (width*0.20, height*0.52), (width*0.22, height*0.48)
        ]
        draw.polygon(south_america, fill='#90EE90', outline='#228B22', width=2)
        
        # Europa
        europe = [
            (width*0.45, height*0.22), (width*0.48, height*0.20), (width*0.52, height*0.18),
            (width*0.55, height*0.20), (width*0.58, height*0.25), (width*0.57, height*0.30),
            (width*0.55, height*0.35), (width*0.52, height*0.38), (width*0.48, height*0.37),
            (width*0.45, height*0.35), (width*0.43, height*0.30), (width*0.43, height*0.25),
            (width*0.45, height*0.22)
        ]
        draw.polygon(europe, fill='#90EE90', outline='#228B22', width=2)
        
        # Africa
        africa = [
            (width*0.45, height*0.38), (width*0.48, height*0.35), (width*0.52, height*0.35),
            (width*0.55, height*0.38), (width*0.57, height*0.42), (width*0.58, height*0.48),
            (width*0.57, height*0.55), (width*0.55, height*0.62), (width*0.52, height*0.68),
            (width*0.48, height*0.72), (width*0.45, height*0.75), (width*0.42, height*0.70),
            (width*0.40, height*0.62), (width*0.40, height*0.55), (width*0.42, height*0.48),
            (width*0.43, height*0.42), (width*0.45, height*0.38)
        ]
        draw.polygon(africa, fill='#90EE90', outline='#228B22', width=2)
        
        # Asia
        asia = [
            (width*0.58, height*0.15), (width*0.65, height*0.12), (width*0.75, height*0.10),
            (width*0.85, height*0.12), (width*0.88, height*0.18), (width*0.90, height*0.25),
            (width*0.88, height*0.32), (width*0.85, height*0.38), (width*0.80, height*0.42),
            (width*0.75, height*0.45), (width*0.70, height*0.48), (width*0.65, height*0.50),
            (width*0.60, height*0.48), (width*0.58, height*0.42), (width*0.57, height*0.35),
            (width*0.58, height*0.25), (width*0.58, height*0.15)
        ]
        draw.polygon(asia, fill='#90EE90', outline='#228B22', width=2)
        
        # Australia
        australia = [
            (width*0.72, height*0.62), (width*0.78, height*0.60), (width*0.85, height*0.62),
            (width*0.88, height*0.68), (width*0.85, height*0.72), (width*0.78, height*0.75),
            (width*0.72, height*0.72), (width*0.70, height*0.68), (width*0.72, height*0.62)
        ]
        draw.polygon(australia, fill='#90EE90', outline='#228B22', width=2)
        
        # Groenlandia
        greenland = [
            (width*0.32, height*0.08), (width*0.38, height*0.06), (width*0.42, height*0.08),
            (width*0.40, height*0.15), (width*0.35, height*0.18), (width*0.30, height*0.15),
            (width*0.32, height*0.08)
        ]
        draw.polygon(greenland, fill='#E0E0E0', outline='#808080', width=1)
        
        # Madagascar
        madagascar = [
            (width*0.55, height*0.70), (width*0.57, height*0.68), (width*0.58, height*0.72),
            (width*0.56, height*0.75), (width*0.54, height*0.73), (width*0.55, height*0.70)
        ]
        draw.polygon(madagascar, fill='#90EE90', outline='#228B22', width=1)
        
        # Giappone
        japan = [
            (width*0.85, height*0.32), (width*0.87, height*0.30), (width*0.88, height*0.35),
            (width*0.86, height*0.38), (width*0.84, height*0.35), (width*0.85, height*0.32)
        ]
        draw.polygon(japan, fill='#90EE90', outline='#228B22', width=1)
        
        # Nuova Zelanda
        new_zealand = [
            (width*0.88, height*0.75), (width*0.90, height*0.73), (width*0.91, height*0.77),
            (width*0.89, height*0.78), (width*0.88, height*0.75)
        ]
        draw.polygon(new_zealand, fill='#90EE90', outline='#228B22', width=1)
    
    def _draw_grid(self, draw, width, height):
        """Disegna griglia di coordinate con etichette"""
        # Linee di latitudine
        for lat in range(-60, 61, 30):
            y = height - ((lat + 90) / 180) * height
            draw.line([(0, y), (width, y)], fill='#CCCCCC', width=1)
            
            # Aggiungi etichetta latitudine
            try:
                from PIL import ImageFont
                font = ImageFont.load_default()
                label = f"{lat}°"
                draw.text((5, y-5), label, fill='#333333', font=font)
            except:
                pass
            
        # Linee di longitudine
        for lon in range(-180, 181, 30):
            x = ((lon + 180) / 360) * width
            draw.line([(x, 0), (x, height)], fill='#CCCCCC', width=1)
            
            # Aggiungi etichetta longitudine
            try:
                from PIL import ImageFont
                font = ImageFont.load_default()
                label = f"{lon}°"
                draw.text((x-10, 5), label, fill='#333333', font=font)
            except:
                pass
        
        # Equatore (linea più spessa)
        eq_y = height // 2
        draw.line([(0, eq_y), (width, eq_y)], fill='#FF0000', width=2)
        
        # Meridiano di Greenwich (linea più spessa)
        greenwich_x = width // 2
        draw.line([(greenwich_x, 0), (greenwich_x, height)], fill='#FF0000', width=2)
    
    def _latlon_to_canvas(self, lat, lon, width, height):
        """Converte coordinate lat/lon in coordinate canvas"""
        x = ((lon + 180) / 360) * width
        y = height - ((lat + 90) / 180) * height
        return int(x), int(y)
    
    def save_map(self):
        """Salva la mappa come file immagine"""
        if not hasattr(self, 'map_photo'):
            messagebox.showwarning("Attenzione", "Nessuna mappa da salvare!")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Salva l'immagine corrente
                self.map_canvas.postscript(file=filename.replace('.png', '.ps'))
                messagebox.showinfo("Successo", f"Mappa salvata in {filename}")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile salvare la mappa:\n{e}")
    
    def load_map_image(self):
        """Carica un'immagine della mappa da file"""
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Seleziona immagine mappa",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"), ("All files", "*.*")]
        )
        
        if filename:
            self.map_image_path = filename
            self.status_var.set(f"Mappa caricata: {os.path.basename(filename)}")
            
            # Ridisegna la mappa se è attiva
            if self.show_map_var.get() and hasattr(self, 'my_lat') and hasattr(self, 'my_lon'):
                self.draw_world_map(self.my_lat, self.my_lon, self.all_stations_coords)
    
    def _load_config(self):
        """Carica configurazione dal file config.ini"""
        config = configparser.ConfigParser()
        
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            
            # Carica il tuo grid locator
            if "DISTANCE_CALCULATOR" in config:
                self.my_grid_var.set(config["DISTANCE_CALCULATOR"].get("my_grid", "JN00AA"))
                self.distance_unit_var.set(config["DISTANCE_CALCULATOR"].get("unit", "km"))
                self.show_all_connections_var.set(config["DISTANCE_CALCULATOR"].getboolean("show_all_connections", True))
                
                map_path = config["DISTANCE_CALCULATOR"].get("map_image_path", "")
                if map_path and os.path.exists(map_path):
                    self.map_image_path = map_path
    
    def save_config(self):
        """Salva configurazione nel file config.ini"""
        config = configparser.ConfigParser()
        
        # Leggi config esistente
        if os.path.exists(self.config_path):
            config.read(self.config_path)
        
        # Aggiungi/aggiorna sezione distance calculator
        if "DISTANCE_CALCULATOR" not in config:
            config.add_section("DISTANCE_CALCULATOR")
        
        config["DISTANCE_CALCULATOR"]["my_grid"] = self.my_grid_var.get()
        config["DISTANCE_CALCULATOR"]["unit"] = self.distance_unit_var.get()
        config["DISTANCE_CALCULATOR"]["show_all_connections"] = str(self.show_all_connections_var.get())
        
        if self.map_image_path:
            config["DISTANCE_CALCULATOR"]["map_image_path"] = self.map_image_path
        
        try:
            with open(self.config_path, 'w') as configfile:
                config.write(configfile)
            
            messagebox.showinfo("Successo", "Configurazione salvata correttamente!")
            self.status_var.set("Configurazione salvata")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare la configurazione:\n{e}")

def main():
    root = tk.Tk()
    app = GridDistanceCalculator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
