import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client
import altair as alt

# ---------------- SUPABASE ----------------
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["anon_key"]
SUPABASE_TABLE = "programacion_transporte_test"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

COL_OS_DB = "os"
COL_FECHA_DB = "fecha_programacion"
COL_UPDATED_DB = "updated_at"
COL_ESTADO_ACT_DB = "estado_actividad"
COL_TRANSP_DB = "transportista"

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="Vencimientos de Casos", page_icon="favicon.png", layout="wide")

st.markdown("""
<style>
/* CONTENEDOR */
.block-container { padding-top: 0.6rem !important; padding-bottom: 0.8rem !important; }

/* TITULOS */
h1 { margin-bottom: 0.2rem !important; font-weight: 800 !important; }

/* TARJETAS KPI */
.kpi-card {
    height: 120px;
    border-radius: 14px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.kpi-title {
    font-size: 20px;
    font-weight: 600;
    opacity: 0.9;
    text-transform: none !important;   /* SIN MAYÚSCULAS */
}

.kpi-value {
    font-size: 40px;
    font-weight: 800;
    line-height: 1.1;
}

.kpi-sub {
    font-size: 14px;
    opacity: 0.8;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# AUTOREFRESH
REFRESH_MS = 1000
refresh_counter = st_autorefresh(interval=REFRESH_MS, key="refresh")

# TITULO PRINCIPAL
st.title("Vencimientos Servicios de HOY")

# ---------------- LOAD DATA ----------------
def load_data_from_supabase() -> pd.DataFrame:
    cols = f"{COL_OS_DB},{COL_FECHA_DB},{COL_UPDATED_DB},{COL_ESTADO_ACT_DB},{COL_TRANSP_DB}"
    resp = supabase.table(SUPABASE_TABLE).select(cols).execute()
    data = resp.data or []
    if not data:
        return pd.DataFrame(columns=[COL_OS_DB, COL_FECHA_DB, COL_UPDATED_DB, COL_ESTADO_ACT_DB, COL_TRANSP_DB])
    return pd.DataFrame(data)

df = load_data_from_supabase()

# ---------------- RELOJ + ÚLTIMA LECTURA ----------------
now_ui = datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)

last_updated = None
if not df.empty and COL_UPDATED_DB in df.columns:
    tmp = pd.to_datetime(df[COL_UPDATED_DB], errors="coerce")
    if tmp.notna().any():
        last_updated = tmp.max()

c_time1, c_time2 = st.columns([1, 1])

with c_time1:
    st.markdown(f"""
    <div style="text-align:left;">
        🕒 Hora actual: <b>{now_ui.strftime('%Y-%m-%d %H:%M:%S')}</b>
    </div>
    """, unsafe_allow_html=True)

with c_time2:
    ultima_txt = last_updated.strftime('%Y-%m-%d %H:%M:%S') if last_updated else "—"
    st.markdown(f"""
    <div style="text-align:right;">
        🗄️ Última actualización: <b>{ultima_txt}</b>
    </div>
    """, unsafe_allow_html=True)

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

now = datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)

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
casos_efectivos = int(((estado_act == "PROG") & transportista_asignado).sum())
efectividad = (casos_efectivos / total_casos * 100.0) if total_casos > 0 else 0.0

# ---------------- COLOR EFECTIVIDAD (rangos, SOLO COLOR) ----------------
def efectividad_style(pct: float):
    try:
        pct = float(pct)
    except Exception:
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    if pct <= 25:
        return {"bg": "rgba(255,0,0,0.12)", "border": "red", "text": "red"}
    elif pct <= 50:
        return {"bg": "rgba(255,165,0,0.18)", "border": "orange", "text": "orange"}
    elif pct <= 75:
        return {"bg": "rgba(255,241,118,0.20)", "border": "#FFF176", "text": "#FFF176"}
    else:
        return {"bg": "rgba(0,200,83,0.14)", "border": "#00C853", "text": "#00C853"}

ef = efectividad_style(efectividad)

# ---------------- KPIs ----------------
# ✅ Solo casos SIN transportista
vencidos = int(((df["EstadoTiempo"] == "VENCIDO") & sin_transportista).sum())
urgentes = int(((df["EstadoTiempo"] == "URGENTE") & sin_transportista).sum())
por_vencer = int(((df["EstadoTiempo"] == "POR VENCER") & sin_transportista).sum())

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="kpi-card" style="background:rgba(255,0,0,0.12); border-left:8px solid red;">
        <div class="kpi-title">Vencidos</div>
        <div class="kpi-value" style="color:red;">{vencidos}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card" style="background:rgba(255,165,0,0.18); border-left:8px solid orange;">
        <div class="kpi-title">Urgentes (&lt;30m)</div>
        <div class="kpi-value" style="color:orange;">{urgentes}</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="kpi-card" style="background:rgba(255,241,118,0.20); border-left:8px solid #FFF176;">
        <div class="kpi-title">Por vencer</div>
        <div class="kpi-value" style="color:#FFF176;">{por_vencer}</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="kpi-card" style="background:{ef['bg']}; border-left:8px solid {ef['border']};">
        <div class="kpi-title">Efectividad</div>
        <div class="kpi-value" style="color:{ef['text']};">{efectividad:.1f}%</div>
        <div class="kpi-sub">
            Efectivos: <b>{casos_efectivos}</b> / Total: <b>{total_casos}</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)


# ---------------- PRÓXIMO VENCIMIENTO (SOLO SIN TRANSPORTISTA) ----------------
df_valid = df.dropna(subset=[COL_FECHA_DB]).copy()
df_valid = df_valid[sin_transportista].copy()

next_dt = None
next_count = 0
next_os_list = []

if not df_valid.empty:
    futuros = df_valid[df_valid[COL_FECHA_DB] >= now].copy()
    if not futuros.empty:
        next_dt = futuros[COL_FECHA_DB].min()
        grupo = futuros[futuros[COL_FECHA_DB] == next_dt].copy()
        next_os_list = sorted(grupo[COL_OS_DB].astype(str).unique().tolist())
        next_count = len(next_os_list)

# ---------------- EXPANDER ----------------
with st.expander(f"Ver O/S del próximo vencimiento ({next_count})"):
    if next_count > 0:
        os_only = pd.DataFrame({"O/S": next_os_list})
        st.dataframe(os_only, use_container_width=True, hide_index=True, height=240)
    else:
        st.info("No hay próximos vencimientos sin transportista.")

# ---------------- TABLA BASE (para urgentes/por vencer) ----------------
order_map = {"VENCIDO": 0, "URGENTE": 1, "POR VENCER": 2, "SIN FECHA": 3}
df["_ord"] = df["EstadoTiempo"].map(order_map).fillna(99)
df_sorted = df.sort_values(by=["_ord", COL_FECHA_DB]).drop(columns=["_ord"]).copy()

blink_on = (datetime.now(ZoneInfo("America/Santiago")).second % 2 == 0)

def icono_estado(est):
    if est == "VENCIDO": return "🔴"
    if est == "URGENTE": return "🟠"
    if est == "POR VENCER": return "🟡"
    return "⚪"

# ---------------- ROTACIÓN ----------------
try:
    phase = (refresh_counter // ROTATION_WINDOW) % 2
except NameError:
    phase = 0

if phase == 0:
    df_v = df_sorted[(df_sorted["EstadoTiempo"] == "VENCIDO") & sin_transportista].copy()

    tabla_view = df_v[[COL_OS_DB, "fecha_programacion_display", "EstadoTiempo", "DetalleTiempo"]].copy()
    tabla_view = tabla_view.rename(columns={
        COL_OS_DB: "O/S",
        "fecha_programacion_display": "Fecha Programación de servicio",
    })
    tabla_view["Riesgo"] = tabla_view["EstadoTiempo"].apply(icono_estado)
    tabla_view = tabla_view[["Riesgo", "O/S", "Fecha Programación de servicio", "EstadoTiempo", "DetalleTiempo"]]

    view_title = "Servicios Vencidos"
else:
    df_u = df_sorted[df_sorted["EstadoTiempo"].isin(["URGENTE", "POR VENCER"]) & sin_transportista].copy()

    tabla_view = df_u[[COL_OS_DB, "fecha_programacion_display", "EstadoTiempo", "DetalleTiempo"]].copy()
    tabla_view = tabla_view.rename(columns={
        COL_OS_DB: "O/S",
        "fecha_programacion_display": "Fecha Programación de servicio",
    })
    tabla_view["Riesgo"] = tabla_view["EstadoTiempo"].apply(icono_estado)
    tabla_view = tabla_view[["Riesgo", "O/S", "Fecha Programación de servicio", "EstadoTiempo", "DetalleTiempo"]]

    view_title = "Servicios Urgentes y Por Vencer"

st.subheader(view_title)

# ---------------- STYLE TABLA ----------------
def style_row(row):
    styles = [""] * len(row)
    idx_riesgo = row.index.get_loc("Riesgo")
    idx_estado = row.index.get_loc("EstadoTiempo")
    idx_detalle = row.index.get_loc("DetalleTiempo")

    if row["EstadoTiempo"] == "VENCIDO":
        styles[idx_estado] = "color:red; font-weight:900;"
        styles[idx_riesgo] = "font-size:20px;"
    elif row["EstadoTiempo"] == "URGENTE":
        if blink_on:
            styles[idx_estado] = "color:orange; font-weight:900;"
            styles[idx_detalle] = "color:orange; font-weight:800;"
            styles[idx_riesgo] = "font-size:20px;"
        else:
            styles[idx_estado] = "color:rgba(255,165,0,0.25); font-weight:900;"
            styles[idx_detalle] = "color:rgba(255,165,0,0.25); font-weight:800;"
            styles[idx_riesgo] = "font-size:20px; opacity:0.25;"
    elif row["EstadoTiempo"] == "POR VENCER":
        styles[idx_estado] = "color:#FFF176; font-weight:900;"
        styles[idx_riesgo] = "font-size:20px;"

    return styles

styled_df = tabla_view.style.apply(style_row, axis=1)
st.dataframe(styled_df, use_container_width=True, hide_index=True, height=720)

