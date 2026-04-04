import asyncio
from datetime import datetime, timezone
from app.adapters.mongo_client import get_mongo_db

async def apply_core_definitions():
    db = get_mongo_db()
    
    # 1. Procedimientos
    procedimientos_rules = [
        {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Procedimientos' como toda intervención terapéutica, quirúrgica o diagnóstica invasiva/no invasiva. Incluyen cirugías (programadas/urgencia, técnica), endoscopías, cateterismos, punciones, y procedimientos menores (drenajes, suturas complejas, reducciones, dispositivos). Captura: tipo de procedimiento y fecha. Solo incluye los que modificaron el curso clínico o plan terapéutico.", "priority": "critica", "active": True},
        {"text": "1. FILTRO INVASIVO DIRECTO: Incluye exclusivamente procedimientos quirúrgicos, biopsias, catéteres, sondas e intubaciones. Excluye imágenes médicas (van a Estudios) y rutinas de enfermería. PROHÍBE RIGUROSAMENTE las Interconsultas o menciones a Especialidades Médicas (ej: Otorrinolaringología, Neurología, etc), las cuales deben ser purgadas de aquí e ir a su sección nativa.", "priority": "critica", "active": True},
        {"text": "2. ARQUITECTURA CRONOLÓGICA: Ordena los procedimientos con fecha entre paréntesis. Si hay procedimientos compuestos de un mismo tiempo quirúrgico, agrúpalos como un evento único.", "priority": "alta", "active": True},
        {"text": "3. TOPOGRAFÍA Y TÉCNICA: Específica la localización anatómica exacta (sitio de inserción, lecho vascular). En cirugías, anota brevemente el hallazgo intraoperatorio.", "priority": "alta", "active": True},
        {"text": "4. DURACIÓN DE SOPORTES: Para Asistencia Respiratoria Mecánica (ARM) e Infusiones/Nutrición enteral es obligatorio detallar las fechas de inicio a fin.", "priority": "alta", "active": True},
        {"text": "5. FILTRO DE LABORATORIO: Los exámenes de sangre de rutina están excluidos, salvo hallazgo drástico ausente en evolución.", "priority": "normal", "active": True},
    ]

    await db.golden_rules.update_one(
        {"_id": "procedimientos"},
        {"$set": {"rules": procedimientos_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema_agente"}},
        upsert=True
    )

    # 2. Estudios
    estudios_rules = [
        {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Estudios' como el registro de estudios diagnósticos por imágenes (Rx, Eco, RM, TC) y funcionales (ECG, EEG, Espirometría) relevantes para la EPC. Para cada uno captura: tipo, fecha realización, hallazgos principales y si fue normal/patológico. Solo incluye los que tuvieron impacto en la toma de decisiones clínicas.", "priority": "critica", "active": True},
        {"text": "1. FILTRO DE RELEVANCIA Y ALCANCE: Incluye EXCLUSIVAMENTE estudios por Imágenes, Endoscopias, Anatomía Patológica y Microbiología. Quedan terminalmente PROHIBIDOS los laboratorios de sangre de rutina.", "priority": "critica", "active": True},
        {"text": "2. PRECISIÓN TÉCNICA DEL INFORME: Escribe el nombre completo y exacto. Especifica técnica ('con/sin contraste'), la vía, y el lecho vascular analizado en Doppler/AngioTAC.", "priority": "alta", "active": True},
        {"text": "3. RESUMEN DE HALLAZGOS: Acompaña cada estudio con una descripción ultraconcisa de su hallazgo más relevante (Ej: 'TAC de Tórax: múltiples fracturas costales').", "priority": "alta", "active": True},
        {"text": "4. CULTIVOS Y ANATOMÍA PATOLÓGICA: Para microbiológicos, especifica sitio, germen aislado y sensibilidad. Para anatomía patológica, la conclusión macro/microscópica.", "priority": "alta", "active": True},
        {"text": "5. CRONOLOGÍA Y REPETICIONES: Enumera con su Fecha de realización estricta entre paréntesis. ELIMINA la hora. Compila repeticiones resumiendo si hubo empeoramiento.", "priority": "alta", "active": True},
        {"text": "6. ESTUDIOS FALLIDOS/SUSPENDIDOS: Si un estudio de alta relevancia no pudo completarse, súmalo a la lista indicando explícitamente el motivo de cancelación.", "priority": "normal", "active": True},
    ]

    await db.golden_rules.update_one(
        {"_id": "estudios"},
        {"$set": {"rules": estudios_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema_agente"}},
        upsert=True
    )

    # 3. Interconsultas
    interconsultas_rules = [
        {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Interconsultas' como las evaluaciones solicitadas a otros especialistas o servicios. Incluyen IC clínicas (Cardiología, Neurología), quirúrgicas (Traumatología, Cirugía General) y de apoyo (Kinesiología, Nutrición, Salud Mental). Para cada interconsulta registrada, debes capturar ÚNICAMENTE la especialidad consultada.", "priority": "critica", "active": True},
        {"text": "1. PUREZA DE ESPECIALIDAD: Extrae únicamente valoraciones formales de especialistas externos al médico a cargo. Omite pasadas de sala del médico tratante base.", "priority": "critica", "active": True},
        {"text": "2. FORMATO MINIMALISTA ABSOLUTO: Enumera ÚNICAMENTE el nombre de la especialidad (Ej: Hematología, Infectología). Queda TERMINANTEMENTE PROHIBIDO incluir fechas, motivos, diagnósticos, resultados o conductas.", "priority": "critica", "active": True},
        {"text": "3. DEDUPLICACIÓN ESTRICTA: Agrupa cualquier repetición. Si Infectología pasó 5 veces, solo debe aparecer UNA sola vez en toda la lista.", "priority": "alta", "active": True},
        {"text": "4. PROTOCOLOS DE AISLAMIENTO: (Excepción): Si la IC resultó en un aislamiento infectológico (Ej: Aislamiento de contacto), es la ÚNICA información anexa permitida.", "priority": "alta", "active": True},
    ]

    await db.golden_rules.update_one(
        {"_id": "interconsultas"},
        {"$set": {"rules": interconsultas_rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema_agente"}},
        upsert=True
    )

    print("Definiciones CORE inyectadas exitosamente en MongoDB.")

if __name__ == "__main__":
    asyncio.run(apply_core_definitions())
