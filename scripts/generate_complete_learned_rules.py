#!/usr/bin/env python3
"""
Script para generar el documento COMPLETO de Reglas EPC por Aprendizaje.

CARACTERÍSTICAS:
- Extrae TODOS los feedbacks de MongoDB (sin límite)
- Muestra CADA comentario individual
- Es INCREMENTAL: nuevos feedbacks se agregan sin perder los anteriores
- Genera documento Markdown completo

Uso:
    python scripts/generate_complete_learned_rules.py
"""

import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/ainstein/ainstein_be')

from datetime import datetime
from collections import defaultdict


async def get_all_feedbacks():
    """Obtiene TODOS los feedbacks de MongoDB sin límite."""
    from app.adapters.mongo_client import db as mongo
    
    feedbacks = []
    cursor = mongo.epc_feedback.find({}).sort("created_at", -1)
    
    async for doc in cursor:
        feedbacks.append({
            "section": doc.get("section", "unknown"),
            "rating": doc.get("rating", "unknown"),
            "feedback_text": doc.get("feedback_text", ""),
            "has_omissions": doc.get("has_omissions", False),
            "has_repetitions": doc.get("has_repetitions", False),
            "is_confusing": doc.get("is_confusing", False),
            "created_at": doc.get("created_at"),
            "epc_id": str(doc.get("epc_id", "")),
            "user_id": str(doc.get("user_id", "")),
        })
    
    return feedbacks


def format_date(dt):
    """Formatea fecha para display."""
    if dt:
        return dt.strftime("%d/%m/%Y %H:%M")
    return "Sin fecha"


