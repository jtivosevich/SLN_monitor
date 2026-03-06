import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client

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

TZ = ZoneInfo("America/Santiago")

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="Vencimientos de Casos", page_icon="favicon.png", layout="wide")

st.markdown(
"""
<style>

/* CONTENEDOR */
.block-container { padding-top:0.6rem !important; padding-bottom:0.8rem !important; }

/* TITULOS */
h1 { margin-bottom:0.2rem !important; font-weight:800 !important; }

/* TARJETAS KPI */
.kpi-card {
    height:120px;
    border-radius:14px;
    padding:16px 18px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    box-shadow:0 6px 18px rgba(0,0,0,0.25);
}

/* TITULO KPI */
.kpi-title{
    font-size:20px;
    font-weight:600;
    opacity:0.9;
}

/* VALOR KPI */
.kpi-value{
    font-size:40px;
    font-weight:800;
}

/* TEXTO KPI */
.kpi-sub{
    font-size:14px;
    opacity:0.8;
}

</style>
""",
unsafe_allow_html=True
)

# AUTOREFRESH
REFRESH_MS = 1000
refresh_counter = st_autorefresh(interval=REFRESH_MS, key="refresh")

# ROTACIÓN
ROTATION_WINDOW = 15

# TITULO
st.title("Vencimientos Servicios de HOY")

# ---------------- LOAD DATA ----------------
def load_data_from_supabase():
    cols=f"{COL_OS_DB},{COL_FECHA_DB},{COL_UPDATED_DB},{COL_ESTADO_ACT_DB},{COL_TRANSP_DB}"
    resp=supabase.table(SUPABASE_TABLE).select(cols).execute()
    data=resp.data or []
    if not data:
        return pd.DataFrame(columns=[COL_OS_DB,COL_FECHA_DB,COL_UPDATED_DB,COL_ESTADO_ACT_DB,COL_TRANSP_DB])
    return pd.DataFrame(data)

df=load_data_from_supabase()

# ---------------- RELOJ ----------------
now_ui=datetime.now(TZ).replace(tzinfo=None)

last_updated=None
if not df.empty and COL_UPDATED_DB in df.columns:
    tmp=pd.to_datetime(df[COL_UPDATED_DB],errors="coerce")
    if tmp.notna().any():
        last_updated=tmp.max()

c_time1,c_time2=st.columns([1,1])

with c_time1:
    st.markdown(f"""
<div style="text-align:left;">
🕒 Hora actual: <b>{now_ui.strftime('%Y-%m-%d %H:%M:%S')}</b>
</div>
""",unsafe_allow_html=True)

with c_time2:
    ultima_txt=last_updated.strftime("%Y-%m-%d %H:%M:%S") if last_updated else "—"
    st.markdown(f"""
<div style="text-align:right;">
🗄️ Última actualización: <b>{ultima_txt}</b>
</div>
""",unsafe_allow_html=True)

st.markdown("<div style='height:18px'></div>",unsafe_allow_html=True)

# ---------------- VALIDACIONES ----------------
missing=[c for c in [COL_OS_DB,COL_FECHA_DB] if c not in df.columns]

if missing:
    st.error(f"Faltan columnas en Supabase: {missing}")
    st.stop()

if df.empty:
    st.warning("No hay datos.")
    st.stop()

# ---------------- FECHAS ----------------
dt=pd.to_datetime(df[COL_FECHA_DB],errors="coerce")
df[COL_FECHA_DB]=dt
df["fecha_programacion_display"]=df[COL_FECHA_DB].dt.strftime("%Y-%m-%d %H:%M:%S")

now=datetime.now(TZ).replace(tzinfo=None)

def human_diff(target_dt):

    diff=int((now-target_dt).total_seconds())

    if diff>=0:
        estado="VENCIDO"
        h,m=divmod(diff,3600)
        m,s=divmod(m,60)
        detalle=f"Lleva vencido {h}h {m}m {s}s"

    else:
        left=abs(diff)
        h,m=divmod(left,3600)
        m,s=divmod(m,60)

        if left<=1800:
            estado="URGENTE"
            detalle=f"⚠️ Faltan {h}h {m}m {s}s"
        else:
            estado="POR VENCER"
            detalle=f"Faltan {h}h {m}m {s}s"

    return estado,detalle

estados=[]
detalles=[]

