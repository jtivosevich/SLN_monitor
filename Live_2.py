import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client
from html import escape

# ---------------- SUPABASE ----------------
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["anon_key"]
SUPABASE_TABLE = "programacion_transporte_test"

COL_OS_DB = "os"
COL_FECHA_DB = "fecha_programacion"
COL_UPDATED_DB = "updated_at"
COL_ESTADO_ACT_DB = "estado_actividad"
COL_TRANSP_DB = "transportista"

TZ = ZoneInfo("America/Santiago")

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="Vencimientos de Casos", page_icon="favicon.png", layout="wide")

st.markdown(
    """
<style>
/* CONTENEDOR */
.block-container { padding-top: 0.6rem !important; padding-bottom: 0.8rem !important; }

/* TITULOS */
h1 { margin-bottom: 0.2rem !important; font-weight: 800 !important; }

/* BOTON */
div.stButton > button {
    border-radius: 12px !important;
    font-weight: 700 !important;
    height: 44px !important;
}

/* TARJETAS KPI */
.kpi-card {
    height: 120px;
    border-radius: 14px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    box-shadow: 0 6px 18px rgba(0,0,0,0.18);
    backdrop-filter: blur(4px);
}

.kpi-title {
    font-size: 20px;
    font-weight: 600;
    opacity: 0.92;
    text-transform: none !important;
}

.kpi-value {
    font-size: 40px;
    font-weight: 800;
    line-height: 1.1;
}

.kpi-sub {
    font-size: 14px;
    opacity: 0.82;
    margin-top: 6px;
}

/* BRILLO ANIMADO BARRA EFECTIVIDAD */
@keyframes shine {
    0% { transform: translateX(-140%); }
    100% { transform: translateX(260%); }
}

.progress-shine {
    position: absolute;
    top: 0;
    left: 0;
    width: 40%;
    height: 100%;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.00) 0%,
        rgba(255,255,255,0.35) 40%,
        rgba(255,255,255,0.55) 50%,
        rgba(255,255,255,0.35) 60%,
        rgba(255,255,255,0.00) 100%
    );
    animation: shine 2.6s linear infinite;
    pointer-events: none;
}

/* TABLA PREMIUM */
.table-shell {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    overflow: hidden;
    background: rgba(255,255,255,0.015);
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}

.table-scroll {
    max-height: 720px;
    overflow-y: auto;
    overflow-x: auto;
}

.table-scroll::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

.table-scroll::-webkit-scrollbar-track {
    background: rgba(255,255,255,0.04);
    border-radius: 999px;
}

.table-scroll::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.14);
    border-radius: 999px;
}

.premium-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}

.premium-table thead th {
    transform: translateZ(0);
    position: sticky;
    top: 0;
    z-index: 5;
    text-align: left;
    padding: 14px 14px;
    font-size: 14px;
    font-weight: 700;
    color: rgba(255,255,255,0.90);
    background: linear-gradient(
        180deg,
        rgba(28,32,40,0.98) 0%,
        rgba(18,21,27,0.98) 100%
    );
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

.premium-table tbody td {
    padding: 13px 14px;
    font-size: 14px;
    color: rgba(255,255,255,0.92);
    border-bottom: 1px solid rgba(255,255,255,0.05);
    vertical-align: middle;
    word-wrap: break-word;
}

.premium-table tbody tr:hover {
    background: rgba(255,255,255,0.03);
}

.premium-table th:nth-child(1),
.premium-table td:nth-child(1) {
    width: 90px;
}

.premium-table th:nth-child(2),
.premium-table td:nth-child(2) {
    width: 90px;
}

.premium-table th:nth-child(3),
.premium-table td:nth-child(3) {
    width: 260px;
}

.premium-table th:nth-child(4),
.premium-table td:nth-child(4) {
    width: 150px;
}

.premium-table th:nth-child(5),
.premium-table td:nth-child(5) {
    width: 220px;
}

.risk-dot {
    display: inline-block;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    box-shadow:
        0 0 0 2px rgba(255,255,255,0.04) inset,
        0 0 10px currentColor;
}

.state-vencido {
    color: #ff3b30;
    font-weight: 900;
}

.state-urgente {
    color: #ff9f0a;
    font-weight: 900;
}

.state-urgente-dim {
    color: rgba(255,165,0,0.28);
    font-weight: 900;
}

.state-porvencer {
    color: #FFF176;
    font-weight: 900;
}

.detail-urgente {
    color: #ffb020;
    font-weight: 800;
}

.detail-urgente-dim {
    color: rgba(255,165,0,0.28);
    font-weight: 800;
}
</style>
""",
    unsafe_allow_html=True,
)

