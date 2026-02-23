#!/usr/bin/env python3
"""
Script para regenerar todas las reglas de aprendizaje basándose en todos los feedbacks existentes.
Las reglas se crean con estado "applied" (ya procesadas).
"""
import asyncio
import os
import sys

# Agregar el directorio raíz del backend al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def regenerate_all_rules():
    from app.adapters.mongo_client import db as mongo
    from datetime import datetime
    
    # El cliente mongo ya está conectado (motor client)
    print("📊 Contando feedbacks existentes...")
    feedbacks_cursor = mongo.epc_feedback.find({"feedback_text": {"$exists": True, "$ne": ""}})
    feedbacks = await feedbacks_cursor.to_list(None)
    print(f"   Total feedbacks con texto: {len(feedbacks)}")
    
    if not feedbacks:
        print("❌ No hay feedbacks con texto. Saliendo.")
        return
    
    # Agrupar feedbacks por sección
    by_section = {}
    for fb in feedbacks:
        section = fb.get("section_key", "general")
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(fb)
    
    print(f"📂 Secciones encontradas: {list(by_section.keys())}")
    
    # Limpiar reglas y problemas existentes
    print("\n🗑️  Limpiando reglas y problemas anteriores...")
    del_rules = await mongo.learning_rules.delete_many({})
    del_problems = await mongo.learning_problems.delete_many({})
    print(f"   - Reglas eliminadas: {del_rules.deleted_count}")
    print(f"   - Problemas eliminados: {del_problems.deleted_count}")
    
    # Importar el analizador
    from app.services.feedback_llm_analyzer import get_feedback_llm_analyzer
    analyzer = get_feedback_llm_analyzer()
    
    print("\n🤖 Ejecutando análisis LLM para regenerar reglas...")
    print("   Esto puede tomar varios minutos dependiendo del número de secciones...\n")
    
    # Forzar regeneración completa
    try:
        result = await analyzer.analyze_all_sections(force_refresh=True)
    except Exception as e:
        print(f"⚠️  Error en LLM (usando fallback): {e}")
        result = {"sections": []}
    
    sections = result.get("sections", [])
    total_rules = sum(len(s.get("rules", [])) for s in sections)
    total_problems = sum(len(s.get("problems", [])) for s in sections)
    
    print(f"\n✅ Análisis completado:")
    print(f"   - Secciones analizadas: {len(sections)}")
    print(f"   - Reglas generadas: {total_rules}")
    print(f"   - Problemas detectados: {total_problems}")
    
    # Marcar TODAS las reglas como "applied"
    print("\n📝 Marcando todas las reglas como 'aplicadas'...")
    update_result = await mongo.learning_rules.update_many(
        {},
        {
            "$set": {
                "status": "applied",
                "applied_at": datetime.utcnow(),
            }
        }
    )
    print(f"   - Reglas actualizadas: {update_result.modified_count}")
    
    # Contar reglas finales
    rules_count = await mongo.learning_rules.count_documents({})
    problems_count = await mongo.learning_problems.count_documents({})
    
    print(f"\n📊 Estado final de MongoDB:")
    print(f"   - learning_rules: {rules_count} documentos")
    print(f"   - learning_problems: {problems_count} documentos")
    
    # Mostrar algunas reglas de ejemplo
    if rules_count > 0:
        print("\n📋 Ejemplo de reglas generadas:")
        sample_rules = await mongo.learning_rules.find().limit(5).to_list(5)
        for rule in sample_rules:
            print(f"   • [{rule.get('section')}] {rule.get('text', '')[:80]}...")
    
    print("\n✅ ¡Regeneración completada!")

if __name__ == "__main__":
    asyncio.run(regenerate_all_rules())
