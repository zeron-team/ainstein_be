#!/usr/bin/env python3
"""
Seed CONSOLIDATED Golden Rules from REGLAS_EPC.md into MongoDB.

This script takes the 342+ learned rules from evaluator feedback,
consolidates them into ~5-8 concise, non-redundant rules per section,
and upserts them into the `golden_rules` MongoDB collection.

It PRESERVES any existing manually-entered rules and APPENDS the
consolidated learned rules.

Usage:
    cd ainstein_be
    python scripts/seed_learned_golden_rules.py
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.mongo_client import get_mongo_db


# ═══════════════════════════════════════════════════════════════════════
# CONSOLIDATED LEARNED RULES — Deduplicated from 342+ individual rules
# Each section has 5-8 concise "master rules" that cover all the patterns
# ═══════════════════════════════════════════════════════════════════════

LEARNED_RULES = {
    "estudios": {
        "title": "Estudios",
        "rules": [
            {
                "text": "Verificar que TODOS los estudios mencionados en la evolución (TC, RMN, RX, Eco, Doppler, EEG, ECG, PET, AngioTC, AngioTAC, Ecocardiograma) estén listados en la sección Estudios con su fecha de realización.",
                "priority": "critica",
            },
            {
                "text": "Incluir estudios microbiológicos (hemocultivos, urocultivos, BAL, cultivos de secreciones) con el microorganismo aislado y la sensibilidad a antibióticos si está disponible.",
                "priority": "alta",
            },
            {
                "text": "Diferenciar estudios con y sin contraste. Especificar el tipo exacto de estudio (ej: Ecocardiograma transesofágico vs transtorácico, Doppler carotídeo vs Doppler venoso de MMII).",
                "priority": "alta",
            },
            {
                "text": "Incluir una breve descripción del hallazgo más relevante de cada estudio de imagen (ej: 'TAC de tórax: fracturas costales múltiples').",
                "priority": "alta",
            },
            {
                "text": "Eliminar duplicados. Si un estudio se repitió, listar cada instancia con su fecha y comparar resultados si hubo cambios significativos.",
                "priority": "alta",
            },
            {
                "text": "Incluir estudios de anatomía patológica y citología con sus resultados relevantes.",
                "priority": "normal",
            },
            {
                "text": "Si un estudio no pudo realizarse, mencionarlo con el motivo (ej: 'EEG no realizado por vendaje y catéter PICC').",
                "priority": "normal",
            },
            {
                "text": "Eliminar la hora de realización de los estudios. NO incluir laboratorios de sangre individuales en esta sección. Usar capitalización consistente.",
                "priority": "alta",
            },
        ],
    },
    "evolucion": {
        "title": "Evolución",
        "rules": [
            {
                "text": "Organizar la evolución por sistemas/especialidades (neurológico, respiratorio, infectológico, cardiovascular) en orden cronológico estricto, indicando fechas clave.",
                "priority": "critica",
            },
            {
                "text": "Incluir antecedentes patológicos relevantes y medicación habitual al ingreso (nombre genérico, dosis, frecuencia) al inicio de la sección.",
                "priority": "alta",
            },
            {
                "text": "En infecciones: especificar microorganismo aislado, sensibilidad antibiótica, antibióticos usados (dosis, vía, duración en días), si cultivos fueron intra o pre-antibióticos, y respuesta al tratamiento.",
                "priority": "alta",
            },
            {
                "text": "En complicaciones: detallar fecha de inicio, presentación clínica, estudios diagnósticos realizados, tratamiento instaurado y evolución.",
                "priority": "alta",
            },
            {
                "text": "Mencionar estadía en UTI/UCO con duración, necesidad de ARM (duración) y soporte inotrópico (fármacos y duración). Mencionar interconsultas realizadas y recomendaciones de especialistas.",
                "priority": "alta",
            },
            {
                "text": "En óbito: indicar fecha, hora, causa de muerte siguiendo normativa legal argentina (causa directa, interviniente y básica). En PCR: detallar maniobras de RCP y medicación administrada.",
                "priority": "critica",
            },
            {
                "text": "Al alta: incluir estado del paciente, examen físico relevante, destino (domicilio, centro de rehabilitación, derivación), plan de seguimiento ambulatorio y estudios pendientes.",
                "priority": "alta",
            },
            {
                "text": "NO inventar datos. Verificar consistencia con otras secciones. Usar lenguaje médico técnico, tiempo pasado, sin abreviaturas ambiguas. No incluir información subjetiva no confirmada.",
                "priority": "critica",
            },
        ],
    },
    "indicaciones_alta": {
        "title": "Indicaciones al Alta",
        "rules": [
            {
                "text": "Lista completa de medicación al alta: nombre genérico, dosis, frecuencia, vía de administración y duración del tratamiento. Diferenciar medicación preexistente de la nueva.",
                "priority": "critica",
            },
            {
                "text": "Si el paciente egresa con antibióticos ambulatorios, especificar nombre, dosis, vía, frecuencia y duración total del tratamiento.",
                "priority": "alta",
            },
            {
                "text": "Incluir citas de seguimiento: especialidad, nombre del médico (si disponible), fecha y hora. Especificar estudios complementarios pendientes con tiempo máximo recomendado.",
                "priority": "alta",
            },
            {
                "text": "Incluir cuidados especiales post-alta: manejo de heridas, sistemas de vacío, restricciones de actividad física, higiene personal, recomendaciones dietéticas e hidratación.",
                "priority": "alta",
            },
            {
                "text": "Incluir analgésicos de rescate si corresponde: nombre, dosis, frecuencia máxima y cuándo consultar al médico.",
                "priority": "normal",
            },
            {
                "text": "En óbito: registrar fecha y hora exacta del fallecimiento. En cuidados paliativos: explicitar régimen de cuidados domiciliarios y seguimiento.",
                "priority": "critica",
            },
            {
                "text": "NO incluir información de contacto personal (WhatsApp). NO incluir indicaciones ya detalladas en otras secciones de forma redundante.",
                "priority": "alta",
            },
        ],
    },
    "interconsultas": {
        "title": "Interconsultas",
        "rules": [
            {
                "text": "Incluir TODAS las interconsultas formales realizadas durante la hospitalización. Verificar contra el registro clínico completo (órdenes médicas, notas de evolución, informes de consultores).",
                "priority": "critica",
            },
            {
                "text": "Para cada interconsulta: especialidad, fecha, motivo de solicitud y breve resumen de hallazgos/recomendaciones principales del especialista (máx 2 frases).",
                "priority": "alta",
            },
            {
                "text": "Priorizar especialidades frecuentemente omitidas: Neurocirugía, Infectología, Nutrición, Cuidados Paliativos, Psiquiatría, Fonoaudiología, Hematología.",
                "priority": "alta",
            },
            {
                "text": "NO incluir como interconsulta el manejo rutinario del médico tratante (ej: 'Clínica Médica' si el paciente está a cargo). NO incluir indicaciones terapéuticas generales ni horarios.",
                "priority": "alta",
            },
            {
                "text": "Diferenciar entre interconsulta formal y seguimiento rutinario. Excluir seguimientos preexistentes salvo que impacten en la internación actual.",
                "priority": "normal",
            },
            {
                "text": "Si la interconsulta resultó en un procedimiento (ej: VEDA por Gastroenterología), mencionar el estudio y su resultado relevante.",
                "priority": "normal",
            },
            {
                "text": "Validar que la especialidad corresponda a quien realizó la evaluación, no a quien la solicitó. Evitar duplicación con información ya detallada en Evolución.",
                "priority": "alta",
            },
        ],
    },
    "medicacion": {
        "title": "Medicación",
        "rules": [
            {
                "text": "Separar claramente: medicación habitual/crónica del paciente (previa al ingreso) vs medicación indicada durante la internación vs medicación al alta.",
                "priority": "critica",
            },
            {
                "text": "Para cada fármaco: nombre genérico, dosis, vía de administración, frecuencia y duración (o fecha inicio-fin). Unificar nombre genérico y comercial en una sola entrada.",
                "priority": "alta",
            },
            {
                "text": "Priorizar: antibióticos (con indicación y duración), anticoagulantes, anticonvulsivantes, inmunosupresores e inotrópicos. Agrupar por categoría farmacológica.",
                "priority": "alta",
            },
            {
                "text": "Excluir medicación puntual/esporádica (dosis única de analgésico, Ringer Lactato aislado, antieméticos PRN) salvo que sea relevante para la evolución.",
                "priority": "alta",
            },
            {
                "text": "Si se suspende o modifica medicación crónica, indicar el motivo. En sedación paliativa: detallar fármacos, dosis y vía.",
                "priority": "normal",
            },
            {
                "text": "NO incluir procedimientos quirúrgicos en esta sección (ej: frenulotomía). NO incluir indicaciones no farmacológicas.",
                "priority": "critica",
            },
            {
                "text": "Si no hay indicaciones de medicación al alta, explicitarlo: 'No se indican modificaciones en la medicación habitual al alta'.",
                "priority": "alta",
            },
        ],
    },
    "motivo_internacion": {
        "title": "Motivo de Internación",
        "rules": [
            {
                "text": "Extraer el motivo DIRECTAMENTE de la primera nota de admisión o consulta inicial. Priorizar síntomas y signos al ingreso, NO diagnósticos confirmados posteriormente.",
                "priority": "critica",
            },
            {
                "text": "Usar terminología médica precisa y específica (ej: 'Pérdida de conciencia' en vez de 'Síncope en estudio'). Evitar términos vagos como 'malestar general'.",
                "priority": "alta",
            },
            {
                "text": "En politraumatismos: incluir causa Y manifestaciones principales (ej: 'Accidente automovilístico con pérdida de conciencia y fractura de fémur').",
                "priority": "alta",
            },
            {
                "text": "En cirugías programadas: indicar procedimiento y condición subyacente (ej: 'Cirugía programada de reemplazo de cadera por artrosis').",
                "priority": "normal",
            },
            {
                "text": "En derivaciones: indicar razón de derivación tal como se expresa en la orden original.",
                "priority": "normal",
            },
            {
                "text": "NO incluir antecedentes del paciente (salvo directamente relevantes). NO incluir estudios en curso ni planes de tratamiento como motivo. Usar minúsculas excepto inicio de frase.",
                "priority": "alta",
            },
        ],
    },
    "procedimientos": {
        "title": "Procedimientos",
        "rules": [
            {
                "text": "Incluir TODOS los procedimientos invasivos y quirúrgicos realizados durante la internación: cirugías, toilettes, punciones, drenajes, colocación/retiro de catéteres, intubaciones, traqueostomías, transfusiones, diálisis.",
                "priority": "critica",
            },
            {
                "text": "Agrupar por nombre de procedimiento y mostrar fecha(s) entre paréntesis. Si se repitió, indicar la cantidad de sesiones.",
                "priority": "alta",
            },
            {
                "text": "Excluir procedimientos administrativos genéricos: ingreso, enfermería, controles, higiene, cambio de ropa de cama.",
                "priority": "alta",
            },
            {
                "text": "Imágenes diagnósticas (RX, TAC, RMN, Eco) van en la sección Estudios, NO en Procedimientos.",
                "priority": "alta",
            },
            {
                "text": "Para procedimientos quirúrgicos: incluir fecha, tipo de procedimiento, hallazgos intraoperatorios relevantes y complicaciones si las hubo.",
                "priority": "normal",
            },
            {
                "text": "NO inventar procedimientos. Si no hay procedimientos documentados, dejar la sección vacía.",
                "priority": "critica",
            },
        ],
    },
}


async def seed():
    db = get_mongo_db()

    for section_key, data in LEARNED_RULES.items():
        title = data["title"]
        new_rules = data["rules"]

        # Check if section exists
        existing = await db.golden_rules.find_one({"_id": section_key})

        if existing:
            # --- MERGE: Keep existing manual rules, add learned ones ---
            existing_rules = existing.get("rules", [])
            # Find existing rule texts (lowercase) to avoid duplicates
            existing_texts = {r.get("text", "").strip().lower() for r in existing_rules}

            added = 0
            for rule in new_rules:
                if rule["text"].strip().lower() not in existing_texts:
                    existing_rules.append({
                        "text": rule["text"],
                        "priority": rule["priority"],
                        "active": True,
                        "processed": True,
                        "source": "learned_from_feedback",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    added += 1

            await db.golden_rules.update_one(
                {"_id": section_key},
                {"$set": {"rules": existing_rules, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            print(f"  ✅ {title}: Merged {added} new learned rules (kept {len(existing_rules) - added} existing)")
        else:
            # --- CREATE: New section ---
            doc = {
                "_id": section_key,
                "title": title,
                "rules": [
                    {
                        "text": r["text"],
                        "priority": r["priority"],
                        "active": True,
                        "processed": True,
                        "source": "learned_from_feedback",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    for r in new_rules
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.golden_rules.insert_one(doc)
            print(f"  🆕 {title}: Created with {len(new_rules)} learned rules")

    print("\n🏆 Done! All consolidated learned rules are now in MongoDB Golden Rules.")
    print("   They will be injected into EVERY EPC generation prompt from now on.")


if __name__ == "__main__":
    print("=" * 70)
    print("  SEED: Consolidated Learned Rules → MongoDB Golden Rules")
    print("  Source: REGLAS_EPC.md (342+ rules → ~50 consolidated)")
    print("=" * 70)
    asyncio.run(seed())