# AUTOREFRESH
REFRESH_MS = 1000
refresh_counter = st_autorefresh(interval=REFRESH_MS, key="refresh")

# ROTACIÓN (segundos)
ROTATION_WINDOW = 15

# ---------------- FUNCIONES CACHEADAS ----------------
@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=15)
def load_data_from_supabase() -> pd.DataFrame:
    supabase = get_supabase_client()
    cols = f"{COL_OS_DB},{COL_FECHA_DB},{COL_UPDATED_DB},{COL_ESTADO_ACT_DB},{COL_TRANSP_DB}"
    resp = supabase.table(SUPABASE_TABLE).select(cols).execute()
    data = resp.data or []
    if not data:
        return pd.DataFrame(columns=[COL_OS_DB, COL_FECHA_DB, COL_UPDATED_DB, COL_ESTADO_ACT_DB, COL_TRANSP_DB])
    return pd.DataFrame(data)

# TITULO PRINCIPAL
st.title("Vencimientos Servicios de HOY")

# ---------------- BOTÓN FORZAR RECARGA ----------------
c_btn1, c_btn2 = st.columns([1.1, 4])

with c_btn1:
    if st.button("🔄 Forzar recarga", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

with c_btn2:
    st.caption("Usa este botón si la app despertó y los datos no se ven actualizados.")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ---------------- LOAD DATA ----------------
df = load_data_from_supabase()

# ---------------- RELOJ + ÚLTIMA LECTURA ----------------
now_ui = datetime.now(TZ).replace(tzinfo=None)

last_updated = None
if not df.empty and COL_UPDATED_DB in df.columns:
    tmp = pd.to_datetime(df[COL_UPDATED_DB], errors="coerce")
    if tmp.notna().any():
        last_updated = tmp.max()

c_time1, c_time2 = st.columns([1, 1])

with c_time1:
    st.markdown(
        f"""
<div style="text-align:left;">
    🕒 Hora actual: <b>{now_ui.strftime('%Y-%m-%d %H:%M:%S')}</b>
</div>
""",
        unsafe_allow_html=True,
    )

with c_time2:
    ultima_txt = last_updated.strftime("%Y-%m-%d %H:%M:%S") if last_updated is not None else "—"
    st.markdown(
        f"""
<div style="text-align:right;">
    🗄️ Última lectura desde Supabase: <b>{ultima_txt}</b>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ---------------- VALIDACIONES ----------------
missing = [c for c in [COL_OS_DB, COL_FECHA_DB] if c not in df.columns]
if missing:
    st.error(f"Faltan columnas en Supabase: {missing}")
    st.stop()

if df.empty:
    st.warning("Supabase respondió OK, pero no hay filas en la tabla todavía.")
    st.stop()

# ---------------- FECHAS ----------------
dt = pd.to_datetime(df[COL_FECHA_DB], errors="coerce")
try:
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_convert("UTC").dt.tz_localize(None)
except Exception:
    pass

df[COL_FECHA_DB] = dt
df["fecha_programacion_display"] = df[COL_FECHA_DB].dt.strftime("%Y-%m-%d %H:%M:%S").astype(str)

now = datetime.now(TZ).replace(tzinfo=None)

def human_diff(target_dt: datetime):
    diff_seconds = int((now - target_dt).total_seconds())

    if diff_seconds >= 0:
        estado = "VENCIDO"
        s = diff_seconds
        h, r = divmod(s, 3600)
        m, s = divmod(r, 60)
        detalle = f"Lleva vencido {h}h {m}m {s}s"
    else:
        s_left = abs(diff_seconds)
        h, r = divmod(s_left, 3600)
        m, s = divmod(r, 60)

        if s_left <= 1800:
            estado = "URGENTE"
            detalle = f"⚠️ Faltan {h}h {m}m {s}s"
        else:
            estado = "POR VENCER"
            detalle = f"Faltan {h}h {m}m {s}s"

    return estado, detalle

estados, detalles = [], []
for dtx in df[COL_FECHA_DB]:
    if pd.isna(dtx):
        estados.append("SIN FECHA")
        detalles.append("—")
    else:
        est, det = human_diff(dtx)
        estados.append(est)
        detalles.append(det)

df["EstadoTiempo"] = estados
df["DetalleTiempo"] = detalles

# ---------------- SIN TRANSPORTISTA ----------------
transp = df.get(COL_TRANSP_DB, pd.Series([None] * len(df))).astype("string")
sin_transportista = transp.isna() | (transp.str.strip() == "") | (transp.str.lower().str.strip() == "nan")

# ---------------- EFECTIVIDAD ----------------
total_casos = int(len(df))
estado_act = df.get(COL_ESTADO_ACT_DB, pd.Series([None] * len(df))).astype("string")

transportista_asignado = ~sin_transportista
estados_efectivos = ["PROG", "DESP", "ENRU", "FINA"]

casos_efectivos = int(((estado_act.isin(estados_efectivos)) & transportista_asignado).sum())
efectividad = (casos_efectivos / total_casos * 100.0) if total_casos > 0 else 0.0

# ---------------- ESTILO EFECTIVIDAD ----------------
def efectividad_style(pct: float):
    try:
        pct = float(pct)
    except Exception:
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    if pct <= 25:
        return {
            "bg": "linear-gradient(135deg, rgba(255,0,0,0.22) 0%, rgba(120,0,0,0.12) 100%)",
            "border": "#ff3b30",
            "text": "#ff3b30",
            "bar": "linear-gradient(90deg, #ff5f57 0%, #ff3b30 100%)",
        }
    elif pct <= 50:
        return {
            "bg": "linear-gradient(135deg, rgba(255,165,0,0.22) 0%, rgba(120,70,0,0.12) 100%)",
            "border": "#ff9f0a",
            "text": "#ff9f0a",
            "bar": "linear-gradient(90deg, #ffbe55 0%, #ff9f0a 100%)",
        }
    elif pct <= 75:
        return {
            "bg": "linear-gradient(135deg, rgba(255,241,118,0.22) 0%, rgba(140,130,40,0.12) 100%)",
            "border": "#FFF176",
            "text": "#FFF176",
            "bar": "linear-gradient(90deg, #fff59d 0%, #FFF176 100%)",
        }
    else:
        return {
            "bg": "linear-gradient(135deg, rgba(0,200,83,0.22) 0%, rgba(0,90,50,0.12) 100%)",
            "border": "#00C853",
            "text": "#00E676",
            "bar": "linear-gradient(90deg, #00e676 0%, #00c853 100%)",
        }

ef = efectividad_style(efectividad)
ef_pct = max(0.0, min(100.0, efectividad))

# ---------------- ESTILOS KPI POR CATEGORÍA ----------------
kpi_vencidos_bg = "linear-gradient(135deg, rgba(255,0,0,0.22) 0%, rgba(90,0,0,0.14) 100%)"
kpi_urgentes_bg = "linear-gradient(135deg, rgba(255,165,0,0.22) 0%, rgba(110,70,0,0.14) 100%)"
kpi_porvencer_bg = "linear-gradient(135deg, rgba(255,241,118,0.22) 0%, rgba(110,110,45,0.14) 100%)"

# ---------------- KPIs ----------------
vencidos = int(((df["EstadoTiempo"] == "VENCIDO") & sin_transportista).sum())
urgentes = int(((df["EstadoTiempo"] == "URGENTE") & sin_transportista).sum())
por_vencer = int(((df["EstadoTiempo"] == "POR VENCER") & sin_transportista).sum())

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(
        f"""
<div class="kpi-card" style="background:{kpi_vencidos_bg}; border-left:8px solid #ff3b30;">
    <div class="kpi-title">Vencidos</div>
    <div class="kpi-value" style="color:#ff3b30;">{vencidos}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
<div class="kpi-card" style="background:{kpi_urgentes_bg}; border-left:8px solid #ff9f0a;">
    <div class="kpi-title">Urgentes (&lt;30m)</div>
    <div class="kpi-value" style="color:#ffb020;">{urgentes}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
<div class="kpi-card" style="background:{kpi_porvencer_bg}; border-left:8px solid #FFF176;">
    <div class="kpi-title">Por vencer</div>
    <div class="kpi-value" style="color:#FFF176;">{por_vencer}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
<div class="kpi-card" style="background:{ef['bg']}; border-left:8px solid {ef['border']};">
    <div class="kpi-title">Efectividad</div>
    <div class="kpi-value" style="color:{ef['text']};">{efectividad:.1f}%</div>
    <div class="kpi-sub">
        Efectivos: <b>{casos_efectivos}</b> / Total: <b>{total_casos}</b>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ---------------- BARRA GLOBAL EFECTIVIDAD ----------------
st.markdown(f"""<div style="margin-top:10px; margin-bottom:18px;">

<div style="
display:flex;
justify-content:space-between;
align-items:center;
margin-bottom:6px;
font-size:15px;
font-weight:600;
">
<span>Efectividad global</span>
<span style="color:{ef['text']}; font-weight:800;">{efectividad:.1f}%</span>
</div>

<div style="
width:100%;
height:16px;
background:linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.10) 100%);
border-radius:999px;
overflow:hidden;
box-shadow: inset 0 1px 3px rgba(0,0,0,0.35);
border:1px solid rgba(255,255,255,0.06);
">

<div style="
width:{ef_pct}%;
height:100%;
background:{ef['bar']};
border-radius:999px;
transition:width 0.9s ease-in-out;
box-shadow: 0 0 10px rgba(255,255,255,0.10), 0 0 12px rgba(0,0,0,0.15);
position:relative;
overflow:hidden;
">

<div class="progress-shine"></div>

</div>
</div>

</div>""", unsafe_allow_html=True)

# ---------------- PRÓXIMO VENCIMIENTO ----------------
df_valid = df.dropna(subset=[COL_FECHA_DB]).copy()
df_valid = df_valid[sin_transportista].copy()

next_count = 0
next_os_list = []

if not df_valid.empty:
    futuros = df_valid[df_valid[COL_FECHA_DB] >= now].copy()
    if not futuros.empty:
        next_dt = futuros[COL_FECHA_DB].min()
        grupo = futuros[futuros[COL_FECHA_DB] == next_dt].copy()
        next_os_list = sorted(grupo[COL_OS_DB].astype(str).unique().tolist())
        next_count = len(next_os_list)

with st.expander(f"Ver O/S del próximo vencimiento ({next_count})"):
    if next_count > 0:
        st.dataframe(
            pd.DataFrame({"O/S": next_os_list}),
            use_container_width=True,
            hide_index=True,
            height=240
        )
    else:
        st.info("No hay próximos vencimientos sin transportista.")

# ---------------- TABLA + ROTACIÓN ----------------
order_map = {"VENCIDO": 0, "URGENTE": 1, "POR VENCER": 2, "SIN FECHA": 3}
df["_ord"] = df["EstadoTiempo"].map(order_map).fillna(99)
df_sorted = df.sort_values(by=["_ord", COL_FECHA_DB]).drop(columns=["_ord"]).copy()

blink_on = (datetime.now(TZ).second % 2 == 0)
phase = (refresh_counter // ROTATION_WINDOW) % 2

if phase == 0:
    df_v = df_sorted[(df_sorted["EstadoTiempo"] == "VENCIDO") & sin_transportista].copy()
    view_title = "Servicios Vencidos"
    tabla_view = df_v
else:
    df_u = df_sorted[df_sorted["EstadoTiempo"].isin(["URGENTE", "POR VENCER"]) & sin_transportista].copy()
    view_title = "Servicios Urgentes y Por Vencer"
    tabla_view = df_u

st.subheader(view_title)

tabla = tabla_view[[COL_OS_DB, "fecha_programacion_display", "EstadoTiempo", "DetalleTiempo"]].copy()
tabla = tabla.rename(
    columns={
        COL_OS_DB: "O/S",
        "fecha_programacion_display": "Fecha Programación de servicio",
    }
)
tabla = tabla[["O/S", "Fecha Programación de servicio", "EstadoTiempo", "DetalleTiempo"]]

def get_risk_dot_and_classes(estado: str):
    if estado == "VENCIDO":
        return "#ff3b30", "state-vencido", ""
    if estado == "URGENTE":
        if blink_on:
            return "#ff9f0a", "state-urgente", "detail-urgente"
        return "#a86a1b", "state-urgente-dim", "detail-urgente-dim"
    if estado == "POR VENCER":
        return "#FFF176", "state-porvencer", ""
    return "rgba(255,255,255,0.35)", "", ""

def render_premium_table(df_table: pd.DataFrame, height_px: int = 720) -> str:
    headers = [
        "Riesgo",
        "O/S",
        "Fecha Programación de servicio",
        "EstadoTiempo",
        "DetalleTiempo",
    ]

    rows = []

    if df_table.empty:
        rows.append(
            """
<tr>
    <td colspan="5" style="text-align:center; color:rgba(255,255,255,0.65); padding:22px;">
        No hay registros para mostrar.
    </td>
</tr>
"""
        )
    else:
        for _, row in df_table.iterrows():
            estado = str(row["EstadoTiempo"])
            riesgo_color, estado_class, detalle_class = get_risk_dot_and_classes(estado)

            riesgo_html = f'<span class="risk-dot" style="background:{riesgo_color}; color:{riesgo_color};"></span>'
            os_html = escape(str(row["O/S"]))
            fecha_html = escape(str(row["Fecha Programación de servicio"]))
            estado_html = (
                f'<span class="{estado_class}">{escape(estado)}</span>'
                if estado_class else escape(estado)
            )
            detalle_raw = escape(str(row["DetalleTiempo"]))
            detalle_html = (
                f'<span class="{detalle_class}">{detalle_raw}</span>'
                if detalle_class else detalle_raw
            )

            row_html = (
                "<tr>"
                f"<td>{riesgo_html}</td>"
                f"<td>{os_html}</td>"
                f"<td>{fecha_html}</td>"
                f"<td>{estado_html}</td>"
                f"<td>{detalle_html}</td>"
                "</tr>"
            )
            rows.append(row_html)

    header_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_html = "".join(rows)

    return (
        f'<div class="table-shell">'
        f'  <div class="table-scroll" style="max-height:{height_px}px;">'
        f'    <table class="premium-table">'
        f'      <thead><tr>{header_html}</tr></thead>'
        f'      <tbody>{body_html}</tbody>'
        f'    </table>'
        f'  </div>'
        f'</div>'
    )

tabla_html = render_premium_table(tabla, height_px=720)
st.markdown(tabla_html, unsafe_allow_html=True)
