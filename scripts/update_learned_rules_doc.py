#!/usr/bin/env python3
"""
Script para actualizar el documento REGLAS_EPC_APRENDIZAJE.md
con las reglas actuales aprendidas del feedback.

Uso:
    python scripts/update_learned_rules_doc.py
"""

import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/ainstein/ainstein_be')

from datetime import datetime


async def main():
    from app.services.feedback_insights_service import get_feedback_insights_service
    
    print("📊 Obteniendo insights de feedback...")
    service = get_feedback_insights_service()
    insights = await service.get_insights(force_refresh=True)
    
    # Preparar contenido del documento
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    content = f"""# Reglas EPC por Aprendizaje

> 📚 **Este documento contiene las reglas que la IA aprende automáticamente** del feedback de los evaluadores médicos.

---

## 🤖 Sistema de Aprendizaje Continuo

El sistema **FeedbackInsightsService** analiza el feedback de los evaluadores y genera reglas automáticas que se inyectan en el prompt del LLM.

### Fuentes de Aprendizaje:

| Fuente | Descripción |
|--------|-------------|
| **Calificaciones** | ok / partial / bad por sección |
| **3 Preguntas Obligatorias** | ¿Omisiones? ¿Repeticiones? ¿Confuso? |
| **Comentarios** | Texto libre de los evaluadores |

---

## 📊 Estadísticas de Feedback Actuales

### Última actualización: {now}

| Sección | Total | OK | Parcial | Malo | % Negativo |
|---------|-------|-----|---------|------|------------|
"""
    
    # Agregar estadísticas por sección
    section_stats = insights.get("section_stats", {})
    section_names = {
        "motivo_internacion": "Motivo Internación",
        "evolucion": "Evolución",
        "procedimientos": "Procedimientos",
        "interconsultas": "Interconsultas",
        "medicacion": "Medicación",
        "indicaciones_alta": "Indicaciones Alta",
        "recomendaciones": "Recomendaciones",
        "diagnostico_principal": "Diagnóstico Principal",
        "diagnosticos_secundarios": "Diagnósticos Secundarios",
    }
    
    for section_key, display_name in section_names.items():
        stats = section_stats.get(section_key, {})
        total = stats.get("total", 0)
        ok = stats.get("ok", 0)
        partial = stats.get("partial", 0)
        bad = stats.get("bad", 0)
        neg_rate = f"{int((partial + bad) / total * 100)}%" if total > 0 else "-"
        
        if total > 0:
            content += f"| {display_name} | {total} | {ok} | {partial} | {bad} | {neg_rate} |\n"
        else:
            content += f"| {display_name} | - | - | - | - | - |\n"
    
    # Agregar reglas generadas
    rules = insights.get("rules", [])
    content += f"""
---

## 📋 Reglas Generadas por el Sistema ({len(rules)} activas)

Las reglas se generan cuando:
- ≥2 reportes de **omisiones** en una sección
- ≥2 reportes de **repeticiones** en una sección
- ≥2 reportes de contenido **confuso/erróneo**
- >30% de feedback negativo en una sección

### Reglas Activas:

"""
    
    if rules:
        for i, rule in enumerate(rules, 1):
            content += f"{i}. {rule}\n"
    else:
        content += "*No hay reglas activas aún. Se generarán conforme los evaluadores califiquen las EPCs.*\n"
    
    # Agregar estadísticas de las 3 preguntas
    questions = insights.get("questions_by_section", {})
    content += """
---

## 🔄 Patrones Detectados por Sección (3 Preguntas)

| Sección | Omisiones | Repeticiones | Confuso |
|---------|-----------|--------------|---------|
"""
    
    for section_key, display_name in section_names.items():
        q = questions.get(section_key, {})
        omissions = q.get("omissions", 0)
        repetitions = q.get("repetitions", 0)
        confusing = q.get("confusing", 0)
        if omissions or repetitions or confusing:
            content += f"| {display_name} | {omissions} | {repetitions} | {confusing} |\n"
    
    # Agregar secciones problemáticas
    problem_sections = insights.get("problem_sections", [])
    content += f"""
---

## ⚠️ Secciones Problemáticas

"""
    if problem_sections:
        for section in problem_sections:
            name = section_names.get(section, section)
            content += f"- **{name}**: Requiere atención especial (>20% feedback negativo)\n"
    else:
        content += "*No hay secciones con problemas significativos actualmente.*\n"
    
    # Footer
    content += f"""
---

## 🔗 Referencias

- **Documento de Reglas de Oro**: [REGLAS_GENERACION_EPC.md](./REGLAS_GENERACION_EPC.md)
- **Servicio de Insights**: `app/services/feedback_insights_service.py`
- **Colección MongoDB**: `epc_feedback`
- **Total feedbacks analizados**: {insights.get('total_feedbacks_analyzed', 0)}

---

## Versionado

- **Última actualización**: {now}
- **Generado automáticamente** por `scripts/update_learned_rules_doc.py`
"""
    
    # Escribir archivo
    output_path = "/home/ubuntu/ainstein/ainstein_be/docs/REGLAS_EPC_APRENDIZAJE.md"
    with open(output_path, "w") as f:
        f.write(content)
    
    print(f"✅ Documento actualizado: {output_path}")
    print(f"   - {len(rules)} reglas activas")
    print(f"   - {insights.get('total_feedbacks_analyzed', 0)} feedbacks analizados")


if __name__ == "__main__":
    asyncio.run(main())
