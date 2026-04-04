import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "core_1", "text": "1. LECTURA 100% ESTRICTA: La IA DEBE analizar obligatoriamente el 100% del texto de la Historia Clínica Electrónica proveída sin truncar ni omitir eventos. Ninguna información relevante debe pre-descartarse.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_2", "text": "2. TOLERANCIA CERO A ALUCINACIONES: Está terminantemente prohibido inventar, predecir, deducir fechas no explícitas o suponer datos clínicos. Si no hay información para un apartado, se debe omitir o dejar vacío.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_3", "text": "3. FIDELIDAD CLÍNICA ('PASE ENTRE COLEGAS'): El estilo de redacción debe ser estrictamente médico-técnico, formal y denso, equivalente a un pase de guardia o derivación entre especialistas.", "priority": "alta", "active": True, "processed": True},
        {"id": "core_4", "text": "4. FILTRO INTELIGENTE (LOOK VS DO): Excluir absoluta y automáticamente procedimientos de enfermería (ej. control signos vitales, valoración) y fluidos basales o fisiológicos (excepto cuando marquen un hito terapéutico).", "priority": "alta", "active": True, "processed": True},
        {"id": "core_5", "text": "5. CRONOLOGÍA LINEAL ABSOLUTA: Todo evento clínico debe relatarse en una línea de tiempo unidireccional y secuencial (Antecedentes -> Motivo de Ingreso -> Desarrollo en Sala/UTI -> Condición al Alta/Óbito).", "priority": "alta", "active": True, "processed": True},
        {"id": "core_6", "text": "6. DESPERSONALIZACIÓN MÉDICA: Queda prohibido el uso de la 1ra persona ('le indiqué', 'observo'). Todo debe redactarse de forma impersonal ('se indica', 'paciente refiere', 'se constata').", "priority": "normal", "active": True, "processed": True},
        {"id": "core_7", "text": "7. INFERENCIA DE AGRUPACIÓN (DE-DUPLICACIÓN): Si un tratamiento clínico, antibiótico o vía endovenosa se repite consecutivamente por días en la HCE, no describirlo repetitivamente por cada día. Agrupar la conducta (ej. 'Cumplió esquema con Ceftriaxona por 5 días').", "priority": "alta", "active": True, "processed": True},
        {"id": "core_8", "text": "8. SALVAGUARDA LEGAL (CRISIS Y ÓBITO): Ante reportes de RCP, maniobras avanzadas, intubaciones de urgencia o fallecimiento, la narrativa abandona el estilo de resumen y pasa a describir causas directas e intervinientes, temporalidad (hora) y respuesta a maniobras de modo hiper-preciso.", "priority": "critica", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "core"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}},
        upsert=True
    )
    print("Top 8 Core rules added to DB.")

if __name__ == "__main__":
    asyncio.run(update())
