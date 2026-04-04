# -*- coding: utf-8 -*-
"""
REGLAS DE CLASIFICACIÓN DE ESTUDIOS MÉDICOS

Este módulo contiene las reglas de clasificación de estudios según
las categorías definidas por el usuario. Se utiliza para:
1. Identificar y categorizar estudios en la HCE
2. Estandarizar nombres/abreviaturas
3. Facilitar el filtrado y agrupación en la EPC

Categorías principales:
- 🩻 Diagnóstico por Imágenes (9 subcategorías)
- ❤️ Cardiología
- 🧠 Neurología
- 🫁 Neumonología
- 🔍 Endoscopía
- 👁️ Oftalmología
- 🦴 Traumatología
- 👂 ORL
- 👩‍⚕️ Ginecología
- 👨‍⚕️ Urología
- 🧬 Genética
"""

from typing import Dict, List, Tuple, Optional
import re

# =============================================================================
# DICCIONARIO DE ESTUDIOS POR CATEGORÍA
# Formato: "ABREVIATURA": "NOMBRE COMPLETO"
# =============================================================================

ESTUDIOS_POR_CATEGORIA: Dict[str, Dict[str, str]] = {
    # =========================================================================
    # 🩻 1. DIAGNÓSTICO POR IMÁGENES
    # =========================================================================
    
    # 1.1 Radiología Convencional
    "radiologia_convencional": {
        "RX": "Radiografía simple",
        "RXC": "Radiografía con contraste",
        "SEGD": "Serie esófago-gastro-duodenal",
        "TI": "Tránsito intestinal",
        "CE": "Colon por enema",
        "HSG": "Histerosalpingografía",
        "CUM": "Cistouretrografía miccional",
        "RADIOGRAFIA": "Radiografía simple",
    },
    
    # 1.2 Tomografía Computada
    "tomografia": {
        "TC": "Tomografía computada",
        "TAC": "Tomografía axial computada",
        "TC C/C": "TC con contraste",
        "TC SC": "TC sin contraste",
        "ANGIO-TC": "Angiotomografía",
        "ANGIOTC": "Angiotomografía",
        "ANGIO-TAC": "Angiotomografía",
        "ANGIOTAC": "Angiotomografía",
        "ANGIOTOMOGRAFIA": "Angiotomografía",
        "ANGIOTOMOGRAFÍA": "Angiotomografía",
        "ANGIO TOMOGRAFIA": "Angiotomografía",
        "ANGIO TOMOGRAFÍA": "Angiotomografía",
        "TCAR": "TC de alta resolución",
        "TC CARD": "TC cardíaca",
        "TC COR": "TC coronaria",
        "TOMOGRAFIA": "Tomografía computada",
    },
    
    # 1.3 Resonancia Magnética
    "resonancia": {
        "RM": "Resonancia magnética",
        "RMN": "Resonancia magnética nuclear",
        "RM C/C": "RM con contraste",
        "ANGIO-RM": "Angiorresonancia",
        "ANGIORM": "Angiorresonancia",
        "RMF": "Resonancia funcional",
        "COLANGIO-RM": "Colangioresonancia",
        "COLANGIORM": "Colangioresonancia",
        "RM CARD": "Resonancia cardíaca",
        "RESONANCIA": "Resonancia magnética",
    },
    
    # 1.4 Ecografía
    "ecografia": {
        "ECO ABD": "Ecografía abdominal",
        "ECO PELV": "Ecografía pélvica",
        "ECO TV": "Ecografía transvaginal",
        "ECO OB": "Ecografía obstétrica",
        "ECO REN": "Ecografía renal",
        "ECO TIRO": "Ecografía tiroidea",
        "ECO MAM": "Ecografía mamaria",
        "ECOGRAFIA": "Ecografía",
        "ECO": "Ecografía",
    },
    
    # 1.5 Doppler
    "doppler": {
        "ECODOP ART": "Doppler arterial",
        "ECODOP VEN": "Doppler venoso",
        "ECODOP CAR": "Doppler carotídeo",
        "ECODOP MMII": "Doppler miembros inferiores",
        "ECODOP REN": "Doppler renal",
        "DOPPLER": "Doppler",
        "ECODOPPLER": "Ecodoppler",
    },
    
    # 1.6 Cardiología por Imágenes
    "cardiologia_imagenes": {
        "ECO TT": "Ecocardiograma transtorácico",
        "ECO TE": "Ecocardiograma transesofágico",
        "ECO STR": "Ecoestrés",
        "ECO STR F": "Ecoestrés farmacológico",
        "ECOCARDIOGRAMA": "Ecocardiograma",
        "ECOTT": "Ecocardiograma transtorácico",
        "ECOTE": "Ecocardiograma transesofágico",
    },
    
    # 1.7 Medicina Nuclear
    "medicina_nuclear": {
        "CX OSEO": "Centellograma óseo",
        "GAMM PERF": "Gammagrafía de perfusión miocárdica",
        "RENOG": "Renograma isotópico",
        "PET-CT FDG": "PET-TC oncológico",
        "PET-CT": "PET-TC oncológico",
        "PETCT": "PET-TC oncológico",
        "PET-TC": "PET-TC oncológico",
        "PET/TC": "PET-TC oncológico",
        "SPECT CEREB": "SPECT cerebral",
        "SPECT": "SPECT",
        "HIDA": "Centellograma hepatobiliar",
        "CENTELLOGRAMA": "Centellograma",
        "GAMMAGRAFIA": "Gammagrafía",
    },
    
    # 1.8 Otros de Imágenes
    "otros_imagenes": {
        "MMG": "Mamografía",
        "DBT": "Tomosíntesis mamaria",
        "DEXA": "Densitometría ósea",
        "CBCT": "Tomografía haz cónico",
        "MAMOGRAFIA": "Mamografía",
        "DENSITOMETRIA": "Densitometría ósea",
        "ANGIOGRAFIA": "Angiografía",
        "ANGIOGRAFÍA": "Angiografía",
    },
    
    # =========================================================================
    # ❤️ 2. CARDIOLOGÍA
    # =========================================================================
    
    # 2.1 No Invasivos
    "cardiologia_no_invasivo": {
        "ECG": "Electrocardiograma",
        "HOLTER": "Holter de ritmo",
        "MAPA": "Monitoreo ambulatorio de presión",
        "PEG": "Prueba ergométrica graduada",
        "TILT TEST": "Test de mesa basculante",
        "ELECTROCARDIOGRAMA": "Electrocardiograma",
        "ERGOMETRIA": "Prueba ergométrica",
    },
    
    # 2.2 Hemodinámicos e Intervencionismo
    "cardiologia_invasivo": {
        "CCG": "Cinecoronariografía",
        "ATC": "Angioplastia transluminal coronaria",
        "ATC C/ST": "ATC con stent",
        "CAT DER": "Cateterismo derecho",
        "CAT IZQ": "Cateterismo izquierdo",
        "EP STUDY": "Estudio electrofisiológico",
        "ABL": "Ablación por catéter",
        "TAVI": "Implante valvular aórtico transcatéter",
        "MITRACLIP": "Reparación percutánea mitral",
        "CATETERISMO": "Cateterismo cardíaco",
        "ANGIOPLASTIA": "Angioplastia",
        "CINECORONARIOGRAFIA": "Cinecoronariografía",
    },
    
    # =========================================================================
    # 🧠 3. NEUROLOGÍA
    # =========================================================================
    "neurologia": {
        "EEG": "Electroencefalograma",
        "VIDEO-EEG": "EEG prolongado con video",
        "EMG": "Electromiografía",
        "VCN": "Velocidad de conducción nerviosa",
        "PEV": "Potenciales evocados visuales",
        "PESS": "Potenciales evocados somatosensitivos",
        "ELECTROENCEFALOGRAMA": "Electroencefalograma",
        "ELECTROMIOGRAFIA": "Electromiografía",
    },
    
    # =========================================================================
    # 🫁 4. NEUMONOLOGÍA
    # =========================================================================
    "neumonologia": {
        "ESPIRO": "Espirometría",
        "DLCO": "Difusión pulmonar",
        "PLETIS": "Pletismografía pulmonar",
        "GSA": "Gasometría arterial",
        "POLISOM": "Polisomnografía",
        "ESPIROMETRIA": "Espirometría",
        "GASOMETRIA": "Gasometría arterial",
    },
    
    # =========================================================================
    # 🔍 5. ENDOSCOPÍA
    # =========================================================================
    "endoscopia": {
        "VEDA": "Videoendoscopía digestiva alta",
        "VCC": "Videocolonoscopía",
        "BRONCO": "Broncoscopía",
        "CISTO": "Cistoscopía",
        "HISTERO": "Histeroscopía",
        "ARTRO": "Artroscopía",
        "LAP DX": "Laparoscopía diagnóstica",
        "ENDOSCOPIA": "Endoscopía",
        "COLONOSCOPIA": "Colonoscopía",
        "VIDEOCOLONOSCOPIA": "Videocolonoscopía",
        "VIDEOENDOSCOPIA": "Videoendoscopía digestiva alta",
        "BRONCOSCOPIA": "Broncoscopía",
        "CISTOSCOPIA": "Cistoscopía",
        "HISTEROSCOPIA": "Histeroscopía",
        "ARTROSCOPIA": "Artroscopía",
        "LAPAROSCOPIA": "Laparoscopía",
        "CPRE": "Colangiopancreatografía Retrógrada Endoscópica",
        "COLANGIOPANCREATOGRAFIA": "Colangiopancreatografía Retrógrada Endoscópica",
        "FIBROBRONCOSCOPIA": "Fibrobroncoscopía",
    },
    
    # =========================================================================
    # 👁️ 6. OFTALMOLOGÍA
    # =========================================================================
    "oftalmologia": {
        "OCT": "Tomografía de coherencia óptica",
        "CV COMP": "Campo visual computarizado",
        "PIO": "Tonometría",
        "PAQ": "Paquimetría",
        "TOP COR": "Topografía corneal",
        "ERG": "Electrorretinograma",
        "CAMPIMETRIA": "Campo visual",
        "FONDO DE OJO": "Fondo de ojo",
    },
    
    # =========================================================================
    # 🦴 7. TRAUMATOLOGÍA / OSTEOARTICULAR
    # =========================================================================
    "traumatologia": {
        "ARTROCENT": "Artrocentesis",
        "ECO ARTIC": "Ecografía articular",
        "RM ARTIC": "Resonancia articular",
        "ARTROCENTESIS": "Artrocentesis",
    },
    
    # =========================================================================
    # 👂 8. OTORRINOLARINGOLOGÍA
    # =========================================================================
    "orl": {
        "AUDIO": "Audiometría",
        "LOGO": "Logoaudiometría",
        "IMPED": "Impedanciometría",
        "BERA": "Potenciales evocados auditivos",
        "VNG": "Videonistagmografía",
        "AUDIOMETRIA": "Audiometría",
        "LOGOAUDIOMETRIA": "Logoaudiometría",
        "IMPEDANCIOMETRIA": "Impedanciometría",
    },
    
    # =========================================================================
    # 👩‍⚕️ 9. GINECOLOGÍA
    # =========================================================================
    "ginecologia": {
        "COLPO": "Colposcopía",
        "ECO TV": "Ecografía transvaginal",
        "HISTERO": "Histeroscopía",
        "COLPOSCOPIA": "Colposcopía",
        "PAP": "Papanicolaou",
    },
    
    # =========================================================================
    # 👨‍⚕️ 10. UROLOGÍA
    # =========================================================================
    "urologia": {
        "UROFLUJO": "Uroflujometría",
        "CISTO": "Cistoscopía",
        "ECO PROST": "Ecografía prostática",
        "CISTOSCOPIA": "Cistoscopía",
        "UROFLUJOMETRIA": "Uroflujometría",
    },
    
    # =========================================================================
    # 🧬 11. GENÉTICA / ESTUDIOS MOLECULARES
    # =========================================================================
    "genetica": {
        "CARIOTIPO": "Estudio cromosómico",
        "FISH": "Hibridación fluorescente",
        "NGS": "Secuenciación genética",
    },
}


