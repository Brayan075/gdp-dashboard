import csv
import io
import sqlite3
import time
from datetime import datetime, date
from pathlib import Path

import streamlit as st

APP_NAME = "Salud Rural Digital"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "salud_rural_digital.db"

st.set_page_config(
    page_title="Salud Rural Digital",
    page_icon="✚",
    layout="wide",
)

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path))
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
        return self.conn.execute("SELECT * FROM patients ORDER BY name").fetchall()

    def get_patient(self, document):
        return self.conn.execute("SELECT * FROM patients WHERE document=?", (document,)).fetchone()

    def add_appointment(self, document, name, appt_date, reason):
        self.conn.execute(
            """INSERT INTO appointments
            (patient_document, patient_name, appointment_date, reason, status, created_at)
            VALUES (?, ?, ?, ?, 'Pendiente', ?)""",
            (document, name, appt_date, reason, now_text())
        )
        self.conn.commit()

    def appointments(self):
        return self.conn.execute("SELECT * FROM appointments ORDER BY appointment_date DESC, id DESC").fetchall()

    def add_clinical_record(self, document, name, notes):
        self.conn.execute(
            """INSERT INTO clinical_records
            (patient_document, patient_name, notes, created_at)
            VALUES (?, ?, ?, ?)""",
            (document, name, notes, now_text())
        )
        self.conn.commit()

    def clinical_records(self):
        return self.conn.execute("SELECT * FROM clinical_records ORDER BY id DESC").fetchall()

    def add_pending(self, item_type, description):
        self.conn.execute(
            """INSERT INTO pending_sync (item_type, description, created_at, synced)
            VALUES (?, ?, ?, 0)""",
            (item_type, description, now_text())
        )
        self.conn.commit()

    def pending(self):
        return self.conn.execute("SELECT * FROM pending_sync WHERE synced=0 ORDER BY id").fetchall()

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
        return self.conn.execute("SELECT * FROM test_runs ORDER BY id").fetchall()

    def counts(self):
        return {
            "patients": self.conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            "appointments": self.conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
            "records": self.conn.execute("SELECT COUNT(*) FROM clinical_records").fetchone()[0],
            "pending": self.conn.execute("SELECT COUNT(*) FROM pending_sync WHERE synced=0").fetchone()[0],
        }

    def close(self):
        self.conn.close()


def init_session_state():
    if "connected" not in st.session_state:
        st.session_state.connected = True
    if "last_test_summary" not in st.session_state:
        st.session_state.last_test_summary = "Aún no se han ejecutado pruebas en esta sesión."


def render_dashboard(db):
    counts = db.counts()
    st.header("Panel principal")
    st.caption("Resumen operativo del prototipo de salud digital.")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pacientes registrados", counts["patients"])
    col2.metric("Citas creadas", counts["appointments"])
    col3.metric("Registros clínicos", counts["records"])
    col4.metric("Pendientes de sincronizar", counts["pending"])

    st.subheader("Arquitectura funcional")
    flow = [
        ("01", "Paciente rural", "Accede a los servicios desde la aplicación."),
        ("02", "Aplicación", "Permite registrar pacientes y solicitar servicios."),
        ("03", "API / lógica del sistema", "Valida y procesa las solicitudes simuladas."),
        ("04", "Base de datos SQLite", "Almacena la información local de demostración."),
        ("05", "Profesional de salud", "Consulta los datos autorizados en el escenario simulado."),
    ]

    for num, title, desc in flow:
        with st.container():
            st.markdown(f"**{num}. {title}** — {desc}")


