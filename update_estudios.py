import asyncio
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime, timezone

async def update():
    db = get_mongo_db()
    rules = [
        {"id": "est_1", "text": "1. FILTRO DE RELEVANCIA Y ALCANCE: Incluye EXCLUSIVAMENTE estudios por Imágenes (RX, TAC, RMN, Ecografías), Endoscopias, Anatomía Patológica (Biopsias/Citologías) y Microbiología (Cultivos). Quedan terminalmente PROHIBIDOS los laboratorios de sangre de rutina (estos deben agruparse en la sección Procedimientos).", "priority": "critica", "active": True, "processed": True},
        {"id": "est_2", "text": "2. PRECISIÓN TÉCNICA DEL INFORME: Escribe el nombre completo y exacto del estudio. Especifica la técnica detallada: indica siempre si es 'con o sin contraste', la vía (Ej: Ecocardiograma Transesofágico vs Transtorácico), y en estudios vasculares (AngioTAC/Doppler) detalla el lecho vascular analizado.", "priority": "alta", "active": True, "processed": True},
        {"id": "est_3", "text": "3. RESUMEN DE HALLAZGOS: No listes únicamente el nombre del estudio. Debes acompañar cada estudio con una descripción ultraconcisa de su hallazgo más relevante que contribuya al diagnóstico o evolución (Ej: 'TAC de Tórax: múltiples fracturas costales').", "priority": "alta", "active": True, "processed": True},
        {"id": "est_4", "text": "4. CULTIVOS Y ANATOMÍA PATOLÓGICA: Para los estudios microbiológicos, especifica sitio de muestra, germen aislado y sensibilidad antibiótica (antibiograma). Para anatomía patológica, detalla la conclusión macro/microscópica de relevancia.", "priority": "alta", "active": True, "processed": True},
        {"id": "est_5", "text": "5. CRONOLOGÍA Y REPETICIONES: Enumera los estudios con su Fecha de realización estricta entre paréntesis. ELIMINA la hora. Si un estudio se repitió en el tiempo, compila sus fechas y resume brevemente si hubo un cambio evolutivo o empeoramiento entre ellos.", "priority": "alta", "active": True, "processed": True},
        {"id": "est_6", "text": "6. ESTUDIOS FALLIDOS/SUSPENDIDOS: Si un estudio de alta relevancia fue solicitado pero no pudo completarse (ej. contraindicación, falta de colaboración, problemas técnicos), debes sumarlo a la lista indicando explícitamente el motivo de cancelación.", "priority": "normal", "active": True, "processed": True},
    ]
    await db.golden_rules.update_one(
        {"_id": "estudios"},
        {"$set": {"rules": rules, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": "sistema"}}
    )
    print("estudios replaced 72 -> 6 rules")

if __name__ == "__main__":
    asyncio.run(update())