# =============================================================================
# MAPEO DE CATEGORÍAS A GRUPOS PRINCIPALES
# =============================================================================
CATEGORIA_A_GRUPO = {
    "radiologia_convencional": "Diagnóstico por Imágenes",
    "tomografia": "Diagnóstico por Imágenes",
    "resonancia": "Diagnóstico por Imágenes",
    "ecografia": "Diagnóstico por Imágenes",
    "doppler": "Diagnóstico por Imágenes",
    "cardiologia_imagenes": "Diagnóstico por Imágenes",
    "medicina_nuclear": "Diagnóstico por Imágenes",
    "otros_imagenes": "Diagnóstico por Imágenes",
    "cardiologia_no_invasivo": "Cardiología",
    "cardiologia_invasivo": "Cardiología",
    "neurologia": "Neurología",
    "neumonologia": "Neumonología",
    "endoscopia": "Endoscopía",
    "oftalmologia": "Oftalmología",
    "traumatologia": "Traumatología",
    "orl": "ORL",
    "ginecologia": "Ginecología",
    "urologia": "Urología",
    "genetica": "Genética",
}


# =============================================================================
# ÍNDICE INVERSO: TÉRMINO -> (CATEGORÍA, ABREVIATURA, NOMBRE COMPLETO)
# =============================================================================
_INDICE_ESTUDIOS: Dict[str, Tuple[str, str, str]] = {}

