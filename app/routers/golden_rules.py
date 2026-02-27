"""
Golden Rules API — Manages EPC generation rules.
Sections are stored in MongoDB collection 'golden_rules'.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user, get_db
from app.adapters.mongo_client import get_mongo_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/golden-rules", tags=["golden-rules"])

# ──────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────

class RuleItem(BaseModel):
    id: Optional[str] = None
    text: str
    priority: str = "normal"  # critica | alta | normal
    active: bool = True


class RuleSection(BaseModel):
    key: str
    title: str
    rules: List[RuleItem]


class RuleSectionUpdate(BaseModel):
    rules: List[RuleItem]


# ──────────────────────────────────────────────────────────────────────
# Default sections and seed rules (from REGLAS_GENERACION_EPC.md)
# ──────────────────────────────────────────────────────────────────────

DEFAULT_SECTIONS = [
    {
        "key": "motivo",
        "title": "Motivo de internación",
        "rules": [
            {"text": "El motivo de internación se trunca automáticamente a máximo 10 palabras.", "priority": "critica", "active": True},
            {"text": "Si no se encuentra en la HCE, se infiere con IA desde la evolución médica (máx 30 palabras, entre paréntesis).", "priority": "critica", "active": True},
            {"text": "Formato: resumen lógico, sin fechas, sin nombre del paciente.", "priority": "alta", "active": True},
            {"text": "Orden de búsqueda: entrMotivoConsulta → Plantilla ANAMNESIS → Plantilla RESUMEN INTERNACION → Primera evolución → IA fallback.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "evolucion",
        "title": "Evolución",
        "rules": [
            {"text": "La evolución se construye EXCLUSIVAMENTE con registros de tipo EVOLUCION MEDICA, INGRESO DE PACIENTE, PARTE QUIRURGICO y PARTE PROCEDIMIENTO.", "priority": "critica", "active": True},
            {"text": "Se descartan: HOJA DE ENFERMERIA, CONTROL DE ENFERMERIA, BALANCE HIDROELECTROLITICO, EVOLUCION DE INTERCONSULTA, INDICACION.", "priority": "critica", "active": True},
            {"text": "Estilo médico técnico, como pase entre colegas.", "priority": "alta", "active": True},
            {"text": "NO inventar datos. Si una sección no tiene información, dejar vacío.", "priority": "critica", "active": True},
        ],
    },
    {
        "key": "procedimientos",
        "title": "Procedimientos",
        "rules": [
            {"text": "Los procedimientos se agrupan por nombre y muestran fecha(s) entre paréntesis.", "priority": "alta", "active": True},
            {"text": "Laboratorios se agrupan en un solo ítem: 'Laboratorios realizados (N estudios)'.", "priority": "normal", "active": True},
            {"text": "Se excluyen procedimientos genéricos: ingreso, enfermería, controles, higiene.", "priority": "alta", "active": True},
            {"text": "Imágenes (RX, TAC, RMN, Eco) van en sección Estudios separada.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "interconsultas",
        "title": "Interconsultas",
        "rules": [
            {"text": "Se agrupan por especialidad, mostrando solo la primera fecha de cada una.", "priority": "alta", "active": True},
            {"text": "Sin duplicados (misma fecha + misma especialidad).", "priority": "normal", "active": True},
            {"text": "Formato: Especialidad (DD/MM/YYYY).", "priority": "normal", "active": True},
        ],
    },
    {
        "key": "medicacion",
        "title": "Medicación",
        "rules": [
            {"text": "Se clasifica en 'previa' (medicación habitual) e 'internación' (indicada durante la hospitalización).", "priority": "alta", "active": True},
            {"text": "Antihipertensivos orales (losartán, enalapril, etc.) marcados como 'internación' se corrigen a 'previa'.", "priority": "normal", "active": True},
            {"text": "Antibióticos IV (vancomicina, meropenem, etc.) marcados como 'previa' se corrigen a 'internación'.", "priority": "normal", "active": True},
            {"text": "Se ordenan alfabéticamente por nombre de fármaco.", "priority": "normal", "active": True},
        ],
    },
    {
        "key": "obito",
        "title": "Detección de Óbito",
        "rules": [
            {"text": "Si se detecta fallecimiento, el último párrafo DEBE comenzar con: PACIENTE OBITÓ - Fecha: [fecha] Hora: [hora].", "priority": "critica", "active": True},
            {"text": "Indicaciones de alta y recomendaciones se vacían en caso de óbito.", "priority": "critica", "active": True},
            {"text": "Se eliminan frases contradictorias: 'alta médica', 'evolución favorable', 'egreso a domicilio'.", "priority": "alta", "active": True},
            {"text": "Anti-keywords (revierte, exitosa, mejoría, alta médica) invalidan la detección de muerte.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "pdf",
        "title": "Exportación PDF",
        "rules": [
            {"text": "Orden: Título, Datos clínicos, Motivo, Evolución, Procedimientos, Interconsultas, Indicaciones de alta.", "priority": "alta", "active": True},
            {"text": "Medicación, notas al alta y recomendaciones NO aparecen en el PDF.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "learned",
        "title": "Reglas aprendidas",
        "rules": [],
    },
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

async def _ensure_seeded(mongo):
    """Seed default rules if collection is empty."""
    count = await mongo.golden_rules.count_documents({})
    if count == 0:
        for sec in DEFAULT_SECTIONS:
            # Add IDs to rules and mark as processed
            for i, r in enumerate(sec["rules"]):
                r["id"] = f"{sec['key']}_{i+1}"
                r["processed"] = True
            await mongo.golden_rules.insert_one({
                "_id": sec["key"],
                "title": sec["title"],
                "rules": sec["rules"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system",
            })
        log.info("[GoldenRules] Seeded %d sections", len(DEFAULT_SECTIONS))


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Dict[str, Any]])
async def get_all_rules(user=Depends(get_current_user)):
    """Return all golden rule sections. Learned section includes approved dictionary mappings."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    # Auto-migrate: mark existing rules as processed if field missing
    async for doc in mongo.golden_rules.find({}):
        rules = doc.get("rules", [])
        needs_update = False
        for r in rules:
            if "processed" not in r:
                r["processed"] = True
                needs_update = True
        if needs_update:
            await mongo.golden_rules.update_one(
                {"_id": doc["_id"]},
                {"$set": {"rules": rules}},
            )
    
    cursor = mongo.golden_rules.find({})
    sections = []
    async for doc in cursor:
        sections.append({
            "key": doc["_id"],
            "title": doc.get("title", doc["_id"]),
            "rules": doc.get("rules", []),
            "updated_at": doc.get("updated_at"),
            "updated_by": doc.get("updated_by"),
        })
    
    # ── Merge approved dictionary mappings into "learned" section ──
    SECTION_LABELS = {
        "motivo_internacion": "Motivo internación",
        "evolucion": "Evolución",
        "procedimientos": "Procedimientos",
        "interconsultas": "Interconsultas",
        "medicacion": "Medicación",
        "indicaciones_alta": "Indicaciones alta",
        "recomendaciones": "Recomendaciones",
    }
    
    try:
        dict_cursor = mongo.section_mapping_dictionary.find().sort("frequency", -1).limit(200)
        dict_rules = []
        async for doc in dict_cursor:
            item = doc.get("item_pattern", "")
            target = doc.get("target_section", "")
            freq = doc.get("frequency", 1)
            target_label = SECTION_LABELS.get(target, target)
            
            rule = {
                "id": f"dict_{doc.get('_id', '')}",
                "text": f"'{item}' → {target_label} (aprendido de {freq} corrección{'es' if freq > 1 else ''})",
                "priority": "alta" if freq >= 3 else "normal",
                "active": True,
                "source": "dictionary",
                "item_pattern": item,
                "target_section": target,
                "frequency": freq,
            }
            # Preserve processed state from dictionary
            if doc.get("processed"):
                rule["processed"] = True
                rule["processed_at"] = doc.get("processed_at")
                rule["processed_by"] = doc.get("processed_by")
            
            dict_rules.append(rule)
        
        # Find or create learned section and append dict rules
        learned = next((s for s in sections if s["key"] == "learned"), None)
        if learned:
            # Keep manually added rules, append dict rules
            manual_rules = [r for r in learned["rules"] if r.get("source") != "dictionary"]
            learned["rules"] = manual_rules + dict_rules
        elif dict_rules:
            sections.append({
                "key": "learned",
                "title": "Reglas aprendidas",
                "rules": dict_rules,
                "updated_at": None,
                "updated_by": "sistema",
            })
        
        if dict_rules:
            log.info("[GoldenRules] Merged %d dictionary rules into 'learned' section", len(dict_rules))
    except Exception as e:
        log.warning("[GoldenRules] Could not merge dictionary rules: %s", e)
    
    # Sort by predefined order
    order = ["motivo", "evolucion", "procedimientos", "interconsultas", "medicacion", "obito", "pdf", "learned"]
    sections.sort(key=lambda s: order.index(s["key"]) if s["key"] in order else 99)
    
    return sections


