import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "core_1", "text": "La IA DEBE analizar obligatoriamente el 100% del texto de la Historia Clínica Electrónica proveída sin truncar ni omitir eventos.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_2", "text": "TOLERANCIA CERO A ALUCINACIONES: Está terminantemente prohibido inventar, deducir fechas no explícitas o suponer datos clínicos. Si no hay información, dejar vacío.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_3", "text": "MANTENER FIDELIDAD CLÍNICA: Respetar plenamente la terminología técnica original de los profesionales sin alterar el significado de los diagnósticos, conductas o evoluciones.", "priority": "alta", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "core"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    print("Core rules injected to DB.")

if __name__ == "__main__":
    asyncio.run(update())
