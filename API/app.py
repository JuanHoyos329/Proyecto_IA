import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

# Configuración de página
st.set_page_config(
    page_title="Sistema de Prediccion Logistica",
    page_icon="D",
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

# Inicializar session_state para almacenar resultados
if 'resultado_excel' not in st.session_state:
    st.session_state.resultado_excel = None
if 'vista_seleccionada' not in st.session_state:
    st.session_state.vista_seleccionada = "Excel"

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
                    res = requests.post("https://sistema-de-prediccion-logistica.onrender.com/predecir_excel", files=files, timeout=30)
                
                if res.status_code == 200:
                    resultado = res.json()
                    # Guardar en session_state para evitar re-renders
                    st.session_state.resultado_excel = resultado
                    st.session_state.vista_seleccionada = "Excel"
                    st.success("Archivo procesado exitosamente")
            except Exception as e:
                st.error(f"No se pudo establecer conexión con la API: {e}")
        
        # Mostrar resultados desde session_state
        if st.session_state.resultado_excel is not None:
            resultado = st.session_state.resultado_excel
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

            # ============================================
            # OPCIÓN DE VISUALIZACIÓN - Solo si hay datos de Cali
            # ============================================
            if not df_cali.empty:
                st.session_state.vista_seleccionada = st.radio(
                    "Tipo de visualización para Cali",
                    ["Excel", "Mapa de Calor"],
                    horizontal=True
                )

            # ============================================
            # TABLAS O MAPA
            # ============================================

            if st.session_state.vista_seleccionada == "Excel":
                col_a, col_b = st.columns(2)

                with col_a:
                    mostrar_tabla_ordenada(df_cali, "Cali (Límite 24h)")

                with col_b:
                    mostrar_tabla_ordenada(df_resto, "Otras Ciudades (Límite 48h)")

            else:  # Mapa de Calor
                st.subheader("Mapa de Calor de Pedidos en Retraso - Cali")

                # Filtrar solo Cali con coordenadas validas
                mapa_df = df_cali.dropna(subset=["Latitud", "Longitud"]).copy()

                if mapa_df.empty:
                    st.warning("No existen coordenadas validas para generar el mapa.")
                else:
                    import folium
                    from streamlit_folium import st_folium

                    # Agregar columna indicadora de si hay retraso
                    mapa_df["tiene_retraso"] = (mapa_df["estado"] == "CON RETRASO").astype(int)
                    
                    # Contar pedidos con retraso por zona
                    retrasos_por_zona = mapa_df.groupby("Zona").agg({
                        "tiene_retraso": "sum",
                        "Latitud": "mean",
                        "Longitud": "mean",
                        "Ciudad": "first"
                    }).reset_index()
                    retrasos_por_zona.columns = ["Zona", "cantidad_retrasos", "Latitud", "Longitud", "Ciudad"]
                    
                    # Función para obtener color según cantidad de retrasos
                    def get_color(cantidad):
                        if cantidad >= 5:
                            return "#CC0000"  # Rojo oscuro
                        elif cantidad >= 3:
                            return "#E63946"  # Rojo
                        elif cantidad >= 1:
                            return "#F77F88"  # Rosa claro
                        else:
                            return "#B8C5D6"  # Gris claro

                    # Crear mapa centrado en Cali
                    m = folium.Map(
                        location=[3.4516, -76.5320],
                        zoom_start=11,
                        tiles="CartoDB positron"
                    )

                    # Agregar círculos para cada zona
                    for idx, row in retrasos_por_zona.iterrows():
                        color = get_color(row["cantidad_retrasos"])
                        
                        # Tamaño del círculo proporcional a cantidad de retrasos
                        radius = 15000 + (row["cantidad_retrasos"] * 8000)
                        
                        folium.Circle(
                            location=[row["Latitud"], row["Longitud"]],
                            radius=radius,
                            popup=f"<b>Zona: {row['Zona']}</b><br>Pedidos en Retraso: {int(row['cantidad_retrasos'])}",
                            color=color,
                            fill=True,
                            fillColor=color,
                            fillOpacity=0.7,
                            weight=2
                        ).add_to(m)

                    # Renderizar mapa
                    st_folium(m, width=1400, height=600)

                    # Estadísticas por zona
                    st.subheader("Estadisticas de Retrasos por Zona")
                    zona_stats = retrasos_por_zona.sort_values("cantidad_retrasos", ascending=False).copy()
                    zona_stats["cantidad_retrasos"] = zona_stats["cantidad_retrasos"].astype(int)
                    st.dataframe(
                        zona_stats[["Zona", "cantidad_retrasos"]].rename(columns={"cantidad_retrasos": "Pedidos en Retraso"}),
                        use_container_width=True,
                        hide_index=True
                    )

                    # Leyenda
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown("<div style='background-color: #CC0000; padding: 10px; border-radius: 5px; color: white; text-align: center;'><b>Rojo Oscuro</b><br>5+ pedidos</div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown("<div style='background-color: #E63946; padding: 10px; border-radius: 5px; color: white; text-align: center;'><b>Rojo</b><br>3-4 pedidos</div>", unsafe_allow_html=True)
                    with col3:
                        st.markdown("<div style='background-color: #F77F88; padding: 10px; border-radius: 5px; color: white; text-align: center;'><b>Rosa</b><br>1-2 pedidos</div>", unsafe_allow_html=True)
                    with col4:
                        st.markdown("<div style='background-color: #B8C5D6; padding: 10px; border-radius: 5px; color: white; text-align: center;'><b>Gris</b><br>0 pedidos</div>", unsafe_allow_html=True)

# =========================================================
# TAB 2: CONSULTA INDIVIDUAL
# =========================================================
with tabs[1]:
    st.subheader("Simulacion de Pedido Unico")
    
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
            res = requests.post("https://sistema-de-prediccion-logistica.onrender.com/predecir", json=data)
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