import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "motivo_1", "text": "1. FUENTE TEMPORAL ESTRICTA (DÍA 1): Extrae el motivo DIRECTAMENTE de la Anamnesis, primera nota de admisión o consulta inicial. Está terminantemente prohibido extraer información de resúmenes de egreso (Epicrisis), evoluciones de días posteriores o complicaciones intra-hospitalarias (ej. neumonía intrahospitalaria).", "priority": "critica", "active": True, "processed": True},
        {"id": "motivo_2", "text": "2. FOCO CLÍNICO DE ADMISIÓN: Redacta exclusivamente el síntoma, signo, o síndrome agudo que disparó la necesidad de internación. Inhibición absoluta: NO incluyas diagnósticos prospectivos confirmados más tarde ni antecedentes patológicos previos, a menos que sean la causa directa de internación.", "priority": "critica", "active": True, "processed": True},
        {"id": "motivo_3", "text": "3. PROTOCOLOS DE INGRESO ESPECIAL: Trauma/Accidentes: Describe Causa + Lesión inicial (Ej: Caída con fractura de fémur). Cirugía Programada: Procedimiento + Patología base. Derivación: Motivo de traslado + Institución origen (si consta).", "priority": "alta", "active": True, "processed": True},
        {"id": "motivo_4", "text": "4. FORMATO DE ALTA PRECISIÓN: Redacción telegráfica ultra-concisa de 15 a 30 palabras máximo. Prohibido usar mayúsculas sostenidas, nombres de pacientes, fechas o detallar la fisiopatología.", "priority": "alta", "active": True, "processed": True},
        {"id": "motivo_5", "text": "5. FALLBACK DE INFERENCIA DE IA: Si la historia carece por completo de nota de ingreso visible, deduce el motivo sintomático leyendo las primeras intervenciones médicas y enciérralo entre paréntesis para indicar que fue inferido de forma secundaria.", "priority": "normal", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "motivo_internacion"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    print("motivo_internacion replaced 88 -> 5 rules")

if __name__ == "__main__":
    asyncio.run(update())
