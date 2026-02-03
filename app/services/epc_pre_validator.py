# app/services/epc_pre_validator.py
"""
Validador PRE-generación de EPC.

Este servicio valida y enriquece los datos de la HCE ANTES de enviarlos a la IA.
Detecta inconsistencias críticas y las corrige para evitar alucinaciones.

Principio: "La IA solo debería generar texto, no inferir hechos."
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.services.hce_ainstein_parser import ParsedHCE
from app.rules.death_detection import detect_death_in_text

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de validación pre-generación."""
    is_valid: bool
    warnings: List[str]
    errors: List[str]
    corrections: Dict[str, Any]
    # Flags importantes
    is_obito: bool = False
    tipo_alta_oficial: Optional[str] = None


class EPCPreValidator:
    """
    Validador pre-generación de EPC.
    
    Detecta y corrige problemas ANTES de que la IA los propague.
    """
    
    # Tipos de alta que indican fallecimiento
    TIPOS_ALTA_OBITO = [
        "OBITO", "ÓBITO", "FALLECIDO", "FALLECIMIENTO",
        "DEFUNCION", "DEFUNCIÓN", "MUERTE"
    ]
    
    def validate(self, parsed_hce: ParsedHCE) -> ValidationResult:
        """
        Valida la HCE parseada y detecta inconsistencias.
        
        Args:
            parsed_hce: HCE parseada
            
        Returns:
            ValidationResult con warnings, errors y correcciones
        """
        warnings: List[str] = []
        errors: List[str] = []
        corrections: Dict[str, Any] = {}
        
        # 1. Detectar ÓBITO desde tipo_alta del episodio (FUENTE DE VERDAD)
        tipo_alta = (parsed_hce.tipo_alta or "").upper().strip()
        is_obito = any(t in tipo_alta for t in self.TIPOS_ALTA_OBITO)
        
        if is_obito:
            log.info(f"[PreValidator] ÓBITO detectado desde tipo_alta: {tipo_alta}")
            corrections["force_obito"] = True
            corrections["tipo_alta"] = tipo_alta
        
        # 2. Detectar óbito en texto de evoluciones (backup)
        if not is_obito:
            for evol in parsed_hce.sections.evoluciones_medicas:
                contenido = evol.get("contenido", "")
                death_result = detect_death_in_text(contenido)
                if death_result.detected:
                    is_obito = True
                    warnings.append(
                        f"Óbito detectado en evolución ({death_result.detection_method}) "
                        f"pero tipo_alta es '{tipo_alta}'"
                    )
                    corrections["obito_detected_in_text"] = True
                    break
        
        # 3. Validar consistencia de datos
        if parsed_hce.dias_estada == 0 and parsed_hce.fecha_egreso:
            warnings.append("Días de estadía es 0 pero hay fecha de egreso")
        
        if not parsed_hce.sections.ingreso:
            warnings.append("No hay texto de ingreso registrado")
        
        if len(parsed_hce.sections.evoluciones_medicas) == 0:
            warnings.append("No hay evoluciones médicas registradas")
        
        # 4. Detectar contradicciones en texto fuente
        if is_obito:
            frases_alta_contradictorias = [
                "alta a domicilio", "se retira deambulando",
                "paciente dado de alta", "evolución favorable",
                "mejoría sintomática. alta"
            ]
            
            for evol in parsed_hce.sections.evoluciones_medicas:
                contenido = (evol.get("contenido", "") or "").lower()
                for frase in frases_alta_contradictorias:
                    if frase in contenido:
                        warnings.append(
                            f"Contradicción: HCE menciona '{frase}' pero tipo_alta es OBITO"
                        )
                        corrections["has_contradictions"] = True
                        break
        
        # 5. Validar datos demográficos
        if parsed_hce.edad <= 0 or parsed_hce.edad > 120:
            warnings.append(f"Edad inválida: {parsed_hce.edad}")
        
        if parsed_hce.sexo not in ["M", "F", "MASCULINO", "FEMENINO"]:
            warnings.append(f"Sexo no reconocido: {parsed_hce.sexo}")
        
        # 6. Detectar sexo incorrecto en texto
        sexo_normalizado = "masculino" if parsed_hce.sexo in ["M", "MASCULINO"] else "femenino"
        sexo_opuesto = "femenino" if sexo_normalizado == "masculino" else "masculino"
        
        for evol in parsed_hce.sections.evoluciones_medicas:
            contenido = (evol.get("contenido", "") or "").lower()
            if f"paciente {sexo_opuesto}" in contenido:
                warnings.append(
                    f"Contradicción de sexo: Episodio dice {sexo_normalizado} pero "
                    f"evolución menciona 'paciente {sexo_opuesto}'"
                )
                corrections["sexo_incorrecto_en_texto"] = True
        
        # Determinar si es válido
        is_valid = len(errors) == 0
        
        result = ValidationResult(
            is_valid=is_valid,
            warnings=warnings,
            errors=errors,
            corrections=corrections,
            is_obito=is_obito,
            tipo_alta_oficial=tipo_alta or None
        )
        
        log.info(
            f"[PreValidator] Validación completa: "
            f"valid={is_valid}, obito={is_obito}, "
            f"warnings={len(warnings)}, errors={len(errors)}"
        )
        
        return result
    
    def get_context_overrides(self, validation: ValidationResult) -> Dict[str, Any]:
        """
        Genera overrides de contexto para forzar en los prompts.
        
        Args:
            validation: Resultado de validación
            
        Returns:
            Dict con valores que DEBEN usarse en lugar de los inferidos
        """
        overrides = {}
        
        if validation.is_obito:
            overrides["PACIENTE_FALLECIDO"] = True
            overrides["TIPO_ALTA_OFICIAL"] = validation.tipo_alta_oficial
            overrides["NO_INDICACIONES_ALTA"] = True
            overrides["NO_RECOMENDACIONES"] = True
            overrides["INSTRUCCION_OBITO"] = (
                "⚠️ IMPORTANTE: El paciente FALLECIÓ (tipo_alta = OBITO). "
                "El último párrafo DEBE comenzar con 'PACIENTE OBITÓ - Fecha: ... Hora: ...'. "
                "NO mencionar alta a domicilio, mejoría, ni recomendaciones post-alta."
            )
        
        if validation.corrections.get("sexo_incorrecto_en_texto"):
            overrides["IGNORAR_SEXO_EN_TEXTO"] = True
        
        return overrides


def validate_hce_for_epc(parsed_hce: ParsedHCE) -> ValidationResult:
    """Función de conveniencia para validar HCE."""
    validator = EPCPreValidator()
    return validator.validate(parsed_hce)
