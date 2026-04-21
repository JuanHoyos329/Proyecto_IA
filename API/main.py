# main.py
from fastapi import FastAPI
import pickle
import pandas as pd
from pathlib import Path
import os

app = FastAPI(title="API Predicción Retrasos")

# 🔹 Cargar modelo
# Obtener la ruta correcta del modelo (sube un nivel desde API)
modelo_path = Path(__file__).parent.parent / "Modelos\modelo_entrenado" / "xgb_regression_model.pkl"

if not modelo_path.exists():
    raise FileNotFoundError(f"Modelo no encontrado en: {modelo_path}")

with open(modelo_path, "rb") as f:
    model = pickle.load(f)
    
print(f"✓ Modelo cargado desde: {modelo_path}")

# 🔹 Endpoint principal
@app.post("/predecir")
def predecir(data: dict):

    # Convertir a DataFrame
    df = pd.DataFrame([data])

    # Predicción
    pred = model.predict(df)[0]

    # Probabilidad (si el modelo lo soporta)
    try:
        prob = model.predict_proba(df)[0][1]
    except:
        prob = None

    return {
        "prediccion": int(pred),
        "probabilidad": float(prob) if prob is not None else None
    }

# 🔹 Endpoint de prueba
@app.get("/")
def home():
    return {"mensaje": "API funcionando correctamente"}