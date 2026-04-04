import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update_interconsultas():
    db = get_mongo_db()
    
    interconsultas_rules = [
        {"id": "int_1", "text": "1. PUREZA DE ESPECIALIDAD: Extrae únicamente valoraciones formales de especialistas externos al médico a cargo. Omite pasadas de sala del médico tratante base.", "priority": "critica", "active": True, "processed": True},
        {"id": "int_2", "text": "2. FORMATO MINIMALISTA ABSOLUTO: Enumera ÚNICAMENTE el nombre de la especialidad (Ej: Hematología, Infectología). Queda TERMINANTEMENTE PROHIBIDO incluir fechas, motivos, diagnósticos, resultados o conductas.", "priority": "critica", "active": True, "processed": True},
        {"id": "int_3", "text": "3. DEDUPLICACIÓN ESTRICTA: Agrupa cualquier repetición. Si Infectología pasó 5 veces, solo debe aparecer la palabra 'Infectología' UNA sola vez en toda la lista.", "priority": "alta", "active": True, "processed": True},
        {"id": "int_4", "text": "4. PROTOCOLOS DE AISLAMIENTO: (Excepción): Si la interconsulta resultó en un aislamiento infectológico (Ej: Aislamiento de contacto), es la ÚNICA información anexa permitida junto al nombre de la especialidad.", "priority": "alta", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "interconsultas"},
        {"$set": {"rules": interconsultas_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    
    print("Interconsultas updated: No dates, no reasons")

if __name__ == "__main__":
    asyncio.run(update_interconsultas())