@router.put("/{section_key}")
async def update_section_rules(
    section_key: str,
    body: RuleSectionUpdate,
    user=Depends(get_current_user),
):
    """Update rules for a specific section."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    # Verify section exists
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    # Build lookup of existing rules by id to detect changes
    old_rules_map = {}
    for r in existing.get("rules", []):
        if r.get("id"):
            old_rules_map[r["id"]] = r
    
    # Only mark rules as unprocessed if they actually changed
    rules_data = []
    for i, r in enumerate(body.rules):
        rule_dict = r.dict()
        if not rule_dict.get("id"):
            rule_dict["id"] = f"{section_key}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{i}"
        
        old = old_rules_map.get(rule_dict.get("id"))
        if old is None:
            # New rule → unprocessed
            rule_dict["processed"] = False
        elif (old.get("text") != rule_dict.get("text")
              or old.get("priority") != rule_dict.get("priority")
              or old.get("active") != rule_dict.get("active")):
            # Changed rule → unprocessed
            rule_dict["processed"] = False
        else:
            # Unchanged → keep previous state
            rule_dict["processed"] = old.get("processed", True)
        
        rules_data.append(rule_dict)
    
    username = user.username if hasattr(user, 'username') else str(user)
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {"$set": {
            "rules": rules_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": username,
        }},
    )
    
    print(f"[GoldenRules] Section '{section_key}' updated by {username}: {len(rules_data)} rules")
    
    return {"ok": True, "section": section_key, "rules_count": len(rules_data)}


@router.post("/{section_key}/add")
async def add_rule_to_section(
    section_key: str,
    rule: RuleItem,
    user=Depends(get_current_user),
):
    """Add a single rule to a section."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    rule_dict = rule.dict()
    if not rule_dict.get("id"):
        rule_dict["id"] = f"{section_key}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    rule_dict["processed"] = False
    
    username = user.username if hasattr(user, 'username') else str(user)
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {
            "$push": {"rules": rule_dict},
            "$set": {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": username,
            },
        },
    )
    
    return {"ok": True, "rule_id": rule_dict["id"]}


