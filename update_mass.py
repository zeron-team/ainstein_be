import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def mass_update():
    db = get_mongo_db()
    
    # 1. Procedimientos
    procedimientos_rules = [
        {"id": "proc_1", "text": "1. FILTRO INVASIVO DIRECTO: Incluye exclusivamente procedimientos invasivos, quirúrgicos, catéteres centrales (CVC/PICC), sondas, intubaciones y biopisas. Excluye procedimientos de imagen (van a Estudios) y rutinas de enfermería (higiene/curaciones simples).", "priority": "critica", "active": True, "processed": True},
        {"id": "proc_2", "text": "2. ARQUITECTURA CRONOLÓGICA: Ordena los procedimientos con fecha entre paréntesis. Si hay procedimientos compuestos de un mismo tiempo quirúrgico, agrúpalos como un evento único.", "priority": "alta", "active": True, "processed": True},
        {"id": "proc_3", "text": "3. TOPOGRAFÍA Y TÉCNICA: Específica la localización anatómica exacta (sitio de inserción, lecho vascular). En cirugías, anota brevemente el hallazgo intraoperatorio.", "priority": "alta", "active": True, "processed": True},
        {"id": "proc_4", "text": "4. DURACIÓN DE SOPORTES: Para Asistencia Respiratoria Mecánica (ARM) e Infusiones/Nutrición enteral es obligatorio detallar las fechas de inicio a fin.", "priority": "alta", "active": True, "processed": True},
        {"id": "proc_5", "text": "5. FILTRO DE LABORATORIO: Los exámenes de sangre de rutina están excluidos, salvo hallazgo drástico ausente en evolución.", "priority": "normal", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "procedimientos"},
        {"$set": {"rules": procedimientos_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    
    # 2. Interconsultas
    interconsultas_rules = [
        {"id": "int_1", "text": "1. PUREZA DE ESPECIALIDAD: Extrae únicamente valoraciones formales de especialistas externos al médico a cargo. Omite pasadas de sala del médico tratante base.", "priority": "critica", "active": True, "processed": True},
        {"id": "int_2", "text": "2. FORMATO ESTRUCTURADO: Usa el formato condensado: Especialidad - Fecha: Motivo breve y Conducta. Elimina la hora.", "priority": "alta", "active": True, "processed": True},
        {"id": "int_3", "text": "3. SÍNTESIS DE RECOMENDACIÓN (2 Frases MÁX): Resume exclusivamente el hallazgo crítico y la indicación del especialista. Si sugirió un procedimiento quirúrgico/endoscópico, menciónalo como conducta instalada.", "priority": "alta", "active": True, "processed": True},
        {"id": "int_4", "text": "4. PROTOCOLOS DE AISLAMIENTO: Si la interconsulta fue Infectología, detalla obligatoriamente si el paciente quedó en aislamiento de contacto/respiratorio.", "priority": "alta", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "interconsultas"},
        {"$set": {"rules": interconsultas_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    
    # 3. Medicacion
    medicacion_rules = [
        {"id": "med_1", "text": "1. SISTEMA BIPARTITO: Separa la narrativa en Medicación Habitual (pre-ingreso) y Medicación de Internación.", "priority": "critica", "active": True, "processed": True},
        {"id": "med_2", "text": "2. ESQUEMA FARMACOLÓGICO ABSOLUTO: Todo fármaco debe tener Nombre Genérico, Dosis, Vía y Frecuencia. Las medicaciones comerciales deben homologarse.", "priority": "alta", "active": True, "processed": True},
        {"id": "med_3", "text": "3. FILTRO DE RESCATES Y PROCEDIMIENTOS: Prohibido insertar procedimientos quirúrgicos aquí. Vetados los fármacos de única administración (Ringer Lactato simple, un comprimido per-don).", "priority": "critica", "active": True, "processed": True},
        {"id": "med_4", "text": "4. TAXONOMÍA DE RIESGO: Prioriza agrupar los antibióticos (fechas precisas del esquema), anticoagulantes, sedantes paliativos e inotrópicos.", "priority": "alta", "active": True, "processed": True},
        {"id": "med_5", "text": "5. CRUCES AL ALTA: Si una droga de base se suspendió, explicar por qué. La medicación de receta ambulatoria final NO va en esta sección.", "priority": "alta", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "medicacion"},
        {"$set": {"rules": medicacion_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    
    # 4. Indicaciones al alta
    indicaciones_alta_rules = [
        {"id": "ind_1", "text": "1. RECETA DE EGRESO (FARMACOLOGÍA AMBULATORIA): Proporciona la lista con la que el paciente vuelve a casa (Dosis, Vía, Frecuencia). Si egresa con antibióticos, especifica cuántos días quedan.", "priority": "critica", "active": True, "processed": True},
        {"id": "ind_2", "text": "2. TRAZABILIDAD DE ESPECIALISTAS: Detalla las citas de control exigidas y los estudios ambulatorios solicitados (indicando tiempos).", "priority": "alta", "active": True, "processed": True},
        {"id": "ind_3", "text": "3. TERAPIA FÍSICA Y HERIDAS: Enumera las pautas sobre higiene de heridas, restricciones dietéticas y actividad física.", "priority": "alta", "active": True, "processed": True},
        {"id": "ind_4", "text": "4. VETO PRIVACIDAD Y REPETICIONES: Elimina estrictamente teléfonos personales o de WhatsApp de médicos de esta redacción.", "priority": "critica", "active": True, "processed": True},
        {"id": "ind_5", "text": "5. DOBLE ESCENARIO PALIATIVO/ÓBITO: En pacientes fallecidos, borrar todo e indicar hora del óbito. En pacientes paliativos, explicitar las vías de soporte domiciliario.", "priority": "alta", "active": True, "processed": True},
    ]
    # Insert if not exists
    await db.golden_rules.update_one(
        {"_id": "indicaciones_alta"},
        {"$set": {"title": "Indicaciones al alta", "rules": indicaciones_alta_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}},
        upsert=True
    )
    
    # 5. Recomendaciones
    recomendaciones_rules = [
        {"id": "rec_1", "text": "1. PAUTAS DE ALARMA TRADUCIDAS: Escribe pautas de emergencia adaptadas a la familia que correspondan a su patología central de internación (Ej: 'Acudir a guardia ante fiebre, sangrado o pérdida de fuerza').", "priority": "critica", "active": True, "processed": True},
        {"id": "rec_2", "text": "2. INHIBICIÓN FARMACOLÓGICA CRUZADA: Queda absolutamente PROHIBIDO repetir posologías o nombres de antibióticos aquí (eso pertenece a Indicaciones al Alta).", "priority": "critica", "active": True, "processed": True},
        {"id": "rec_3", "text": "3. DERIVACIONES Y KINESIOLOGÍA: Si aplica internación domiciliaria o kinesiología motora de sostenimiento, plásmalo aquí.", "priority": "alta", "active": True, "processed": True},
        {"id": "rec_4", "text": "4. DETECCIÓN DE FALLECIMIENTO: Si el documento detecta óbito, obviar todas las alarmas y generar solo: 'Paciente fallecido. Sin recomendaciones clínicas al alta'.", "priority": "critica", "active": True, "processed": True},
    ]
    # Insert if not exists
    await db.golden_rules.update_one(
        {"_id": "recomendaciones"},
        {"$set": {"title": "Recomendaciones médicas", "rules": recomendaciones_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}},
        upsert=True
    )
    
    print("Mass migrated 393 rules -> 23 master rules across 5 sections")

if __name__ == "__main__":
    asyncio.run(mass_update())