def _build_index():
    """Construye el índice inverso de estudios para búsqueda rápida."""
    global _INDICE_ESTUDIOS
    if _INDICE_ESTUDIOS:
        return
    
    for categoria, estudios in ESTUDIOS_POR_CATEGORIA.items():
        for abrev, nombre in estudios.items():
            # Agregar por abreviatura
            _INDICE_ESTUDIOS[abrev.upper()] = (categoria, abrev, nombre)
            # Agregar por nombre completo
            _INDICE_ESTUDIOS[nombre.upper()] = (categoria, abrev, nombre)

_build_index()


# =============================================================================
# FUNCIONES DE BÚSQUEDA Y CLASIFICACIÓN
# =============================================================================

def clasificar_estudio(texto: str) -> Optional[Dict[str, str]]:
    """
    Clasifica un texto de estudio según las reglas definidas.
    
    Args:
        texto: Texto del estudio a clasificar (ej: "RX Torax", "ECG")
    
    Returns:
        Dict con:
            - categoria: categoría del estudio
            - grupo: grupo principal
            - abreviatura: abreviatura estándar
            - nombre: nombre completo
            - texto_original: texto original
        O None si no se puede clasificar
    """
    if not texto:
        return None
    
    texto_upper = texto.upper().strip()
    
    # 1. Búsqueda exacta
    if texto_upper in _INDICE_ESTUDIOS:
        categoria, abrev, nombre = _INDICE_ESTUDIOS[texto_upper]
        return {
            "categoria": categoria,
            "grupo": CATEGORIA_A_GRUPO.get(categoria, "Otros"),
            "abreviatura": abrev,
            "nombre": nombre,
            "texto_original": texto,
        }
    
    # 2. Búsqueda por prefijo (ej: "RX TORAX" -> "RX")
    for abrev in _INDICE_ESTUDIOS:
        if texto_upper.startswith(abrev + " ") or texto_upper.startswith(abrev + "-"):
            categoria, ab, nombre = _INDICE_ESTUDIOS[abrev]
            # Agregar detalle del estudio
            detalle = texto[len(abrev):].strip(" -")
            nombre_completo = f"{nombre} de {detalle}" if detalle else nombre
            return {
                "categoria": categoria,
                "grupo": CATEGORIA_A_GRUPO.get(categoria, "Otros"),
                "abreviatura": abrev,
                "nombre": nombre_completo,
                "texto_original": texto,
            }
    
    # 3. Búsqueda por palabras clave
    # ⚠️ REGLA IMPORTANTE: Para abreviaturas cortas (≤3 caracteres),
    # SOLO matchear si es una palabra completa (no substring de otra palabra).
    # Esto evita falsos positivos como "ReCEpción" → "Colon por enema"
    for abrev, (categoria, ab, nombre) in _INDICE_ESTUDIOS.items():
        if len(abrev) <= 3:
            # Para abreviaturas cortas: buscar como palabra completa
            # Usar regex con word boundaries
            pattern = r'\b' + re.escape(abrev) + r'\b'
            if re.search(pattern, texto_upper):
                return {
                    "categoria": categoria,
                    "grupo": CATEGORIA_A_GRUPO.get(categoria, "Otros"),
                    "abreviatura": ab,
                    "nombre": nombre,
                    "texto_original": texto,
                }
        else:
            # Para abreviaturas largas (>3 chars): buscar como substring está OK
            if abrev in texto_upper:
                return {
                    "categoria": categoria,
                    "grupo": CATEGORIA_A_GRUPO.get(categoria, "Otros"),
                    "abreviatura": ab,
                    "nombre": nombre,
                    "texto_original": texto,
                }
    
    return None


