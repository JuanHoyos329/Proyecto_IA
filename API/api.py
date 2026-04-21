from fastapi import FastAPI
import pickle
import pandas as pd
from pathlib import Path

app = FastAPI(title="API Predicción Retrasos")

# 🔹 Cargar modelo
modelo_path = Path(__file__).parent.parent / "Modelos/modelo_entrenado/xgb_regression_model.pkl"

with open(modelo_path, "rb") as f:
    model = pickle.load(f)

# 🔹 Columnas esperadas
COLUMNAS_MODELO = model.feature_names_in_

# 🔹 Función de transformación
def transformar_input(data):
    from sklearn.preprocessing import LabelEncoder
    
    zona = data.get('zona')

    # si no hay zona (ciudades fuera de Cali)
    if zona is None:
        zona = 'SIN_ZONA'

    # Crear DataFrame base
    df = pd.DataFrame([{
        'hora_recibo': data.get('hora_recibo'),
        'dia_semana_recibo': data.get('dia_semana'),
        'mes': data.get('mes'),
        'barrio_encoded': 21.95,
        'Zona': zona,
        'Ciudad': data.get('ciudad'),
        'Transportador': data.get('transportador')
    }])
    
    # 🔥 Label Encoding con valor artificial incluido
    zonas_conocidas = ['580', '584', '586', '594', '600', '601', '603', '951', 'V02', 'SIN_ZONA']
    
    le_zona = LabelEncoder()
    le_zona.fit(zonas_conocidas)
    df['Zona_encoded'] = le_zona.transform([zona])

    # Eliminar columna original
    df = df.drop(columns=['Zona'])

    # One-Hot Encoding
    df = pd.get_dummies(df, columns=['Ciudad', 'Transportador'])

    # Alinear con modelo
    df = df.reindex(columns=COLUMNAS_MODELO, fill_value=0)

    return df


# 🔹 Endpoint principal
@app.post("/predecir")
def predecir(data: dict):
    try:
        campos_requeridos = ["ciudad", "transportador", "hora_recibo", "dia_semana", "mes"]
        for campo in campos_requeridos:
            if campo not in data or data[campo] is None:
                return {"error": f"Campo requerido faltante: {campo}"}, 400
        
        df = transformar_input(data)

        tiempo = model.predict(df)[0]

        ciudad = data.get("ciudad", "").upper()

        if "CALI" in ciudad:
            limite = 24
        else:
            limite = 48

        retraso = max(0, tiempo - limite)
        estado = "A TIEMPO" if retraso == 0 else "CON RETRASO"

        return {
            "estado": estado,
            "tiempo_estimado_horas": round(float(tiempo), 2),
            "retraso_horas": round(float(retraso), 2),
            "limite_horas": limite,
            "ciudad": ciudad,
            "transportador": data.get("transportador")
        }

    except Exception as e:
        return {"error": f"Error en predicción: {str(e)}"}, 500


# 🔹 Home
@app.get("/")
def home():
    return {"mensaje": "API funcionando correctamente"}