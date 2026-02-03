# app/rules/death_detection.py
"""
Regla de detección de fallecimiento/óbito.

Esta regla implementa la detección obligatoria de fallecimiento según
docs/REGLAS_GENERACION_EPC.md - Sección EVOLUCIÓN.

Principio SOLID aplicado: Single Responsibility
- Este módulo SOLO detecta fallecimiento
- NO modifica texto, solo detecta y extrae información
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class DeathInfo:
    """Información extraída sobre el fallecimiento."""
    detected: bool
    date: Optional[str] = None
    time: Optional[str] = None
    source_text: Optional[str] = None
    detection_method: Optional[str] = None


class DeathDetectionRule:
    """
    Regla de detección de fallecimiento según REGLAS_GENERACION_EPC.md.
    
    Uso:
        rule = DeathDetectionRule()
        info = rule.detect(texto_evolucion)
        if info.detected:
            print(f"Óbito detectado: {info.date} {info.time}")
    """
    
    # Palabras clave que indican fallecimiento (orden de prioridad)
    DEATH_KEYWORDS: List[str] = [
        # Términos directos
        "fallece", "falleció", "fallecio", "falleciendo",
        "óbito", "obito", "obitó",
        "murió", "murio", "deceso",
        "defunción", "defuncion", "fallecimiento",
        "muerte", "muerto", "finado", "fallecido",
        # Términos médicos
        "paro cardiorrespiratorio", "pcr",
        "exitus", "éxitus",
        # Acciones que indican muerte
        "se constata", "constata",  # "se constata óbito"
        "maniobras de reanimación",
        "sin respuesta a maniobras",
        "retiro de soporte vital",
        "limitación del esfuerzo terapéutico",
        "cuidados de fin de vida",
        "se certifica defunción",
        "se suspende soporte vital",
        "paciente finado",
    ]
    
    # Patrones regex para extraer fecha y hora
    DATE_PATTERNS = [
        r'(\d{1,2}/\d{1,2}/\d{4})',  # DD/MM/YYYY
        r'(\d{4}-\d{2}-\d{2})',       # YYYY-MM-DD
        r'(\d{1,2}/\d{1,2})',         # DD/MM (sin año)
    ]
    
    TIME_PATTERNS = [
        r'(\d{1,2}:\d{2})\s*(?:hs|hrs|horas)?',  # HH:MM
        r'a las\s*(\d{1,2}:\d{2})',               # a las HH:MM
        r'siendo las\s*(\d{1,2}:\d{2})',          # siendo las HH:MM
    ]
    
    def detect(self, text: str) -> DeathInfo:
        """
        Detecta si hay fallecimiento en el texto.
        
        Args:
            text: Texto de evolución o HCE completa
            
        Returns:
            DeathInfo con toda la información extraída
        """
        if not text:
            return DeathInfo(detected=False)
        
        text_lower = text.lower()
        
        # Buscar palabras clave
        detected_keyword = None
        for keyword in self.DEATH_KEYWORDS:
            if keyword in text_lower:
                detected_keyword = keyword
                break
        
        if not detected_keyword:
            return DeathInfo(detected=False)
        
        # Extraer fecha y hora
        date, time = self._extract_datetime(text, text_lower, detected_keyword)
        
        # Encontrar el fragmento de texto que contiene la detección
        source_text = self._extract_context(text, detected_keyword)
        
        log.info(f"[DeathRule] Detectado '{detected_keyword}' - Fecha: {date}, Hora: {time}")
        
        return DeathInfo(
            detected=True,
            date=date,
            time=time,
            source_text=source_text,
            detection_method=f"keyword:{detected_keyword}",
        )
    
    def _extract_datetime(
        self, 
        text: str, 
        text_lower: str, 
        keyword: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extrae fecha y hora del texto cercano al keyword."""
        
        # Buscar en contexto cercano al keyword (100 chars antes/después)
        idx = text_lower.find(keyword)
        if idx == -1:
            return None, None
        
        # Contexto extendido
        start = max(0, idx - 150)
        end = min(len(text), idx + len(keyword) + 150)
        context = text[start:end]
        
        # Buscar fecha
        date = None
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, context)
            if match:
                date = match.group(1)
                break
        
        # Buscar hora
        time = None
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                time = match.group(1)
                break
        
        return date, time
    
    def _extract_context(self, text: str, keyword: str) -> Optional[str]:
        """Extrae la oración que contiene el keyword."""
        text_lower = text.lower()
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        
        # Buscar inicio de oración (. o inicio)
        start = text.rfind('.', 0, idx)
        start = start + 1 if start != -1 else 0
        
        # Buscar fin de oración
        end = text.find('.', idx)
        end = end + 1 if end != -1 else len(text)
        
        return text[start:end].strip()


def detect_death_in_text(text: str) -> DeathInfo:
    """
    Función de conveniencia para detectar fallecimiento.
    
    Uso:
        info = detect_death_in_text("Se constata óbito a las 15:50")
        if info.detected:
            print(info.time)  # "15:50"
    """
    rule = DeathDetectionRule()
    return rule.detect(text)


def detect_death_from_alta_type(tipo_alta: str) -> bool:
    """
    Detecta fallecimiento desde el tipo de alta del episodio.
    
    Args:
        tipo_alta: Campo taltDescripcion del episodio
        
    Returns:
        True si el tipo de alta indica fallecimiento
    """
    if not tipo_alta:
        return False
    
    tipo_upper = tipo_alta.upper()
    return any(kw in tipo_upper for kw in ["OBITO", "ÓBITO", "FALLEC", "DEFUNC"])


def format_death_line(
    date: Optional[str] = None,
    time: Optional[str] = None,
    description: str = "",
) -> str:
    """
    Formatea la línea de óbito según REGLAS_GENERACION_EPC.md.
    
    Returns:
        Línea formateada: "PACIENTE OBITÓ - Fecha: X Hora: Y. descripción"
    """
    date_str = date or "fecha no registrada"
    time_str = time or "hora no registrada"
    desc = description.strip()
    
    if desc and not desc.endswith('.'):
        desc += '.'
    
    return f"PACIENTE OBITÓ - Fecha: {date_str} Hora: {time_str}. {desc}"
