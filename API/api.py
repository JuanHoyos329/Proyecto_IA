from fastapi import FastAPI, UploadFile, File, HTTPException
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import io

app = FastAPI(title="API Predicción Retrasos - Procesamiento Masivo")

# 🔹 Cargar modelo
modelo_path = Path(__file__).parent.parent / "Modelos/modelo_entrenado/xgb_regression_model.pkl"

with open(modelo_path, "rb") as f:
    model = pickle.load(f)

# 🔹 Columnas esperadas por el modelo
COLUMNAS_MODELO = model.feature_names_in_

# 🔹 Lista de columnas a eliminar según el ETL.ipynb
COLUMNAS_PARA_BORRAR = [
    "Despacho", "Cod. trans", "Código", "Identificación", "Nombres", "Fecha pedido",
    "Fecha facturado", "Hora facturado", "Fecha embalado", "Hora embalado", 
    "Fecha despachado", "Estado", "Dias entregado", "Cajas", "Corte", 
    "Placa vehiculo", "Regional", "Line pick", "Fecha masivo", "Track", "Novedad", "Entregado", "Anotación", "Transportista", 
    "Tipo Docu", "Nro visita"
]

def aplicar_etl(df: pd.DataFrame):
    """Limpia y transforma el DataFrame siguiendo la lógica de ETL.ipynb."""
    # 1. Renombrar si existe la columna duplicada de estado
    if 'Estado.1' in df.columns:
        df.rename(columns={'Estado.1': 'Estado'}, inplace=True)

    # 2. Borrar columnas innecesarias
    df = df.drop(columns=[c for c in COLUMNAS_PARA_BORRAR if c in df.columns])
    
    # 3. Eliminar valores nulos
    df = df.dropna()

    # 4. Normalización de texto (Estado y Ciudad)
    if 'Estado' in df.columns:
        df["Estado"] = df["Estado"].astype(str).str.upper().str.strip()
    if 'Ciudad' in df.columns:
        df["Ciudad"] = df["Ciudad"].astype(str).str.upper().str.strip()

    # 5. Conversión de fechas y cálculo de horas de entrega real (si las columnas existen)
    columnas_fecha = ["Fecha recibo LD", "Fecha reparto", "Fecha entrega"]
    for col in columnas_fecha:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Si tenemos fechas, filtramos por lógica de negocio (opcional para predicción, pero presente en tu ETL)
    if all(col in df.columns for col in ["Fecha entrega", "Fecha reparto"]):
        df["horas_entrega_real"] = (df["Fecha entrega"] - df["Fecha reparto"]).dt.total_seconds() / 3600
        # Filtrar horas negativas
        df = df[df["horas_entrega_real"] >= 0].copy()

        # 6. Eliminación de Outliers (Método IQR)
        Q1 = df["horas_entrega_real"].quantile(0.25)
        Q3 = df["horas_entrega_real"].quantile(0.75)
        IQR = Q3 - Q1
        limite_superior = Q3 + 1.5 * IQR
        df = df[df["horas_entrega_real"] <= limite_superior].copy()
    
    return df

def transformar_y_predecir(df_original: pd.DataFrame):
    """Prepara los datos para el modelo XGBoost."""
    df_proc = df_original.copy()

    # Asegurar que existan las columnas de tiempo para el modelo si no vienen en el Excel
    # (El modelo usualmente requiere hora_recibo, dia_semana, mes)
    if "Fecha recibo LD" in df_proc.columns:
        df_proc['hora_recibo'] = df_proc['Fecha recibo LD'].dt.hour
        df_proc['dia_semana_recibo'] = df_proc['Fecha recibo LD'].dt.dayofweek
        df_proc['mes'] = df_proc['Fecha recibo LD'].dt.month

    # Manejo de Zona
    if 'Zona' not in df_proc.columns:
        df_proc['Zona_encoded'] = 9  # Valor por defecto 'SIN_ZONA'

    # One-Hot Encoding masivo para Ciudad y Transportador
    df_final = pd.get_dummies(df_proc, columns=['Ciudad', 'Transportador'])
    
    # Alinear con las columnas que el modelo conoce
    df_final = df_final.reindex(columns=COLUMNAS_MODELO, fill_value=0)
    
    return model.predict(df_final)

@app.post("/predecir_excel")
async def predecir_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel.")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # 1. Aplicar ETL completo (incluye limpieza de nulos y outliers)
        df = aplicar_etl(df)

        if df.empty:
            return {"error": "El archivo quedó vacío después del proceso de limpieza y filtrado de outliers."}

        # 2. Obtener predicciones
        df['tiempo_estimado_horas'] = transformar_y_predecir(df)

        # 3. Lógica de filtros Ciudad (Cali 24h vs Resto 48h)
        def calcular_estado(row):
            ciudad = str(row['Ciudad']).upper()
            limite = 24 if "CALI" in ciudad else 48
            retraso = max(0, row['tiempo_estimado_horas'] - limite)
            return pd.Series([
                limite, 
                round(float(retraso), 2), 
                "A TIEMPO" if retraso == 0 else "CON RETRASO"
            ])

        df[['limite_horas', 'retraso_horas', 'estado']] = df.apply(calcular_estado, axis=1)

        # 4. Respuesta técnica limpia
        resultado = df.to_dict(orient="records")

        return {
            "total_pedidos_procesados": len(df),
            "pedidos_con_retraso": len(df[df['estado'] == "CON RETRASO"]),
            "data": resultado
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el proceso ETL/Predicción: {str(e)}")

@app.get("/")
def home():
    return {"mensaje": "API de carga masiva con ETL activo"}

@app.head("/")
def head_home():
    return {}