for d in df[COL_FECHA_DB]:

    if pd.isna(d):
        estados.append("SIN FECHA")
        detalles.append("—")
    else:
        e,deta=human_diff(d)
        estados.append(e)
        detalles.append(deta)

df["EstadoTiempo"]=estados
df["DetalleTiempo"]=detalles

# ---------------- TRANSPORTISTA ----------------
transp=df.get(COL_TRANSP_DB,pd.Series([None]*len(df))).astype("string")

sin_transportista=(
transp.isna()
|
(transp.str.strip()=="")
|
(transp.str.lower().str.strip()=="nan")
)

# ---------------- EFECTIVIDAD ----------------
total_casos=len(df)

estado_act=df.get(COL_ESTADO_ACT_DB,pd.Series([None]*len(df))).astype("string")

estados_ok=["PROG","DESP","ENRU","FINA"]

transportista_asignado=~sin_transportista

casos_efectivos=int(
((estado_act.isin(estados_ok)) & transportista_asignado).sum()
)

efectividad=(casos_efectivos/total_casos*100) if total_casos>0 else 0

ef_pct=max(0,min(100,efectividad))

# ---------------- KPI COLORES ----------------
bg_vencidos="linear-gradient(135deg, rgba(255,0,0,0.25), rgba(120,0,0,0.15))"
bg_urgentes="linear-gradient(135deg, rgba(255,165,0,0.25), rgba(120,80,0,0.15))"
bg_porvencer="linear-gradient(135deg, rgba(255,241,118,0.25), rgba(120,120,40,0.15))"
bg_efectividad="linear-gradient(135deg, rgba(0,200,83,0.25), rgba(0,90,50,0.15))"

# ---------------- KPIs ----------------
vencidos=int(((df["EstadoTiempo"]=="VENCIDO") & sin_transportista).sum())
urgentes=int(((df["EstadoTiempo"]=="URGENTE") & sin_transportista).sum())
por_vencer=int(((df["EstadoTiempo"]=="POR VENCER") & sin_transportista).sum())

c1,c2,c3,c4=st.columns(4)

with c1:
    st.markdown(f"""
<div class="kpi-card" style="background:{bg_vencidos}; border-left:8px solid red;">
<div class="kpi-title">Vencidos</div>
<div class="kpi-value" style="color:red;">{vencidos}</div>
</div>
""",unsafe_allow_html=True)

with c2:
    st.markdown(f"""
<div class="kpi-card" style="background:{bg_urgentes}; border-left:8px solid orange;">
<div class="kpi-title">Urgentes (&lt;30m)</div>
<div class="kpi-value" style="color:orange;">{urgentes}</div>
</div>
""",unsafe_allow_html=True)

with c3:
    st.markdown(f"""
<div class="kpi-card" style="background:{bg_porvencer}; border-left:8px solid #FFF176;">
<div class="kpi-title">Por vencer</div>
<div class="kpi-value" style="color:#FFF176;">{por_vencer}</div>
</div>
""",unsafe_allow_html=True)

with c4:
    st.markdown(f"""
<div class="kpi-card" style="background:{bg_efectividad}; border-left:8px solid #00E676;">
<div class="kpi-title">Efectividad</div>
<div class="kpi-value" style="color:#00E676;">{efectividad:.1f}%</div>
<div class="kpi-sub">Efectivos: <b>{casos_efectivos}</b> / Total: <b>{total_casos}</b></div>
</div>
""",unsafe_allow_html=True)

st.markdown("<div style='height:12px'></div>",unsafe_allow_html=True)

# ---------------- BARRA EFECTIVIDAD ----------------
st.markdown(
f"""
<div style="margin-top:6px;margin-bottom:18px;">

<div style="
display:flex;
justify-content:space-between;
font-size:15px;
font-weight:600;
margin-bottom:6px;
">

<span>Efectividad global</span>
<span style="color:#00E676;">{efectividad:.1f}%</span>

</div>

<div style="
width:100%;
height:18px;
background:linear-gradient(90deg, rgba(255,255,255,0.05), rgba(255,255,255,0.10));
border-radius:999px;
overflow:hidden;
box-shadow: inset 0 2px 4px rgba(0,0,0,0.35);
">

<div style="
width:{ef_pct}%;
height:100%;
background:linear-gradient(90deg,#00e676,#00c853);
border-radius:999px;
transition:width 0.9s ease-in-out;
box-shadow:0 0 10px rgba(0,0,0,0.3);
"></div>

</div>

</div>
""",
unsafe_allow_html=True
)
