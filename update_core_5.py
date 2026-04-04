import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "core_1", "text": "1. LECTURA 100% ESTRICTA: Analiza obligatoriamente todo el contexto provisto sin realizar sesgos iniciales ni resúmenes prematuros. Prohibido truncar o ignorar datos de fechas antiguas; considera toda la historia clínica como evidencia activa.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_2", "text": "2. TOLERANCIA CERO A ALUCINACIONES (CERO INVENCIÓN): Solo puedes usar datos presentes textualmente en la HCE. Prohibido deducir diagnósticos, inventar fechas no documentadas o suponer resoluciones de síntomas. Si una sección carece de datos, déjala estrictamente vacía.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_3", "text": "3. FIDELIDAD ESTILÍSTICA ('PASE ENTRE COLEGAS'): Redacta utilizando jerga médico-técnica, densa y formal. Formula el texto como si fuese un sumario de un especialista para derivar a otro especialista. Nunca uses lenguaje coloquial o dirigido al paciente.", "priority": "alta", "active": True, "processed": True},
        {"id": "core_4", "text": "4. FILTRADO CLÍNICO DE RUIDO (LOOK VS DO): Ignora y excluye sistemáticamente rutinas de enfermería (controles vitales, valoraciones, higiene) y fluidos de mantenimiento (dextrosa basal, solución fisiológica, plan de hidratación) a menos que su inicio o suspensión representen la resolución de un shock o hito crítico.", "priority": "alta", "active": True, "processed": True},
        {"id": "core_5", "text": "5. CRONOLOGÍA SECUENCIAL ESTRICTA: Relata los eventos en orden cronológico ascendente. Estructura general: 1) Antecedentes base relevantes, 2) Motivo fáctico de la internación actual, 3) Evolución médica y conductual por días o periodos, 4) Condición final. Jamás adelantes desenlaces de días futuros al inicio del texto clínico.", "priority": "alta", "active": True, "processed": True},
        {"id": "core_6", "text": "6. DESPERSONALIZACIÓN IMPERSONAL: Escribe estrictamente en formato pasivo y abstracto de tercera persona. Prohibido el uso de la primera persona singular o plural (nunca uses 'indiqué', 'observamos', 'decidimos'). Usa fórmulas universales como 'se constata', 'paciente evoluciona', 'se indica'.", "priority": "normal", "active": True, "processed": True},
        {"id": "core_7", "text": "7. AGRUPACIÓN LÓGICA CONTINUA (ANTI-DUPLICACIÓN): Detecta patrones de continuidad terapéutica. Si una conducta clínica o esquema (ej. infusión antibiótica o aislamiento) persiste sin cambios por varios días, comprímelos en un solo enunciado conclusivo (Ej: 'Cumplió esquema de Ceftriaxona por 7 días con buena tolerancia'). No documentes reiterativamente la misma conducta diaria.", "priority": "alta", "active": True, "processed": True},
        {"id": "core_8", "text": "8. SALVAGUARDA FORENSE (ÓBITO Y SHOCK): Ante el evento de un fallecimiento o paro cardiorrespiratorio, cambia inmediatamente el registro a un formato pericial-descriptivo de máxima precisión. Detalla obligatoriamente: hora exacta, signos clínicos de compromiso severo, terapias completas de reanimación aplicadas, respuesta y, si se declaran, las causas de muerte directas e intervinientes secuenciales.", "priority": "critica", "active": True, "processed": True},
        {"id": "core_9", "text": "9. BLINDAJE ANTI-EPICRISIS PREVIAS (FUENTE PURA): Queda estrictamente prohibido utilizar, extraer información o copiar contenido de cualquier sección etiquetada o titulada como 'Epicrisis' dentro de la Historia Clínica y plantillas documentales. La información debe sintetizarse desde las evoluciones nativas, partes diarios y registros operativos puros, asegurando que no se recicle un resumen anterior.", "priority": "critica", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "core"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    print("9 Core rules optimized in DB.")

if __name__ == "__main__":
    asyncio.run(update())
