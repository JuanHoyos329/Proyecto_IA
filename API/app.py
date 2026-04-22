import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

# Configuración de página
st.set_page_config(
    page_title="Sistema de Predicción Logística",
    page_icon="🚛",
    layout="wide"
)

# Estilo personalizado para modo oscuro y métricas
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1f2937;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #374151;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricLabel"] > div { color: #9ca3af !important; }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Sistema de Predicción de Entregas")
st.caption("Panel de control analítico para la estimación de tiempos de transporte con procesamiento ETL.")

# =========================
# CONFIGURACIÓN DE NAVEGACIÓN
# =========================
tabs = st.tabs(["Carga Masiva (Excel)", "Consulta Individual"])

# =========================================================
# TAB 1: CARGA MASIVA (PROCESAMIENTO EXCEL + ETL)
# =========================================================
with tabs[0]:
    st.subheader("Análisis de Pedidos por Lote")
    archivo_excel = st.file_uploader("Suba el archivo de despacho (.xlsx)", type=["xlsx"])

    if archivo_excel is not None:
        if st.button("Procesar Archivo Masivo", type="primary"):
            try:
                # Preparar el archivo para enviarlo a FastAPI
                files = {"file": (archivo_excel.name, archivo_excel.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                
                with st.spinner("Ejecutando ETL y generando predicciones..."):
                    res = requests.post("http://127.0.0.1:8000/predecir_excel", files=files, timeout=30)
                
                if res.status_code == 200:
                    resultado = res.json()
                    df_final = pd.DataFrame(resultado["data"])

                    # Métricas Generales (Sincronizadas con api.py)
                    m1, m2 = st.columns(2)
                    # Usamos 'total_pedidos_procesados' que es el nombre que pusimos en la API
                    m1.metric("Total Pedidos (Post-ETL)", resultado["total_pedidos_procesados"])
                    m2.metric("Pedidos con Riesgo de Retraso", resultado["pedidos_con_retraso"], delta=resultado["pedidos_con_retraso"], delta_color="inverse")

                    # Separación de Datos: Cali vs Resto
                    df_cali = df_final[df_final['Ciudad'].str.contains("CALI", case=False, na=False)]
                    df_resto = df_final[~df_final['Ciudad'].str.contains("CALI", case=False, na=False)]

                    # Función para mostrar tablas ordenadas de mayor a menor demora
                    def mostrar_tabla_ordenada(df, titulo):
                        st.write(f"### {titulo}")
                        if not df.empty:
                            # 1. Ordenar de Mayor a Menor tiempo estimado
                            df_sorted = df.sort_values(by="tiempo_estimado_horas", ascending=False)
                            
                            # 2. Seleccionar columnas clave para la vista del usuario
                            columnas_mostrar = ["Ciudad", "Transportador", "tiempo_estimado_horas", "limite_horas", "retraso_horas", "estado"]
                            df_display = df_sorted[columnas_mostrar]
                            
                            # 3. Estilo condicional para resaltar retrasos
                            def resaltar_retraso(val):
                                color = '#ef4444' if val == "CON RETRASO" else '#10b981'
                                return f'color: {color}; font-weight: bold'

                            st.dataframe(
                                df_display.style.map(resaltar_retraso, subset=['estado']),
                                use_container_width=True
                            )
                        else:
                            st.info("No se encontraron registros para esta categoría tras el filtrado ETL.")

                    # Visualización en columnas
                    col_a, col_b = st.columns(2)
                    with col_a:
                        mostrar_tabla_ordenada(df_cali, "📍 Cali (Límite 24h)")
                    with col_b:
                        mostrar_tabla_ordenada(df_resto, "🌐 Otras Ciudades (Límite 48h)")

                else:
                    detalle_error = res.json().get('detail', 'Error desconocido en el servidor')
                    st.error(f"Error en el servidor: {detalle_error}")

            except Exception as e:
                st.error(f"No se pudo establecer conexión con la API: {e}")

# =========================================================
# TAB 2: CONSULTA INDIVIDUAL
# =========================================================
with tabs[1]:
    st.subheader("Simulación de Pedido Único")
    
    ZONAS = ['580', '584', '586', '594', '600', '601', '603', '951', 'V02']
    CIUDADES = ['ANDALUCIA (VALLE)', 'BOGOTA (CUNDINAMARCA)', 'CALI (VALLE)', 'YUMBO (VALLE)', 'JAMUNDI (VALLE)', 'SANTANDER DE QUILICHAO (CAUCA)']
    TRANSPORTADORES = ['ABD123', 'BDA446', 'CBL490', 'CBZ922', 'CEN356', 'CFG119']
    DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    col1, col2 = st.columns([2, 1])
    with col1:
        ciudad_sel = st.selectbox("Ciudad de destino", CIUDADES)
        trans_sel = st.selectbox("Placa / Transportador", TRANSPORTADORES)
        # Mostrar zona solo si es Cali
        zona_sel = st.selectbox("Zona logística", ZONAS) if "CALI" in ciudad_sel.upper() else None
    
    with col2:
        now = datetime.now()
        st.metric("Hora de Análisis", f"{now.hour}:00")
        st.metric("Día Detectado", DIAS_SEMANA[now.weekday()])

    if st.button("Analizar Pedido Individual", use_container_width=True, type="primary"):
        data = {
            "zona": zona_sel, 
            "ciudad": ciudad_sel, 
            "transportador": trans_sel,
            "hora_recibo": now.hour, 
            "dia_semana": now.weekday(), 
            "mes": now.month
        }
        
        try:
            res = requests.post("http://127.0.0.1:8000/predecir", json=data)
            if res.status_code == 200:
                r = res.json()
                
                if r["estado"] == "CON RETRASO":
                    st.error(f"Resultado: {r['estado']}")
                else:
                    st.success(f"Resultado: {r['estado']}")
                
                c_res1, c_res2, c_res3 = st.columns(3)
                c_res1.metric("Tiempo Est.", f"{r['tiempo_estimado_horas']}h")
                c_res2.metric("Retraso", f"{r['retraso_horas']}h", delta=r['retraso_horas'], delta_color="inverse")
                c_res3.metric("Límite", f"{r['limite_horas']}h")
            else:
                st.warning("No se pudo obtener la predicción individual. Verifique que la API esté corriendo.")
        except Exception as e:
            st.error(f"Error de conexión: {e}")