@router.post("/{section_key}/process")
async def process_section(
    section_key: str,
    user=Depends(get_current_user),
):
    """Mark all active rules in a section as processed."""
    mongo = get_mongo_db()
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    username = user.username if hasattr(user, 'username') else str(user)
    now = datetime.now(timezone.utc).isoformat()
    
    # Process manual rules in golden_rules
    rules = existing.get("rules", [])
    count = 0
    for r in rules:
        if r.get("active", True):
            r["processed"] = True
            r["processed_at"] = now
            r["processed_by"] = username
            count += 1
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {"$set": {
            "rules": rules,
            "updated_at": now,
            "updated_by": username,
        }},
    )
    
    # If processing "learned", also mark dictionary entries as processed
    dict_count = 0
    if section_key == "learned":
        try:
            result = await mongo.section_mapping_dictionary.update_many(
                {},
                {"$set": {
                    "processed": True,
                    "processed_at": now,
                    "processed_by": username,
                }},
            )
            dict_count = result.modified_count
            log.info("[GoldenRules] Marked %d dictionary rules as processed", dict_count)
        except Exception as e:
            log.warning("[GoldenRules] Error processing dictionary rules: %s", e)
    
    log.info("[GoldenRules] Section '%s' processed by %s: %d rules + %d dict", section_key, username, count, dict_count)
    return {"ok": True, "section": section_key, "processed_count": count + dict_count}
