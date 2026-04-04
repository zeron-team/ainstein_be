import asyncio
from datetime import datetime, timezone
from app.adapters.mongo_client import get_mongo_db

async def update_procedimientos():
    db = get_mongo_db()
    
    procedimientos_rules = [
        {"text": "1. FILTRO INVASIVO DIRECTO: Incluye exclusivamente procedimientos quirúrgicos, biopsias, catéteres, sondas e intubaciones. Excluye imágenes médicas (van a Estudios) y rutinas de enfermería. PROHÍBE RIGUROSAMENTE las Interconsultas o menciones a Especialidades Médicas (ej: Otorrinolaringología, Neurología, etc), las cuales deben ser purgadas de aquí e ir a su sección nativa.", "priority": "critica", "active": True},
        {"text": "2. ARQUITECTURA CRONOLÓGICA: Ordena los procedimientos con fecha entre paréntesis. Si hay procedimientos compuestos de un mismo tiempo quirúrgico, agrúpalos como un evento único.", "priority": "alta", "active": True},
        {"text": "3. TOPOGRAFÍA Y TÉCNICA: Específica la localización anatómica exacta (sitio de inserción, lecho vascular). En cirugías, anota brevemente el hallazgo intraoperatorio.", "priority": "alta", "active": True},
        {"text": "4. DURACIÓN DE SOPORTES: Para Asistencia Respiratoria Mecánica (ARM) e Infusiones/Nutrición enteral es obligatorio detallar las fechas de inicio a fin.", "priority": "alta", "active": True},
        {"text": "5. FILTRO DE LABORATORIO: Los exámenes de sangre de rutina están excluidos, salvo hallazgo drástico ausente en evolución.", "priority": "normal", "active": True},
    ]

    await db.golden_rules.update_one(
        {"_id": "procedimientos"},
        {"$set": {
            "title": "Procedimientos",
            "rules": procedimientos_rules,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "sistema_agente"
        }},
        upsert=True
    )
    print("Reglas de procedimientos actualizadas exitosamente con la regla anti-interconsultas.")

if __name__ == "__main__":
    asyncio.run(update_procedimientos())
