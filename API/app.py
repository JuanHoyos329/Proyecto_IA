import streamlit as st
import requests
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Sistema de Predicción Logística",
    page_icon="🚛",
    layout="wide"
)

# Estilo personalizado para limpiar la interfaz
# Estilo personalizado optimizado para modo oscuro y profesional
st.markdown("""
    <style>
    /* Fondo general más suave */
    .main {
        background-color: #0e1117;
    }
    /* Estilo de las cajas de métricas para evitar el fondo blanco */
    div[data-testid="stMetric"] {
        background-color: #1f2937;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #374151;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* Ajuste de etiquetas de métricas */
    div[data-testid="stMetricLabel"] > div {
        color: #9ca3af !important;
    }
    /* Ajuste de valores de métricas */
    div[data-testid="stMetricValue"] > div {
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Encabezado principal
st.title("Sistema de Predicción de Entregas")
st.caption("Panel de control analítico para la estimación de tiempos de transporte.")

# =========================
# DATASET DE REFERENCIA
# =========================
ZONAS = ['580', '584', '586', '594', '600', '601', '603', '951', 'V02']
CIUDADES = ['ANDALUCIA (VALLE)', 'BOGOTA (CUNDINAMARCA)', 'BUENOS AIRES CAUCA', 'CALI (VALLE)', 
            'CALOTO (CAUCA)', 'CANDELARIA VALLE DEL CAUCA', 'CODAZZI (CESAR)', 'CORINTO (CAUCA)', 
            'DAGUA (VALLE)', 'DAPA (VALLE)', 'EL CHARCO (NARINO)', 'EL ROSARIO (NARINO)', 
            'FELIDIA- VIA CALI DAGUA', 'GUACHENE (CAUCA)', 'JAMUNDI (VALLE)', 'LA CUMBRE (VALLE)', 
            'LOPEZ DE MICAY CAUCA', 'MONDOMO (CAUCA)', 'MORALES (CAUCA)', 'PESCADOR (CAUCA)', 
            'POBLADO CAMPESTRE VALLE DEL CAUCA', 'POTRERITO-ROBLES-TIMBA', 'PUERTO TEJADA (CAUCA)', 
            'SANTANDER DE QUILICHAO (CAUCA)', 'SATINGA- VIA BUENAVENTURA', 'SINCELEJO (SUCRE)', 
            'SUAREZ CAUCA', 'TIMBIO (CAUCA)', 'TORIBIO  (CAUCA)', 'TRUJILLO (VALLE)', 
            'TUMACO (NARINO)', 'VIJES (VALLE)', 'VILLA GORGONA (VALLE)', 'VILLARICA CAUCA', 
            'YOTOCO (VALLE)', 'YUMBO (VALLE)']
TRANSPORTADORES = ['ABD123', 'BDA446', 'CBL490', 'CBZ922', 'CEN356', 'CFG119', 'CXB610', 'FJM605', 
                   'GTL764', 'KWM751', 'MBJ371', 'NCD473', 'NME026', 'ONG735', 'TZN919', 'TZY274', 
                   'VCK267', 'WHU392', 'WLW779', 'WMV363', 'WTI105', 'YAB258', 'YAB291', 'YAB292']
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

# =========================
# CONFIGURACIÓN DE PARÁMETROS
# =========================
with st.sidebar:
    st.header("Configuración")
    modo = st.radio(
        "Entorno de ejecución",
        ["Producción (Tiempo Real)", "Simulación (Manual)"]
    )
    st.divider()
    st.info("Utilice el modo simulación para validar escenarios hipotéticos.")

modo_prueba = "Simulación" in modo

# Contenedor principal de entrada
with st.container():
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Parámetros del Envío")
        c1, c2 = st.columns(2)
        with c1:
            ciudad = st.selectbox("Ciudad de destino", CIUDADES)
        with c2:
            transportador = st.selectbox("Placa / Transportador", TRANSPORTADORES)
        
        if "CALI" in ciudad:
            zona = st.selectbox("Zona logística", ZONAS)
        else:
            st.warning("Zona no aplicable para la ciudad seleccionada.")
            zona = None

    with col2:
        st.subheader("Temporalidad")
        if modo_prueba:
            hora = st.slider("Hora de recepción (24h)", 0, 23, 9)
            dia = st.selectbox("Día de la semana", DIAS_SEMANA)
            mes = st.selectbox("Mes del año", MESES)

            hora_final = int(hora)
            dia_final = DIAS_SEMANA.index(dia)
            mes_final = MESES.index(mes) + 1
        else:
            now = datetime.now()
            hora_final, dia_final, mes_final = now.hour, now.weekday(), now.month
            
            st.metric("Fecha Actual", f"{DIAS_SEMANA[dia_final]}")
            st.metric("Hora Actual", f"{hora_final}:00")

st.divider()

# =========================
# PROCESAMIENTO Y RESULTADOS
# =========================
if st.button("Ejecutar Análisis", use_container_width=True, type="primary"):
    data = {
        "zona": zona,
        "ciudad": ciudad,
        "transportador": transportador,
        "hora_recibo": hora_final,
        "dia_semana": dia_final,
        "mes": mes_final
    }

    try:
        res = requests.post("http://127.0.0.1:8000/predecir", json=data, timeout=5)

        if res.status_code == 200:
            resultado = res.json()

            if "error" in resultado:
                st.error(f"Error en procesamiento: {resultado['error']}")
            else:
                # Encabezado de resultado
                status = resultado["estado"]
                if status == "A TIEMPO":
                    st.success(f"Estado del Pedido: {status}")
                else:
                    st.error(f"Estado del Pedido: {status}")

                # Métricas Clave
                m1, m2, m3 = st.columns(3)
                m1.metric("Tiempo Estimado", f"{resultado['tiempo_estimado_horas']} h")
                m2.metric("Desviación (Retraso)", f"{resultado['retraso_horas']} h", delta=resultado['retraso_horas'], delta_color="inverse")
                m3.metric("Límite de Entrega", f"{resultado['limite_horas']} h")

                # Detalles del registro
                st.markdown(f"**Detalles técnicos:** Registro asociado a {resultado['transportador']} en la ruta de {resultado['ciudad']}.")

        else:
            st.error(f"Error de comunicación: Código de estado {res.status_code}")

    except Exception as e:
        st.error("Error crítico: No se pudo establecer conexión con el motor de predicción.")