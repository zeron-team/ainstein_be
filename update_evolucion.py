import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "evo_1", "text": "1. PUREZA DE FUENTES: Construye el texto EXCLUSIVAMENTE a partir de documentos nativos médicos (EVOLUCION MEDICA, PARTE QUIRURGICO, INGRESO DE PACIENTE). Queda estrictamente vedado el uso de Hojas de Enfermería, Balances o Indicaciones como base narrativa.", "priority": "critica", "active": True, "processed": True},
        {"id": "evo_2", "text": "2. ARQUITECTURA TEMPORAL Y SISTÉMICA: Relata los eventos en estricto tiempo pasado y orden cronológico. Estructura el cuerpo principal desglosando la evolución por sistemas y/o especialidades (Cardiológico, Respiratorio, Infectológico, Neurológico) agrupando fechas clave.", "priority": "alta", "active": True, "processed": True},
        {"id": "evo_3", "text": "3. PROTOCOLO INFECTOLÓGICO Y DE CULTIVOS: Al documentar cuadros infecciosos, es obligatorio detallar: Germen aislado, esquema antibiótico específico (fármaco, dosis, vía, y duración exacta en días), si las muestras fueron tomadas pre o intra-antibiótico, y la respuesta clínica al tratamiento.", "priority": "alta", "active": True, "processed": True},
        {"id": "evo_4", "text": "4. HITOS DE RIESGO Y TERAPIA INTENSIVA: Las estadías en unidades cerradas (UTI/UCO) deben tener fecha de ingreso/egreso. Identifica explícitamente los días de Asistencia Respiratoria Mecánica (ARM) y soporte vasopresor/inotrópico. Documenta cualquier Limitación del Esfuerzo Terapéutico (LET) discutida con la familia.", "priority": "alta", "active": True, "processed": True},
        {"id": "evo_5", "text": "5. PRECISIÓN EN PROCEDIMIENTOS E INTERCONSULTAS: Ante intervenciones quirúrgicas o estudios invasivos, menciona fecha, nombre técnico del procedimiento y hallazgo principal. Resume las interconsultas detallando únicamente la recomendación crítica o conducta instaurada por el especialista.", "priority": "normal", "active": True, "processed": True},
        {"id": "evo_6", "text": "6. DESENLACE LEGAL EN ÓBITOS: Ante un fallecimiento u óbito en sala, aplica la normativa argentina: describe las maniobras de RCP precisas y documenta explícitamente la causa de muerte encadenada (causa básica, interviniente y directa).", "priority": "critica", "active": True, "processed": True},
        {"id": "evo_7", "text": "7. ESTADO AL EGRESO (ALTA/DERIVACIÓN): Si el paciente egresa vivo, el párrafo final debe ser una fotografía clínica: detalla el examen físico de salida de relevancia, el destino de egreso (domicilio, rehabilitación, derivación) y el plan estricto de seguimiento ambulatorio (estudios o controles que el médico solicitó a futuro).", "priority": "alta", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "evolucion"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    print("evolucion replaced 114 -> 7 rules")

if __name__ == "__main__":
    asyncio.run(update())
