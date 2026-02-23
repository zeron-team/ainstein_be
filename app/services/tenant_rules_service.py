# app/services/tenant_rules_service.py
"""
Servicio para gestionar reglas de visualización por tenant.

Cada tenant puede configurar qué secciones de HCE mostrar u ocultar.
Las reglas se almacenan como JSON en el campo display_rules de la tabla tenants.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


# =============================================================================
# SECCIONES DISPONIBLES PARA CONFIGURAR
# Basado en análisis 100% completo de 120 HCE:
# - 98.445 registros analizados
# - 61.873 procedimientos 
# - 39.144 plantillas
# =============================================================================

AVAILABLE_SECTIONS = {
    # =========================================================================
    # TIPOS DE REGISTRO (entrTipoRegistro)
    # Ordenados por frecuencia de aparición en datos reales
    # =========================================================================
    "indicacion": {
        "id": "indicacion",
        "name": "Indicaciones",
        "description": "Indicaciones médicas (62.013 registros)",
        "type": "registro",
        "count": 62013,
        "default_hidden": False,  # Importante para médicos
    },
    "hoja_enfermeria": {
        "id": "hoja_enfermeria",
        "name": "Hoja de Enfermería",
        "description": "Hojas de enfermería detalladas (16.128 registros)",
        "type": "registro",
        "count": 16128,
        "default_hidden": True,
    },
    "balance_hidroelectrolitico": {
        "id": "balance_hidroelectrolitico",
        "name": "Balance Hidroelectrolítico",
        "description": "Balance de fluidos (13.662 registros)",
        "type": "registro",
        "count": 13662,
        "default_hidden": True,
    },
    "evolucion_medica": {
        "id": "evolucion_medica",
        "name": "Evolución Médica",
        "description": "Evolución médica a cargo (2.103 registros)",
        "type": "registro",
        "count": 2103,
        "default_hidden": False,  # Importante para médicos
    },
    "control_enfermeria": {
        "id": "control_enfermeria",
        "name": "Control de Enfermería",
        "description": "Controles de enfermería (1.360 registros)",
        "type": "registro",
        "count": 1360,
        "default_hidden": True,
    },
    "evolucion_interconsulta": {
        "id": "evolucion_interconsulta",
        "name": "Evolución Interconsulta",
        "description": "Evoluciones de interconsultas (1.358 registros)",
        "type": "registro",
        "count": 1358,
        "default_hidden": False,
    },
    "evolucion_kinesiologia": {
        "id": "evolucion_kinesiologia",
        "name": "Evolución Kinesiología",
        "description": "Evoluciones de kinesiología UCI/Internación (746 registros)",
        "type": "registro",
        "count": 746,
        "default_hidden": False,
    },
    "evolucion_hemoterapia": {
        "id": "evolucion_hemoterapia",
        "name": "Evolución Hemoterapia",
        "description": "Evoluciones de hemoterapia (170 registros)",
        "type": "registro",
        "count": 170,
        "default_hidden": False,
    },
    "resumen_internacion": {
        "id": "resumen_internacion",
        "name": "Resumen Internación",
        "description": "Resúmenes de internación (128 registros)",
        "type": "registro",
        "count": 128,
        "default_hidden": False,
    },
    "epicrisis": {
        "id": "epicrisis",
        "name": "Epicrisis HIS",
        "description": "Notas de epicrisis del sistema origen (125 registros)",
        "type": "registro",
        "count": 125,
        "default_hidden": True,  # Evitar confusión con epicrisis generada
    },
    "ingreso_paciente": {
        "id": "ingreso_paciente",
        "name": "Ingreso de Paciente",
        "description": "Registros de ingreso (106 registros)",
        "type": "registro",
        "count": 106,
        "default_hidden": False,
    },
    "parte_quirurgico": {
        "id": "parte_quirurgico",
        "name": "Parte Quirúrgico",
        "description": "Partes quirúrgicos (83 registros)",
        "type": "registro",
        "count": 83,
        "default_hidden": False,
    },
    "checklist_quirofano": {
        "id": "checklist_quirofano",
        "name": "Checklist Quirófano",
        "description": "Checklists entrada/pausa/salida (195 registros)",
        "type": "registro",
        "count": 195,
        "default_hidden": True,
    },
    "monitoreo_quirurgico": {
        "id": "monitoreo_quirurgico",
        "name": "Monitoreo Quirúrgico",
        "description": "Monitoreo durante cirugía (62 registros)",
        "type": "registro",
        "count": 62,
        "default_hidden": False,
    },
    "evolucion_emergencia": {
        "id": "evolucion_emergencia",
        "name": "Evolución Emergencia",
        "description": "Evoluciones de emergencia (40 registros)",
        "type": "registro",
        "count": 40,
        "default_hidden": False,
    },
    "evolucion_fonoaudiologia": {
        "id": "evolucion_fonoaudiologia",
        "name": "Evolución Fonoaudiología",
        "description": "Evoluciones de fonoaudiología (37 registros)",
        "type": "registro",
        "count": 37,
        "default_hidden": False,
    },
    "protocolo_dialisis": {
        "id": "protocolo_dialisis",
        "name": "Protocolo de Diálisis",
        "description": "Sesiones de diálisis (9 registros)",
        "type": "registro",
        "count": 9,
        "default_hidden": False,
    },
    
    # =========================================================================
    # CATEGORÍAS DE PROCEDIMIENTOS
    # Ordenados por frecuencia de aparición en datos reales
    # =========================================================================
    "control": {
        "id": "control",
        "name": "Controles Rutinarios",
        "description": "Signos vitales, glucemia, peso pañales (16.449 procedimientos)",
        "type": "procedimiento",
        "count": 16449,
        "default_hidden": True,
    },
    "enfermeria": {
        "id": "enfermeria",
        "name": "Procedimientos Enfermería",
        "description": "Cambios posición, rotación decúbito (14.164 procedimientos)",
        "type": "procedimiento",
        "count": 14164,
        "default_hidden": True,
    },
    "otro": {
        "id": "otro",
        "name": "Otros",
        "description": "Tendido cama, cambio habitación, CA 19-9 (11.444 procedimientos)",
        "type": "procedimiento",
        "count": 11444,
        "default_hidden": True,
    },
    "laboratorio": {
        "id": "laboratorio",
        "name": "Laboratorio",
        "description": "Hemograma, PCR, urocultivo (4.647 procedimientos)",
        "type": "procedimiento",
        "count": 4647,
        "default_hidden": False,
    },
    "higiene": {
        "id": "higiene",
        "name": "Higiene y Confort",
        "description": "Baño ducha, cambio pañal, faja (4.355 procedimientos)",
        "type": "procedimiento",
        "count": 4355,
        "default_hidden": True,
    },
    "valoracion": {
        "id": "valoracion",
        "name": "Valoraciones",
        "description": "Tolerancia oral, respuesta verbal, fluido (3.671 procedimientos)",
        "type": "procedimiento",
        "count": 3671,
        "default_hidden": True,
    },
    "medicacion_admin": {
        "id": "medicacion_admin",
        "name": "Admin. Medicación",
        "description": "Administración VO, SNG, tópica (3.250 procedimientos)",
        "type": "procedimiento",
        "count": 3250,
        "default_hidden": True,
    },
    "imagen": {
        "id": "imagen",
        "name": "Imágenes",
        "description": "RX, TAC, estudios por imágenes (965 procedimientos)",
        "type": "procedimiento",
        "count": 965,
        "default_hidden": False,
    },
    "tratamiento": {
        "id": "tratamiento",
        "name": "Tratamientos",
        "description": "Curaciones, transfusiones (855 procedimientos)",
        "type": "procedimiento",
        "count": 855,
        "default_hidden": False,
    },
    "valoracion_clinica": {
        "id": "valoracion_clinica",
        "name": "Escalas Clínicas",
        "description": "Morse, RASS, Glasgow (836 procedimientos)",
        "type": "procedimiento",
        "count": 836,
        "default_hidden": True,
    },
    "interconsulta": {
        "id": "interconsulta",
        "name": "Interconsultas",
        "description": "Cardiología, psiquiatría, especialidades (624 procedimientos)",
        "type": "procedimiento",
        "count": 624,
        "default_hidden": False,
    },
    "quirurgico": {
        "id": "quirurgico",
        "name": "Procedimientos Quirúrgicos",
        "description": "Drenajes, paracentesis, catéteres (394 procedimientos)",
        "type": "procedimiento",
        "count": 394,
        "default_hidden": False,
    },
    "estudio": {
        "id": "estudio",
        "name": "Estudios Diagnósticos",
        "description": "Biopsias, holter, punciones (219 procedimientos)",
        "type": "procedimiento",
        "count": 219,
        "default_hidden": False,
    },
}

# Secciones excluidas por defecto (rutinas de enfermería y controles)
# Basado en análisis: ocultar lo que genera "ruido" para la epicrisis
DEFAULT_EXCLUDED_SECTIONS = [
    # Tipos de registro (rutinas)
    "hoja_enfermeria",
    "balance_hidroelectrolitico",
    "control_enfermeria",
    "epicrisis",  # Evitar confusión con epicrisis generada
    "checklist_quirofano",
    # Procedimientos (rutinas de enfermería)
    "control",
    "enfermeria",
    "otro",
    "higiene",
    "valoracion",
    "valoracion_clinica",
    "medicacion_admin",
]


class TenantRulesService:
    """
    Servicio para gestionar reglas de visualización por tenant.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_tenant_rules(self, tenant_id: str) -> Dict[str, Any]:
        """
        Obtiene las reglas de visualización de un tenant.
        
        Returns:
            Dict con estructura:
            {
                "excluded_sections": ["enfermeria", "epicrisis"],
                "custom_settings": {...}
            }
        """
        from app.domain.models import Tenant
        
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            log.warning(f"[TenantRules] Tenant not found: {tenant_id}")
            return {"excluded_sections": DEFAULT_EXCLUDED_SECTIONS.copy()}
        
        # Parsear JSON de reglas
        rules = {}
        if tenant.display_rules:
            try:
                rules = json.loads(tenant.display_rules)
            except json.JSONDecodeError:
                log.warning(f"[TenantRules] Invalid JSON in display_rules for tenant {tenant_id}")
                rules = {}
        
        # Si no hay reglas definidas, usar defaults
        if "excluded_sections" not in rules:
            rules["excluded_sections"] = DEFAULT_EXCLUDED_SECTIONS.copy()
        
        return rules
    
    def get_excluded_sections(self, tenant_id: Optional[str]) -> List[str]:
        """
        Obtiene lista de secciones excluidas para un tenant.
        
        Args:
            tenant_id: ID del tenant. Si es None, retorna defaults.
            
        Returns:
            Lista de IDs de secciones a excluir.
        """
        if not tenant_id:
            return DEFAULT_EXCLUDED_SECTIONS.copy()
        
        rules = self.get_tenant_rules(tenant_id)
        return rules.get("excluded_sections", DEFAULT_EXCLUDED_SECTIONS.copy())
    
    def update_tenant_rules(
        self, 
        tenant_id: str, 
        excluded_sections: List[str],
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Actualiza las reglas de visualización de un tenant.
        
        Args:
            tenant_id: ID del tenant
            excluded_sections: Lista de IDs de secciones a excluir
            custom_settings: Configuraciones adicionales (opcional)
            
        Returns:
            Reglas actualizadas
        """
        from app.domain.models import Tenant
        
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")
        
        # Validar secciones
        valid_sections = set(AVAILABLE_SECTIONS.keys())
        for section in excluded_sections:
            if section not in valid_sections and section != "valoracion_clinica":
                log.warning(f"[TenantRules] Unknown section: {section}")
        
        # Construir reglas
        rules = {
            "excluded_sections": excluded_sections,
        }
        if custom_settings:
            rules["custom_settings"] = custom_settings
        
        # Guardar en BD
        tenant.display_rules = json.dumps(rules, ensure_ascii=False)
        self.db.commit()
        
        log.info(f"[TenantRules] Updated rules for tenant {tenant_id}: {excluded_sections}")
        
        return rules
    
    @staticmethod
    def get_available_sections() -> List[Dict[str, Any]]:
        """
        Retorna lista de secciones disponibles para configurar.
        """
        return list(AVAILABLE_SECTIONS.values())


# =============================================================================
# FUNCIONES HELPER PARA USO DIRECTO
# =============================================================================

def get_excluded_sections_for_tenant(
    db: Session, 
    tenant_id: Optional[str]
) -> List[str]:
    """
    Helper function para obtener secciones excluidas.
    
    Args:
        db: Sesión de SQLAlchemy
        tenant_id: ID del tenant
        
    Returns:
        Lista de secciones a excluir
    """
    service = TenantRulesService(db)
    return service.get_excluded_sections(tenant_id)


def get_tenant_rules_service(db: Session) -> TenantRulesService:
    """Factory function para obtener instancia del servicio."""
    return TenantRulesService(db)