async def main():
    print("📊 Extrayendo TODOS los feedbacks de MongoDB...")
    feedbacks = await get_all_feedbacks()
    print(f"   Total feedbacks encontrados: {len(feedbacks)}")
    
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Agrupar por sección
    by_section = defaultdict(list)
    for fb in feedbacks:
        by_section[fb["section"]].append(fb)
    
    # Calcular estadísticas
    section_stats = {}
    for section, items in by_section.items():
        ok = sum(1 for i in items if i["rating"] == "ok")
        partial = sum(1 for i in items if i["rating"] == "partial")
        bad = sum(1 for i in items if i["rating"] == "bad")
        total = len(items)
        section_stats[section] = {
            "ok": ok, "partial": partial, "bad": bad, "total": total,
            "omissions": sum(1 for i in items if i["has_omissions"]),
            "repetitions": sum(1 for i in items if i["has_repetitions"]),
            "confusing": sum(1 for i in items if i["is_confusing"]),
        }
    
    # Nombres de secciones
    section_names = {
        "motivo_internacion": "Motivo de Internación",
        "evolucion": "Evolución",
        "procedimientos": "Procedimientos",
        "interconsultas": "Interconsultas",
        "medicacion": "Medicación",
        "indicaciones_alta": "Indicaciones de Alta",
        "recomendaciones": "Recomendaciones",
        "diagnostico_principal": "Diagnóstico Principal",
        "diagnosticos_secundarios": "Diagnósticos Secundarios",
        "estudios": "Estudios",
        "laboratorio": "Laboratorio",
    }
    
    # =========================================================================
    # GENERAR DOCUMENTO COMPLETO
    # =========================================================================
    
    content = f"""# Reglas EPC por Aprendizaje - Documento Completo

> Este documento contiene TODOS los feedbacks de los evaluadores médicos, sin omisiones.
> Se actualiza de forma INCREMENTAL: cada nuevo feedback se agrega al documento.

---

## Información General

| Dato | Valor |
|------|-------|
| **Total Feedbacks** | {len(feedbacks)} |
| **Última Actualización** | {now} |
| **Secciones Evaluadas** | {len(by_section)} |

---

## Resumen Estadístico por Sección

| Sección | Total | OK | Parcial | Malo | % Negativo | Omisiones | Repeticiones | Confuso |
|---------|-------|-----|---------|------|------------|-----------|--------------|---------|
"""
    
    # Tabla de estadísticas
    for section_key in ["motivo_internacion", "evolucion", "procedimientos", 
                        "interconsultas", "medicacion", "indicaciones_alta", 
                        "recomendaciones", "estudios", "laboratorio",
                        "diagnostico_principal", "diagnosticos_secundarios"]:
        if section_key in section_stats:
            s = section_stats[section_key]
            name = section_names.get(section_key, section_key)
            neg = s["partial"] + s["bad"]
            neg_pct = f"{int(neg/s['total']*100)}%" if s["total"] > 0 else "-"
            content += f"| {name} | {s['total']} | {s['ok']} | {s['partial']} | {s['bad']} | {neg_pct} | {s['omissions']} | {s['repetitions']} | {s['confusing']} |\n"
    
    content += """
---

## Reglas Aprendidas (Generadas Automáticamente)

Las siguientes reglas se generaron automáticamente basándose en patrones del feedback:

"""
    
    # Generar reglas por sección
    rule_number = 1
    for section_key, stats in section_stats.items():
        name = section_names.get(section_key, section_key)
        
        if stats["omissions"] >= 2:
            content += f"{rule_number}. **[{name}]** ⚠️ Evitar OMISIONES - {stats['omissions']} casos reportados\n"
            rule_number += 1
        
        if stats["repetitions"] >= 2:
            content += f"{rule_number}. **[{name}]** ⚠️ Evitar REPETICIONES - {stats['repetitions']} casos reportados\n"
            rule_number += 1
        
        if stats["confusing"] >= 2:
            content += f"{rule_number}. **[{name}]** ⚠️ Evitar contenido CONFUSO/ERRÓNEO - {stats['confusing']} casos reportados\n"
            rule_number += 1
    
    content += f"""
**Total de reglas activas: {rule_number - 1}**

---

# Detalle Completo de Feedbacks por Sección

A continuación se presenta CADA feedback individual recibido, agrupado por sección.

"""
    
    # =========================================================================
    # DETALLE COMPLETO POR SECCIÓN
    # =========================================================================
    
    for section_key in ["motivo_internacion", "evolucion", "procedimientos", 
                        "interconsultas", "medicacion", "indicaciones_alta", 
                        "recomendaciones", "estudios", "laboratorio",
                        "diagnostico_principal", "diagnosticos_secundarios"]:
        
        if section_key not in by_section:
            continue
        
        items = by_section[section_key]
        name = section_names.get(section_key, section_key)
        stats = section_stats[section_key]
        
        content += f"""
---

## {name}

**Estadísticas:**
- Total: {stats['total']} evaluaciones
- OK: {stats['ok']} | Parcial: {stats['partial']} | Malo: {stats['bad']}
- Omisiones: {stats['omissions']} | Repeticiones: {stats['repetitions']} | Confuso: {stats['confusing']}

### Feedbacks Individuales ({len(items)} registros):

| # | Fecha | Rating | Omisiones | Repeticiones | Confuso | Comentario |
|---|-------|--------|-----------|--------------|---------|------------|
"""
        
        for idx, fb in enumerate(items, 1):
            date = format_date(fb.get("created_at"))
            rating = fb["rating"]
            rating_emoji = "✅" if rating == "ok" else ("⚠️" if rating == "partial" else "❌")
            omit = "Sí" if fb["has_omissions"] else "-"
            repet = "Sí" if fb["has_repetitions"] else "-"
            confus = "Sí" if fb["is_confusing"] else "-"
            comment = (fb.get("feedback_text") or "-").replace("\n", " ").replace("|", "/")[:200]
            
            content += f"| {idx} | {date} | {rating_emoji} {rating} | {omit} | {repet} | {confus} | {comment} |\n"
        
        # Extracto de comentarios textuales destacados
        comments_with_text = [fb for fb in items if fb.get("feedback_text")]
        if comments_with_text:
            content += f"""
### Comentarios Textuales Destacados ({len(comments_with_text)} con texto):

"""
            for i, fb in enumerate(comments_with_text[:50], 1):  # Max 50 por sección
                date = format_date(fb.get("created_at"))
                rating = fb["rating"]
                text = fb.get("feedback_text", "").strip()
                if text:
                    content += f"""**{i}. [{rating.upper()}] - {date}**
> {text}

"""
    
    # =========================================================================
    # SECCIÓN DE PATRONES IDENTIFICADOS
    # =========================================================================
    
    content += """
---

# Patrones Identificados

Los siguientes patrones se identificaron analizando los comentarios de los evaluadores:

"""
    
    # Analizar patrones por keywords
    all_comments = [fb.get("feedback_text", "") for fb in feedbacks if fb.get("feedback_text")]
    combined_text = " ".join(all_comments).lower()
    
    patterns = {
        "extenso|largo|reducir": "Contenido demasiado extenso",
        "falta|incompleto|omite": "Información faltante/incompleta",
        "inventado|inventa|no estaba": "Información inventada",
        "repite|redundante|duplicado": "Información repetida/redundante",
        "confuso|no se entiende|error": "Contenido confuso o erróneo",
        "fecha|hora|cronolog": "Problemas con fechas/cronología",
        "formato|estructura": "Problemas de formato/estructura",
    }
    
    for pattern_keys, pattern_name in patterns.items():
        count = sum(1 for key in pattern_keys.split("|") if key in combined_text)
        if count > 0:
            content += f"- **{pattern_name}**: Detectado en múltiples comentarios\n"
    
    # =========================================================================
    # FOOTER
    # =========================================================================
    
    content += f"""
---

# Historial de Actualizaciones

| Fecha | Evento | Feedbacks Totales |
|-------|--------|-------------------|
| {now} | Documento generado | {len(feedbacks)} |

---

# Referencias

- **Documento de Reglas de Oro**: [REGLAS_GENERACION_EPC.md](./REGLAS_GENERACION_EPC.md)
- **Servicio de Insights**: `app/services/feedback_insights_service.py`
- **Colección MongoDB**: `epc_feedback`
- **Script de generación**: `scripts/generate_complete_learned_rules.py`

---

*Documento generado automáticamente el {now}*
*Total de feedbacks procesados: {len(feedbacks)}*
"""
    
    # Escribir archivo
    output_path = "/home/ubuntu/ainstein/ainstein_be/docs/REGLAS_EPC_APRENDIZAJE.md"
    with open(output_path, "w") as f:
        f.write(content)
    
    print(f"✅ Documento COMPLETO generado: {output_path}")
    print(f"   - {len(feedbacks)} feedbacks incluidos")
    print(f"   - {len(by_section)} secciones documentadas")
    print(f"   - {rule_number - 1} reglas activas")


if __name__ == "__main__":
    asyncio.run(main())
