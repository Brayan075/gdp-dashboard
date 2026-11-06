"""
SALUD RURAL DIGITAL
Prototipo académico de bajo nivel - Reto 4
Python 3.10+ | Tkinter | SQLite

AVISO:
- Aplicación demostrativa; no usar con datos médicos reales.
- No reemplaza un sistema clínico ni ofrece diagnóstico o telemedicina real.
- La conectividad y la sincronización se simulan localmente.
"""

import csv
import os
import sqlite3
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date
from pathlib import Path

APP_NAME = "Salud Rural Digital"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "salud_rural_digital.db"
EXPORT_DIR = BASE_DIR

# Paleta visual
BG = "#F3F6FA"
NAVY = "#14243A"
NAVY_LIGHT = "#203852"
TEAL = "#13A89E"
TEAL_DARK = "#0B817A"
WHITE = "#FFFFFF"
TEXT = "#263445"
MUTED = "#718096"
BORDER = "#DCE4ED"
GREEN = "#16865B"
RED = "#C64B4B"
AMBER = "#C18422"


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                age INTEGER,
                phone TEXT,
                community TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_document TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clinical_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_document TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_sync (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                synced INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                sample_number INTEGER NOT NULL,
                response_ms REAL,
                result TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def add_patient(self, document, name, age, phone, community):
        self.conn.execute(
            """INSERT INTO patients
            (document, name, age, phone, community, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (document, name, age, phone, community, now_text())
        )
        self.conn.commit()

    def patients(self):
        return self.conn.execute(
            "SELECT * FROM patients ORDER BY name"
        ).fetchall()

    def get_patient(self, document):
        return self.conn.execute(
            "SELECT * FROM patients WHERE document=?", (document,)
        ).fetchone()

    def add_appointment(self, document, name, appt_date, reason):
        self.conn.execute(
            """INSERT INTO appointments
            (patient_document, patient_name, appointment_date, reason, status, created_at)
            VALUES (?, ?, ?, ?, 'Pendiente', ?)""",
            (document, name, appt_date, reason, now_text())
        )
        self.conn.commit()

    def appointments(self):
        return self.conn.execute(
            "SELECT * FROM appointments ORDER BY appointment_date DESC, id DESC"
        ).fetchall()

    def add_clinical_record(self, document, name, notes):
        self.conn.execute(
            """INSERT INTO clinical_records
            (patient_document, patient_name, notes, created_at)
            VALUES (?, ?, ?, ?)""",
            (document, name, notes, now_text())
        )
        self.conn.commit()

    def clinical_records(self):
        return self.conn.execute(
            "SELECT * FROM clinical_records ORDER BY id DESC"
        ).fetchall()

    def add_pending(self, item_type, description):
        self.conn.execute(
            """INSERT INTO pending_sync (item_type, description, created_at, synced)
            VALUES (?, ?, ?, 0)""",
            (item_type, description, now_text())
        )
        self.conn.commit()

    def pending(self):
        return self.conn.execute(
            "SELECT * FROM pending_sync WHERE synced=0 ORDER BY id"
        ).fetchall()

    def sync_pending(self):
        rows = self.pending()
        if rows:
            self.conn.executemany(
                "UPDATE pending_sync SET synced=1 WHERE id=?",
                [(r["id"],) for r in rows]
            )
            self.conn.commit()
        return len(rows)

    def save_test(self, test_name, sample_number, response_ms, result):
        self.conn.execute(
            """INSERT INTO test_runs
            (test_name, sample_number, response_ms, result, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (test_name, sample_number, response_ms, result, now_text())
        )
        self.conn.commit()

    def test_runs(self):
        return self.conn.execute(
            "SELECT * FROM test_runs ORDER BY id"
        ).fetchall()

    def counts(self):
        return {
            "patients": self.conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            "appointments": self.conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
            "records": self.conn.execute("SELECT COUNT(*) FROM clinical_records").fetchone()[0],
            "pending": self.conn.execute("SELECT COUNT(*) FROM pending_sync WHERE synced=0").fetchone()[0],
        }

    def close(self):
        self.conn.close()


class SaludRuralApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} | Prototipo académico")
        self.root.geometry("1240x790")
        self.root.minsize(1050, 680)
        self.db = Database()
        self.connected = True
        self.session_start = time.time()
        self.last_test_summary = None

        self.configure_styles()
        self.build_layout()
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground=NAVY, background=BG)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=MUTED, background=BG)
        style.configure("Card.TFrame", background=WHITE, relief="flat")
        style.configure("CardTitle.TLabel", background=WHITE, foreground=MUTED, font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", background=WHITE, foreground=NAVY, font=("Segoe UI", 22, "bold"))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(15, 9), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", WHITE)], foreground=[("selected", TEAL_DARK)])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=29,
                        background=WHITE, fieldbackground=WHITE, foreground=TEXT)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#E8EEF5", foreground=NAVY, padding=8)
        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"),
                        background=TEAL, foreground=WHITE, padding=(12, 8), borderwidth=0)
        style.map("Primary.TButton", background=[("active", TEAL_DARK)])
        style.configure("Secondary.TButton", font=("Segoe UI", 9, "bold"),
                        background="#E7EEF5", foreground=NAVY, padding=(11, 8), borderwidth=0)
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)

    def build_layout(self):
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=NAVY, width=225)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=NAVY)
        brand.pack(fill="x", padx=19, pady=(24, 25))
        tk.Label(brand, text="✚", bg=NAVY, fg=TEAL, font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(brand, text="SALUD RURAL", bg=NAVY, fg=WHITE,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(5, 0))
        tk.Label(brand, text="DIGITAL", bg=NAVY, fg="#8EA6BD",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(sidebar, text="PROTOTIPO ACADÉMICO", bg=NAVY, fg="#8EA6BD",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(0, 12))

        self.nav_buttons = {}
        nav_items = [
            ("⌂", "Panel principal", self.show_dashboard),
            ("＋", "Pacientes", self.show_patients),
            ("▣", "Citas médicas", self.show_appointments),
            ("▤", "Historial clínico", self.show_records),
            ("◉", "Telemedicina", self.show_telemedicine),
            ("⇄", "Conectividad", self.show_connectivity),
            ("▥", "Pruebas y KPI", self.show_tests),
        ]
        for symbol, label, command in nav_items:
            btn = tk.Button(sidebar, text=f"  {symbol}   {label}", anchor="w",
                            bg=NAVY, fg="#D5E0EA", activebackground=NAVY_LIGHT,
                            activeforeground=WHITE, relief="flat", bd=0,
                            font=("Segoe UI", 9, "bold"), padx=16, pady=12,
                            command=command, cursor="hand2")
            btn.pack(fill="x", padx=9, pady=2)
            self.nav_buttons[label] = btn

        bottom = tk.Frame(sidebar, bg=NAVY)
        bottom.pack(side="bottom", fill="x", padx=18, pady=18)
        tk.Label(bottom, text="Florencia · Caquetá", bg=NAVY, fg="#AFC0D0",
                 font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(bottom, text="Versión demostrativa 1.0", bg=NAVY, fg="#71879C",
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        main = tk.Frame(shell, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        topbar = tk.Frame(main, bg=WHITE, height=57)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  Plataforma de gestión de salud", bg=WHITE,
                 fg=NAVY, font=("Segoe UI", 10, "bold")).pack(side="left", padx=14)
        self.connection_badge = tk.Label(topbar, text="● Conectado (simulado)",
                                         bg="#E5F6F1", fg=GREEN,
                                         font=("Segoe UI", 9, "bold"), padx=12, pady=6)
        self.connection_badge.pack(side="right", padx=20, pady=10)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=25, pady=22)

        footer = tk.Frame(main, bg=WHITE, height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer, text="Uso educativo · Información ficticia · No utilizar para atención clínica real",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=18, pady=7)

        self.show_dashboard()

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def page_heading(self, title, subtitle):
        tk.Label(self.content, text=title, bg=BG, fg=NAVY,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w")
        tk.Label(self.content, text=subtitle, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 17))

    def card(self, parent, title, value, note):
        frame = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(frame, text=title.upper(), bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(13, 2))
        tk.Label(frame, text=value, bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=16)
        tk.Label(frame, text=note, bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(1, 13))
        return frame

    def make_table(self, parent, columns, headings, height=9):
        wrap = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=columns, show="headings", height=height)
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=130, anchor="w")
        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        yscroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        return tree

    def refresh_connection_badge(self):
        if self.connected:
            self.connection_badge.config(text="● Conectado (simulado)", bg="#E5F6F1", fg=GREEN)
        else:
            self.connection_badge.config(text="● Sin conexión (simulado)", bg="#FCEEEE", fg=RED)

    def refresh_all(self):
        self.refresh_connection_badge()

    def show_dashboard(self):
        self.clear_content()
        self.page_heading("Panel principal", "Resumen operativo del prototipo de salud digital.")
        counts = self.db.counts()
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x")
        items = [
            ("Pacientes registrados", str(counts["patients"]), "Registros locales"),
            ("Citas creadas", str(counts["appointments"]), "Solicitudes almacenadas"),
            ("Registros clínicos", str(counts["records"]), "Datos ficticios"),
            ("Pendientes de sincronizar", str(counts["pending"]), "Almacenamiento local"),
        ]
        for i, item in enumerate(items):
            c = self.card(cards, *item)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 9, 0), pady=3)
            cards.grid_columnconfigure(i, weight=1)

        lower = tk.Frame(self.content, bg=BG)
        lower.pack(fill="both", expand=True, pady=(20, 0))
        left = tk.Frame(lower, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left, text="  Arquitectura funcional", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(16, 10))
        flow = [
            ("01", "Paciente rural", "Accede a los servicios desde la aplicación."),
            ("02", "Aplicación", "Permite registrar pacientes y solicitar servicios."),
            ("03", "API / lógica del sistema", "Valida y procesa las solicitudes simuladas."),
            ("04", "Base de datos SQLite", "Almacena la información local de demostración."),
            ("05", "Profesional de salud", "Consulta los datos autorizados en el escenario simulado."),
        ]
        for num, title, desc in flow:
            row = tk.Frame(left, bg=WHITE)
            row.pack(fill="x", padx=18, pady=6)
            tk.Label(row, text=num, bg="#E3F5F3", fg=TEAL_DARK,
                     font=("Segoe UI", 9, "bold"), width=4, pady=6).pack(side="left")
            body = tk.Frame(row, bg=WHITE)
            body.pack(side="left", padx=10, fill="x", expand=True)
            tk.Label(body, text=title, bg=WHITE, fg=NAVY,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(body, text=desc, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 8), wraplength=430, justify="left").pack(anchor="w")

        right = tk.Frame(lower, bg=WHITE, width=260, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Indicadores de diseño", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 12))
        kpis = [
            ("Tiempo de respuesta", "≤ 2 s"),
            ("Disponibilidad", "≥ 99,5 %"),
            ("Consultas digitales", "250 / día"),
            ("Almacenamiento", "≤ 25 MB / día"),
            ("Ancho de banda", "≥ 10 Mbps"),
            ("Sincronización", "≥ 95 %"),
        ]
        for label, value in kpis:
            line = tk.Frame(right, bg=WHITE)
            line.pack(fill="x", padx=16, pady=7)
            tk.Label(line, text=label, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 8)).pack(side="left")
            tk.Label(line, text=value, bg=WHITE, fg=TEAL_DARK,
                     font=("Segoe UI", 9, "bold")).pack(side="right")
        tk.Label(right, text="Los valores son metas de diseño, no resultados medidos.",
                 bg=WHITE, fg=AMBER, wraplength=220, justify="left",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(12, 0))

    def show_patients(self):
        self.clear_content()
        self.page_heading("Gestión de pacientes", "Registro de usuarios ficticios para probar la persistencia de datos.")
        form = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        form.pack(fill="x", pady=(0, 15))
        fields = {}
        labels = [("Documento", "document"), ("Nombre completo", "name"),
                  ("Edad", "age"), ("Teléfono", "phone"), ("Vereda / comunidad", "community")]
        for i, (label, key) in enumerate(labels):
            box = tk.Frame(form, bg=WHITE)
            box.grid(row=0, column=i, padx=10, pady=13, sticky="ew")
            tk.Label(box, text=label, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            entry = ttk.Entry(box, width=19)
            entry.pack(fill="x", pady=(5, 0))
            fields[key] = entry
            form.grid_columnconfigure(i, weight=1)

        def save():
            document = fields["document"].get().strip()
            name = fields["name"].get().strip()
            age_text = fields["age"].get().strip()
            phone = fields["phone"].get().strip()
            community = fields["community"].get().strip()
            if not document or not name:
                messagebox.showwarning("Datos incompletos", "Documento y nombre son obligatorios.")
                return
            try:
                age = int(age_text) if age_text else None
                if age is not None and not 0 <= age <= 120:
                    raise ValueError
                self.db.add_patient(document, name, age, phone, community)
                if not self.connected:
                    self.db.add_pending("Paciente", f"Registro local de paciente {document}")
                messagebox.showinfo("Registro guardado", "El paciente se almacenó correctamente.")
                for entry in fields.values():
                    entry.delete(0, "end")
                self.fill_patients_table(tree)
            except ValueError:
                messagebox.showerror("Edad no válida", "Ingrese una edad numérica entre 0 y 120.")
            except sqlite3.IntegrityError:
                messagebox.showerror("Documento duplicado", "Ya existe un paciente con ese documento.")

        ttk.Button(form, text="Guardar paciente", style="Primary.TButton",
                   command=save).grid(row=1, column=0, columnspan=5, padx=10, pady=(0, 13), sticky="e")
        tk.Label(self.content, text="Pacientes registrados", bg=BG, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tree = self.make_table(self.content,
                               ("document", "name", "age", "phone", "community", "created"),
                               ("Documento", "Nombre", "Edad", "Teléfono", "Comunidad", "Fecha de registro"),
                               height=10)
        self.fill_patients_table(tree)

    def fill_patients_table(self, tree):
        tree.delete(*tree.get_children())
        for p in self.db.patients():
            tree.insert("", "end", values=(p["document"], p["name"], p["age"] or "",
                                           p["phone"] or "", p["community"] or "", p["created_at"]))

    def show_appointments(self):
        self.clear_content()
        self.page_heading("Gestión de citas", "Creación y consulta de solicitudes de atención simuladas.")
        form = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        form.pack(fill="x", pady=(0, 15))
        tk.Label(form, text="Documento del paciente", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        doc = ttk.Entry(form, width=25)
        doc.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        tk.Label(form, text="Fecha (AAAA-MM-DD)", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=1, padx=12, pady=(12, 4), sticky="w")
        appt_date = ttk.Entry(form, width=20)
        appt_date.insert(0, date.today().isoformat())
        appt_date.grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")
        tk.Label(form, text="Motivo", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=2, padx=12, pady=(12, 4), sticky="w")
        reason = ttk.Entry(form, width=35)
        reason.grid(row=1, column=2, padx=12, pady=(0, 12), sticky="ew")
        for i in range(3):
            form.grid_columnconfigure(i, weight=1)

        def save():
            patient = self.db.get_patient(doc.get().strip())
            if not patient:
                messagebox.showwarning("Paciente no encontrado", "Registre primero al paciente.")
                return
            try:
                datetime.strptime(appt_date.get().strip(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Fecha no válida", "Use el formato AAAA-MM-DD.")
                return
            self.db.add_appointment(patient["document"], patient["name"],
                                    appt_date.get().strip(), reason.get().strip())
            if not self.connected:
                self.db.add_pending("Cita", f"Cita de {patient['name']}")
            messagebox.showinfo("Cita creada", "La solicitud quedó almacenada.")
            self.show_appointments()

        ttk.Button(form, text="Crear cita", style="Primary.TButton",
                   command=save).grid(row=2, column=2, padx=12, pady=(0, 12), sticky="e")
        tk.Label(self.content, text="Solicitudes registradas", bg=BG, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tree = self.make_table(self.content,
                               ("id", "patient", "document", "date", "reason", "status"),
                               ("ID", "Paciente", "Documento", "Fecha", "Motivo", "Estado"),
                               height=11)
        for a in self.db.appointments():
            tree.insert("", "end", values=(a["id"], a["patient_name"], a["patient_document"],
                                           a["appointment_date"], a["reason"], a["status"]))

    def show_records(self):
        self.clear_content()
        self.page_heading("Historial clínico simulado", "Notas ficticias para demostrar el almacenamiento y la consulta de información.")
        form = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        form.pack(fill="x", pady=(0, 15))
        tk.Label(form, text="Documento del paciente", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        doc = ttk.Entry(form, width=28)
        doc.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        tk.Label(form, text="Nota demostrativa", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=1, padx=12, pady=(12, 4), sticky="w")
        notes = ttk.Entry(form, width=65)
        notes.grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        def save():
            patient = self.db.get_patient(doc.get().strip())
            if not patient or not notes.get().strip():
                messagebox.showwarning("Información incompleta", "Verifique el documento y la nota.")
                return
            self.db.add_clinical_record(patient["document"], patient["name"], notes.get().strip())
            if not self.connected:
                self.db.add_pending("Historial", f"Nota local de {patient['name']}")
            messagebox.showinfo("Registro guardado", "La nota ficticia se almacenó correctamente.")
            self.show_records()

        ttk.Button(form, text="Guardar nota", style="Primary.TButton",
                   command=save).grid(row=2, column=1, padx=12, pady=(0, 12), sticky="e")
        tk.Label(self.content, text="Registros almacenados", bg=BG, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        tree = self.make_table(self.content, ("id", "patient", "document", "notes", "created"),
                               ("ID", "Paciente", "Documento", "Nota demostrativa", "Fecha"), height=11)
        for r in self.db.clinical_records():
            tree.insert("", "end", values=(r["id"], r["patient_name"], r["patient_document"],
                                           r["notes"], r["created_at"]))

    def show_telemedicine(self):
        self.clear_content()
        self.page_heading("Telemedicina", "Simulación de solicitud de consulta remota; no se realiza una videollamada real.")
        panel = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="x", pady=(0, 16))
        tk.Label(panel, text="Consulta médica remota", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=22, pady=(20, 5))
        tk.Label(panel, text="Este módulo representa el flujo de solicitud entre el paciente y el servicio de salud.",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=22)
        tk.Label(panel, text="Documento del paciente", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(18, 5))
        doc = ttk.Entry(panel, width=38)
        doc.pack(anchor="w", padx=22)
        tk.Label(panel, text="Motivo de la solicitud", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(12, 5))
        reason = ttk.Entry(panel, width=75)
        reason.pack(anchor="w", padx=22)

        def request():
            patient = self.db.get_patient(doc.get().strip())
            if not patient:
                messagebox.showwarning("Paciente no encontrado", "Registre primero al paciente.")
                return
            description = f"Solicitud de teleconsulta de {patient['name']}: {reason.get().strip()}"
            self.db.add_pending("Teleconsulta", description)
            messagebox.showinfo("Solicitud registrada",
                                "La solicitud quedó guardada en el prototipo. La atención remota real no está habilitada.")
            self.show_telemedicine()

        ttk.Button(panel, text="Registrar solicitud", style="Primary.TButton",
                   command=request).pack(anchor="w", padx=22, pady=18)
        info = tk.Frame(self.content, bg="#E8F5F4")
        info.pack(fill="x", pady=5)
        tk.Label(info, text="Alcance del prototipo", bg="#E8F5F4", fg=TEAL_DARK,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(info, text="Se demuestra el registro de una solicitud. Para telemedicina real se requerirían "
                 "videocomunicación segura, consentimiento, autenticación robusta e integración con prestadores de salud.",
                 bg="#E8F5F4", fg=TEXT, wraplength=850, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))

    def show_connectivity(self):
        self.clear_content()
        self.page_heading("Conectividad y sincronización", "Simulación del modo sin conexión y del envío posterior de datos pendientes.")
        status = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        status.pack(fill="x", pady=(0, 15))
        tk.Label(status, text="Estado de conectividad", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(17, 5))
        self.connectivity_text = tk.Label(status, text="", bg=WHITE, fg=GREEN,
                                          font=("Segoe UI", 11, "bold"))
        self.connectivity_text.pack(anchor="w", padx=20, pady=(0, 12))
        controls = tk.Frame(status, bg=WHITE)
        controls.pack(anchor="w", padx=20, pady=(0, 18))
        ttk.Button(controls, text="Simular pérdida de conexión", style="Secondary.TButton",
                   command=self.disconnect).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Restablecer conexión y sincronizar", style="Primary.TButton",
                   command=self.reconnect).pack(side="left")
        self.update_connectivity_text()

        tk.Label(self.content, text="Elementos pendientes", bg=BG, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 8))
        tree = self.make_table(self.content, ("id", "type", "description", "created"),
                               ("ID", "Tipo", "Descripción", "Fecha de creación"), height=10)
        for p in self.db.pending():
            tree.insert("", "end", values=(p["id"], p["item_type"], p["description"], p["created_at"]))

    def update_connectivity_text(self):
        if self.connected:
            self.connectivity_text.config(text="● Conexión disponible (estado simulado)", fg=GREEN)
        else:
            self.connectivity_text.config(text="● Sin conexión: los nuevos elementos quedan en cola local", fg=RED)

    def disconnect(self):
        self.connected = False
        self.refresh_connection_badge()
        self.update_connectivity_text()
        messagebox.showinfo("Conectividad", "Se activó el escenario simulado sin conexión.")
        self.show_connectivity()

    def reconnect(self):
        self.connected = True
        total = self.db.sync_pending()
        self.refresh_connection_badge()
        self.update_connectivity_text()
        messagebox.showinfo("Sincronización simulada",
                            f"Conexión restablecida. Registros sincronizados: {total}.")
        self.show_connectivity()

    def show_tests(self):
        self.clear_content()
        self.page_heading("Pruebas experimentales y KPI", "Ejecute mediciones locales y exporte los datos para analizarlos en el informe.")
        targets = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        targets.pack(fill="x", pady=(0, 13))
        tk.Label(targets, text="Metas de diseño de la etapa 3", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(13, 8))
        tk.Label(targets, text="Respuesta ≤ 2 s   |   Disponibilidad ≥ 99,5 %   |   250 consultas/día   |   "
                 "Almacenamiento ≤ 25 MB/día   |   Ancho de banda ≥ 10 Mbps   |   Sincronización ≥ 95 %",
                 bg=WHITE, fg=TEXT, font=("Segoe UI", 9), wraplength=900,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 13))

        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=(0, 13))
        ttk.Button(actions, text="Ejecutar prueba de respuesta", style="Primary.TButton",
                   command=self.run_response_test).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Simular 250 operaciones", style="Secondary.TButton",
                   command=self.run_load_test).pack(side="left", padx=8)
        ttk.Button(actions, text="Probar sincronización", style="Secondary.TButton",
                   command=self.run_sync_test).pack(side="left", padx=8)
        ttk.Button(actions, text="Exportar datos CSV", style="Secondary.TButton",
                   command=self.export_csv).pack(side="left", padx=8)

        self.test_summary = tk.Label(self.content, text="Aún no se han ejecutado pruebas en esta sesión.",
                                     bg="#E8F5F4", fg=TEAL_DARK, anchor="w",
                                     font=("Segoe UI", 9), padx=14, pady=12)
        self.test_summary.pack(fill="x", pady=(0, 13))

        tk.Label(self.content, text="Registro de mediciones", bg=BG, fg=NAVY,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.tests_tree = self.make_table(self.content,
                                          ("id", "test", "sample", "response", "result", "created"),
                                          ("ID", "Prueba", "Muestra", "Respuesta (ms)", "Resultado", "Fecha"),
                                          height=9)
        self.fill_tests_table()

        note = ("Nota metodológica: la prueba de respuesta mide operaciones locales SQLite; "
                "no representa latencia de Internet. La simulación de 250 operaciones verifica "
                "procesamiento local, no demuestra capacidad productiva diaria. El ancho de banda "
                "no se mide porque este prototipo no intercambia datos con un servidor remoto.")
        tk.Label(self.content, text=note, bg=BG, fg=AMBER, wraplength=950,
                 justify="left", font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 0))

    def fill_tests_table(self):
        if not hasattr(self, "tests_tree") or not self.tests_tree.winfo_exists():
            return
        self.tests_tree.delete(*self.tests_tree.get_children())
        for r in self.db.test_runs():
            response = "" if r["response_ms"] is None else f"{r['response_ms']:.3f}"
            self.tests_tree.insert("", "end", values=(r["id"], r["test_name"], r["sample_number"],
                                                       response, r["result"], r["created_at"]))

    def run_response_test(self):
        measurements = []
        for i in range(1, 21):
            start = time.perf_counter()
            self.db.conn.execute("SELECT COUNT(*) FROM patients").fetchone()
            elapsed = (time.perf_counter() - start) * 1000
            measurements.append(elapsed)
            self.db.save_test("Respuesta SQLite", i, elapsed,
                              "Cumple meta local" if elapsed <= 2000 else "Supera meta")
        avg = sum(measurements) / len(measurements)
        maximum = max(measurements)
        self.last_test_summary = {"test": "Respuesta SQLite", "samples": len(measurements),
                                  "average_ms": avg, "max_ms": maximum}
        self.test_summary.config(
            text=f"Prueba completada: 20 consultas locales | Promedio: {avg:.3f} ms | "
                 f"Máximo: {maximum:.3f} ms | Meta de referencia: 2.000 ms. "
                 "Interpretar como medición local, no como latencia de red.")
        self.fill_tests_table()

    def run_load_test(self):
        # 250 operaciones locales con datos ficticios y documentos únicos de prueba.
        durations = []
        prefix = f"TEST{int(time.time())}"
        for i in range(1, 251):
            start = time.perf_counter()
            self.db.conn.execute(
                """INSERT INTO pending_sync (item_type, description, created_at, synced)
                VALUES (?, ?, ?, 0)""",
                ("Carga de prueba", f"{prefix}-{i}", now_text())
            )
            self.db.conn.commit()
            elapsed = (time.perf_counter() - start) * 1000
            durations.append(elapsed)
            self.db.save_test("Carga 250 operaciones", i, elapsed, "Operación completada")
        avg = sum(durations) / len(durations)
        total = sum(durations)
        self.last_test_summary = {"test": "Carga 250 operaciones", "samples": 250,
                                  "average_ms": avg, "total_ms": total}
        self.test_summary.config(
            text=f"Prueba completada: 250 operaciones locales | Tiempo total: {total:.2f} ms | "
                 f"Promedio por operación: {avg:.3f} ms. Los registros de prueba quedan identificados "
                 "como 'Carga de prueba' en la cola local.")
        self.fill_tests_table()

    def run_sync_test(self):
        # Crea 20 elementos de prueba pendientes y mide cuántos se sincronizan.
        for i in range(20):
            self.db.add_pending("Prueba de sincronización", f"Elemento de prueba {i+1}")
        total = len(self.db.pending())
        if not self.connected:
            synced = 0
            result = "Pendiente: sin conexión"
        else:
            synced = self.db.sync_pending()
            result = "Sincronizado" if synced == total else "Revisar"
        percentage = (synced / total * 100) if total else 100
        self.db.save_test("Sincronización", 1, None,
                          f"{synced}/{total} ({percentage:.1f} %) - {result}")
        self.last_test_summary = {"test": "Sincronización", "total": total,
                                  "synced": synced, "percentage": percentage}
        self.test_summary.config(
            text=f"Prueba de sincronización: {synced} de {total} elementos procesados "
                 f"({percentage:.1f} %). Meta: ≥ 95 %. Estado de conexión: "
                 f"{'disponible' if self.connected else 'sin conexión'}.")
        self.fill_tests_table()

    def export_csv(self):
        rows = self.db.test_runs()
        if not rows:
            messagebox.showwarning("Sin datos", "Ejecute al menos una prueba antes de exportar.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar resultados experimentales",
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv")],
            initialfile="resultados_experimentales_salud_rural.csv"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID", "Prueba", "Muestra", "Respuesta_ms", "Resultado", "Fecha"])
            for r in rows:
                writer.writerow([r["id"], r["test_name"], r["sample_number"],
                                 r["response_ms"], r["result"], r["created_at"]])
        messagebox.showinfo("Exportación completada", f"Los datos se guardaron en:\n{path}")

    def on_close(self):
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SaludRuralApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