def render_patients(db):
    st.header("Gestión de pacientes")
    st.caption("Registro de usuarios ficticios para probar la persistencia de datos.")

    with st.form("form_paciente", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        document = c1.text_input("Documento")
        name = c2.text_input("Nombre completo")
        age = c3.number_input("Edad", min_value=0, max_value=120, value=0)

        c4, c5 = st.columns(2)
        phone = c4.text_input("Teléfono")
        community = c5.text_input("Vereda / comunidad")

        submitted = st.form_submit_button("Guardar paciente")

        if submitted:
            if not document.strip() or not name.strip():
                st.warning("Documento y nombre son obligatorios.")
            else:
                try:
                    db.add_patient(document.strip(), name.strip(), int(age), phone.strip(), community.strip())
                    if not st.session_state.connected:
                        db.add_pending("Paciente", f"Registro local de paciente {document.strip()}")
                    st.success("Paciente guardado correctamente.")
                except sqlite3.IntegrityError:
                    st.error("Ya existe un paciente con ese documento.")
                except ValueError:
                    st.error("La edad debe ser numérica y válida.")

    st.subheader("Pacientes registrados")
    rows = [dict(r) for r in db.patients()]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_appointments(db):
    st.header("Gestión de citas")
    st.caption("Creación y consulta de solicitudes de atención simuladas.")

    with st.form("form_cita", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        document = c1.text_input("Documento del paciente")
        fecha = c2.text_input("Fecha (AAAA-MM-DD)", value=date.today().isoformat())
        reason = c3.text_input("Motivo")
        submitted = st.form_submit_button("Crear cita")

        if submitted:
            patient = db.get_patient(document.strip())
            if not patient:
                st.warning("Paciente no encontrado. Registre primero al paciente.")
            else:
                try:
                    datetime.strptime(fecha.strip(), "%Y-%m-%d")
                    db.add_appointment(patient["document"], patient["name"], fecha.strip(), reason.strip())
                    if not st.session_state.connected:
                        db.add_pending("Cita", f"Cita de {patient['name']}")
                    st.success("Cita creada correctamente.")
                except ValueError:
                    st.error("Use el formato AAAA-MM-DD.")

    st.subheader("Solicitudes registradas")
    rows = [dict(r) for r in db.appointments()]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_records(db):
    st.header("Historial clínico simulado")
    st.caption("Notas ficticias para demostrar el almacenamiento y la consulta de información.")

    with st.form("form_nota", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        document = c1.text_input("Documento del paciente")
        notes = c2.text_input("Nota demostrativa")
        submitted = st.form_submit_button("Guardar nota")

        if submitted:
            patient = db.get_patient(document.strip())
            if not patient or not notes.strip():
                st.warning("Verifique el documento y la nota.")
            else:
                db.add_clinical_record(patient["document"], patient["name"], notes.strip())
                if not st.session_state.connected:
                    db.add_pending("Historial", f"Nota local de {patient['name']}")
                st.success("Nota registrada correctamente.")

    st.subheader("Registros almacenados")
    rows = [dict(r) for r in db.clinical_records()]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_telemedicine(db):
    st.header("Telemedicina")
    st.caption("Simulación de solicitud de consulta remota; no se realiza una videollamada real.")

    with st.form("form_teleconsulta", clear_on_submit=True):
        document = st.text_input("Documento del paciente")
        reason = st.text_input("Motivo de la solicitud")
        submitted = st.form_submit_button("Registrar solicitud")

        if submitted:
            patient = db.get_patient(document.strip())
            if not patient:
                st.warning("Paciente no encontrado. Registre primero al paciente.")
            else:
                description = f"Solicitud de teleconsulta de {patient['name']}: {reason.strip()}"
                db.add_pending("Teleconsulta", description)
                st.success("Solicitud registrada. La atención remota real no está habilitada.")

    st.info(
        "Se demuestra el registro de una solicitud. Para telemedicina real se requerirían "
        "videocomunicación segura, consentimiento, autenticación robusta e integración con prestadores de salud."
    )


def render_connectivity(db):
    st.header("Conectividad y sincronización")
    st.caption("Simulación del modo sin conexión y del envío posterior de datos pendientes.")

    if st.button("Simular pérdida de conexión"):
        st.session_state.connected = False

    if st.button("Restablecer conexión y sincronizar"):
        st.session_state.connected = True
        total = db.sync_pending()
        st.success(f"Conexión restablecida. Registros sincronizados: {total}.")

    estado = "Conectado" if st.session_state.connected else "Sin conexión"
    color = "green" if st.session_state.connected else "red"
    st.markdown(f"<h4 style='color:{color};'>● {estado}</h4>", unsafe_allow_html=True)

    st.subheader("Elementos pendientes")
    rows = [dict(r) for r in db.pending()]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_tests(db):
    st.header("Pruebas experimentales y KPI")
    st.caption("Ejecute mediciones locales y exporte los datos para analizarlos.")

    st.subheader("Metas de diseño")
    st.markdown(
        "Respuesta ≤ 2 s | Disponibilidad ≥ 99,5 % | 250 consultas/día | "
        "Almacenamiento ≤ 25 MB/día | Ancho de banda ≥ 10 Mbps | Sincronización ≥ 95 %"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Ejecutar prueba de respuesta"):
            run_response_test(db)
    with col2:
        if st.button("Simular 250 operaciones"):
            run_load_test(db)
    with col3:
        if st.button("Probar sincronización"):
            run_sync_test(db)
    with col4:
        pass

    st.info(st.session_state.last_test_summary)

    st.subheader("Registro de mediciones")
    rows = [dict(r) for r in db.test_runs()]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    csv_data = export_csv_string(db.test_runs())
    st.download_button(
        label="Exportar datos CSV",
        data=csv_data,
        file_name="resultados_experimentales_salud_rural.csv",
        mime="text/csv",
    )

    st.caption(
        "Nota metodológica: la prueba de respuesta mide operaciones locales SQLite; "
        "no representa latencia de Internet. La simulación de 250 operaciones verifica "
        "procesamiento local, no demuestra capacidad productiva diaria. El ancho de banda "
        "no se mide porque este prototipo no intercambia datos con un servidor remoto."
    )


def run_response_test(db):
    measurements = []
    for i in range(1, 21):
        start = time.perf_counter()
        db.conn.execute("SELECT COUNT(*) FROM patients").fetchone()
        elapsed = (time.perf_counter() - start) * 1000
        measurements.append(elapsed)
        db.save_test(
            "Respuesta SQLite",
            i,
            elapsed,
            "Cumple meta local" if elapsed <= 2000 else "Supera meta"
        )
    avg = sum(measurements) / len(measurements)
    maximum = max(measurements)
    st.session_state.last_test_summary = (
        f"Prueba completada: 20 consultas locales | Promedio: {avg:.3f} ms | "
        f"Máximo: {maximum:.3f} ms | Meta de referencia: 2.000 ms. "
        "Interpretar como medición local, no como latencia de red."
    )


def run_load_test(db):
    durations = []
    prefix = f"TEST{int(time.time())}"
    for i in range(1, 251):
        start = time.perf_counter()
        db.conn.execute(
            """INSERT INTO pending_sync (item_type, description, created_at, synced)
            VALUES (?, ?, ?, 0)""",
            ("Carga de prueba", f"{prefix}-{i}", now_text())
        )
        db.conn.commit()
        elapsed = (time.perf_counter() - start) * 1000
        durations.append(elapsed)
        db.save_test("Carga 250 operaciones", i, elapsed, "Operación completada")
    avg = sum(durations) / len(durations)
    total = sum(durations)
    st.session_state.last_test_summary = (
        f"Prueba completada: 250 operaciones locales | Tiempo total: {total:.2f} ms | "
        f"Promedio por operación: {avg:.3f} ms. Los registros de prueba quedan identificados "
        "como 'Carga de prueba' en la cola local."
    )


def run_sync_test(db):
    for i in range(20):
        db.add_pending("Prueba de sincronización", f"Elemento de prueba {i+1}")
    total = len(db.pending())
    if not st.session_state.connected:
        synced = 0
        result = "Pendiente: sin conexión"
    else:
        synced = db.sync_pending()
        result = "Sincronizado" if synced == total else "Revisar"
    percentage = (synced / total * 100) if total else 100
    db.save_test("Sincronización", 1, None, f"{synced}/{total} ({percentage:.1f} %) - {result}")
    st.session_state.last_test_summary = (
        f"Prueba de sincronización: {synced} de {total} elementos procesados "
        f"({percentage:.1f} %). Meta: ≥ 95 %. Estado de conexión: "
        f"{'disponible' if st.session_state.connected else 'sin conexión'}."
    )


def export_csv_string(rows):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Prueba", "Muestra", "Respuesta_ms", "Resultado", "Fecha"])
    for r in rows:
        writer.writerow([r["id"], r["test_name"], r["sample_number"], r["response_ms"], r["result"], r["created_at"]])
    return output.getvalue()


def main():
    init_session_state()
    db = Database()

    st.title("Salud Rural Digital")
    st.caption("Prototipo académico. No usar con datos médicos reales.")
    st.markdown(
        "Este prototipo simula la gestión de salud rural con almacenamiento local y sincronización local."
    )

    sections = [
        "Panel principal",
        "Pacientes",
        "Citas",
        "Historial clínico",
        "Telemedicina",
        "Conectividad",
        "Pruebas",
    ]

    choice = st.sidebar.radio("Secciones", sections)

    if choice == "Panel principal":
        render_dashboard(db)
    elif choice == "Pacientes":
        render_patients(db)
    elif choice == "Citas":
        render_appointments(db)
    elif choice == "Historial clínico":
        render_records(db)
    elif choice == "Telemedicina":
        render_telemedicine(db)
    elif choice == "Conectividad":
        render_connectivity(db)
    else:
        render_tests(db)

    db.close()


if __name__ == "__main__":
    main()