def es_estudio(texto: str) -> bool:
    """
    Determina si un texto corresponde a un estudio médico.
    
    Args:
        texto: Texto a evaluar
    
    Returns:
        True si es un estudio reconocido
    """
    return clasificar_estudio(texto) is not None


def normalizar_nombre_estudio(texto: str) -> str:
    """
    Normaliza el nombre de un estudio a su forma estándar.
    
    Args:
        texto: Texto del estudio
    
    Returns:
        Nombre normalizado o el texto original si no se reconoce
    """
    clasificacion = clasificar_estudio(texto)
    if clasificacion:
        return clasificacion["nombre"]
    return texto


def obtener_estudios_por_grupo(grupo: str) -> List[Dict[str, str]]:
    """
    Obtiene todos los estudios de un grupo principal.
    
    Args:
        grupo: Nombre del grupo (ej: "Diagnóstico por Imágenes")
    
    Returns:
        Lista de estudios con sus abreviaturas y nombres
    """
    resultado = []
    for categoria, grupo_cat in CATEGORIA_A_GRUPO.items():
        if grupo_cat == grupo and categoria in ESTUDIOS_POR_CATEGORIA:
            for abrev, nombre in ESTUDIOS_POR_CATEGORIA[categoria].items():
                resultado.append({
                    "categoria": categoria,
                    "abreviatura": abrev,
                    "nombre": nombre,
                })
    return resultado


def listar_grupos() -> List[str]:
    """Lista todos los grupos principales de estudios."""
    return list(set(CATEGORIA_A_GRUPO.values()))


def listar_categorias() -> List[str]:
    """Lista todas las categorías de estudios."""
    return list(ESTUDIOS_POR_CATEGORIA.keys())
