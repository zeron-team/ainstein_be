# app/rules/medication_classifier.py
"""
Clasificador de medicación (internación vs previa).

Implementa las reglas de REGLAS_GENERACION_EPC.md - Sección MEDICACIÓN.

Principio SOLID aplicado: Single Responsibility
- Este módulo SOLO clasifica medicación
"""

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

log = logging.getLogger(__name__)


@dataclass
class MedicationInfo:
    """Información de un medicamento clasificado."""
    farmaco: str
    dosis: str
    via: str
    frecuencia: str
    tipo: str  # "internacion" | "previa"
    confidence: float  # 0.0 a 1.0
    reason: Optional[str] = None


class MedicationClassifier:
    """
    Clasifica medicamentos entre internación y previos/habituales.
    
    Uso:
        classifier = MedicationClassifier()
        tipo = classifier.classify("Losartan", "50 mg", "Oral", "c/24hs")
        # Retorna: "previa" (es antihipertensivo oral)
    """
    
    # Medicamentos típicamente PREVIOS (crónicos, orales)
    TYPICAL_PREVIOUS: Dict[str, List[str]] = {
        "antihipertensivos": [
            "losartan", "valsartan", "enalapril", "lisinopril",
            "amlodipino", "amlodipina", "bisoprolol", "atenolol",
            "carvedilol", "metoprolol", "ramipril", "telmisartan",
        ],
        "estatinas": [
            "atorvastatina", "simvastatina", "rosuvastatina", 
            "pravastatina", "lovastatina",
        ],
        "diabetes": [
            "metformina", "glibenclamida", "glimepirida", "sitagliptina",
            "empagliflozina", "dapagliflozina", "linagliptina",
        ],
        "tiroides": [
            "levotiroxina", "t4",
        ],
        "ibp": [
            "omeprazol", "pantoprazol", "esomeprazol", "lansoprazol",
        ],
        "anticoagulantes_orales": [
            "warfarina", "acenocumarol", "apixaban", "rivaroxaban",
            "dabigatran", "edoxaban",
        ],
        "antidepresivos": [
            "sertralina", "escitalopram", "fluoxetina", "paroxetina",
            "duloxetina", "venlafaxina", "amitriptilina",
        ],
        "ansioticos": [
            "alprazolam", "clonazepam", "lorazepam", "diazepam",
        ],
        "otros_cronicos": [
            "alopurinol", "colchicina", "levodopa", "pramipexol",
            "quetiapina", "risperidona", "olanzapina",
        ],
    }
    
    # Medicamentos típicamente de INTERNACIÓN (agudos, IV)
    TYPICAL_INTERNATION: Dict[str, List[str]] = {
        "antibioticos_iv": [
            "ampicilina", "sulbactam", "ampicilina/sulbactam",
            "piperacilina", "tazobactam", "piperacilina/tazobactam",
            "vancomicina", "meropenem", "imipenem", "ceftriaxona",
            "ceftazidima", "cefepime", "ciprofloxacina",
            "metronidazol", "clindamicina", "gentamicina", "amikacina",
        ],
        "analgesicos_iv": [
            "morfina", "fentanilo", "tramadol", "dipirona",
            "ketorolac", "dexketoprofeno",
        ],
        "vasopresores": [
            "noradrenalina", "norepinefrina", "dopamina", "dobutamina",
            "adrenalina", "epinefrina", "vasopresina",
        ],
        "sedantes_iv": [
            "midazolam", "propofol", "dexmedetomidina", "haloperidol",
        ],
        "otros_agudos": [
            "furosemida", "hidrocortisona", "dexametasona", "metilprednisolona",
            "amiodarona", "heparina", "enoxaparina", "insulina",
            "omeprazol iv", "pantoprazol iv", "ranitidina",
        ],
    }
    
    # Vías típicas de internación
    IV_ROUTES: Set[str] = {
        "iv", "intravenoso", "intravenosa", "ev", "endovenoso",
        "im", "intramuscular", "sc", "subcutaneo", "subcutánea",
        "sng", "nasogástrica", "enteral",
    }
    
    def __init__(self):
        # Crear sets para búsqueda rápida
        self._previous_meds: Set[str] = set()
        for meds in self.TYPICAL_PREVIOUS.values():
            self._previous_meds.update(meds)
        
        self._internation_meds: Set[str] = set()
        for meds in self.TYPICAL_INTERNATION.values():
            self._internation_meds.update(meds)
    
    def classify(
        self,
        farmaco: str,
        dosis: str = "",
        via: str = "",
        frecuencia: str = "",
    ) -> str:
        """
        Clasifica un medicamento.
        
        Args:
            farmaco: Nombre del medicamento
            dosis: Dosis
            via: Vía de administración
            frecuencia: Frecuencia
            
        Returns:
            "internacion" o "previa"
        """
        farmaco_lower = farmaco.lower().strip()
        via_lower = via.lower().strip()
        
        # 1. Verificar si la vía indica internación
        if any(route in via_lower for route in self.IV_ROUTES):
            # Es IV pero ¿es un medicamento típicamente previo?
            if not self._is_previous_med(farmaco_lower):
                return "internacion"
        
        # 2. Verificar lista de medicamentos previos
        if self._is_previous_med(farmaco_lower):
            # Es oral y es típicamente previo
            if not any(route in via_lower for route in {"iv", "intravenoso", "ev"}):
                return "previa"
        
        # 3. Verificar lista de medicamentos de internación
        if self._is_internation_med(farmaco_lower):
            return "internacion"
        
        # 4. Por defecto según vía
        if any(route in via_lower for route in self.IV_ROUTES):
            return "internacion"
        
        # 5. Default: internación (más seguro)
        return "internacion"
    
    def _is_previous_med(self, farmaco: str) -> bool:
        """Verifica si el fármaco está en lista de previos."""
        return any(
            med in farmaco or farmaco in med 
            for med in self._previous_meds
        )
    
    def _is_internation_med(self, farmaco: str) -> bool:
        """Verifica si el fármaco está en lista de internación."""
        return any(
            med in farmaco or farmaco in med 
            for med in self._internation_meds
        )
    
    def classify_with_details(
        self,
        farmaco: str,
        dosis: str = "",
        via: str = "",
        frecuencia: str = "",
    ) -> MedicationInfo:
        """
        Clasifica con información detallada.
        
        Returns:
            MedicationInfo con tipo, confianza y razón
        """
        tipo = self.classify(farmaco, dosis, via, frecuencia)
        
        farmaco_lower = farmaco.lower()
        via_lower = via.lower()
        
        # Determinar confianza y razón
        if self._is_previous_med(farmaco_lower):
            confidence = 0.9
            reason = "Medicamento típicamente crónico/habitual"
        elif self._is_internation_med(farmaco_lower):
            confidence = 0.9
            reason = "Medicamento típicamente de internación"
        elif any(r in via_lower for r in self.IV_ROUTES):
            confidence = 0.7
            reason = "Vía de administración indica internación"
        else:
            confidence = 0.5
            reason = "Clasificación por defecto"
        
        return MedicationInfo(
            farmaco=farmaco,
            dosis=dosis,
            via=via,
            frecuencia=frecuencia,
            tipo=tipo,
            confidence=confidence,
            reason=reason,
        )


# Instancia global para uso conveniente
_classifier = MedicationClassifier()


def classify_medication(
    farmaco: str,
    via: str = "",
    dosis: str = "",
    frecuencia: str = "",
) -> str:
    """
    Función de conveniencia para clasificar medicación.
    
    Returns:
        "internacion" o "previa"
    """
    return _classifier.classify(farmaco, dosis, via, frecuencia)
