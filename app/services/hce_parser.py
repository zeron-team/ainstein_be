from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Tuple, Union, IO, Dict, Any, List
from datetime import datetime

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

from app.core.config import settings

UPLOAD_ROOT = Path(settings.HCE_UPLOAD_DIR).resolve()
HCE_SUBDIR = settings.HCE_SUBDIR
HCE_DIR = UPLOAD_ROOT / HCE_SUBDIR


# --------------------------- FS Helpers ---------------------------

def ensure_upload_dir() -> Path:
    HCE_DIR.mkdir(parents=True, exist_ok=True)
    return HCE_DIR


def _page_count(pdf_path: Union[str, Path]) -> int:
    pdf_path = Path(pdf_path)
    with pdf_path.open("rb") as fh:
        return sum(1 for _ in PDFPage.get_pages(fh))


def save_upload(filename: str, file_obj: IO[bytes]) -> Path:
    dst_dir = ensure_upload_dir()
    safe_name = os.path.basename(filename)
    dst = dst_dir / safe_name

    i = 1
    while dst.exists():
        stem = Path(safe_name).stem
        suf = Path(safe_name).suffix
        dst = dst_dir / f"{stem}_{i}{suf}"
        i += 1

    with dst.open("wb") as out:
        out.write(file_obj.read())

    return dst


# --------------------------- Text extraction ---------------------------

def extract_text_from_hce(
    pdf_path: Union[str, Path],
    *,
    max_chars: Optional[int] = None,
) -> Tuple[str, int]:
    """
    Devuelve (texto, páginas). Mantengo firma original para no romper tu flujo.
    Usa parse_hce_text(...) para obtener estructura.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no existe: {pdf_path}")

    txt: str = extract_text(str(pdf_path)) or ""
    pages = _page_count(pdf_path)

    if max_chars is not None:
        txt = txt[:max_chars]

    return txt.strip(), pages


# --------------------------- Structured parsing ---------------------------

_DATE_RX = r"(\d{2})/(\d{2})/(\d{4})"  # dd/mm/yyyy


def _to_iso_or_none(m: Optional[re.Match]) -> Optional[str]:
    if not m:
        return None
    d, mth, y = m.group(1), m.group(2), m.group(3)
    try:
        return datetime.strptime(f"{y}-{mth}-{d}", "%Y-%m-%d").date().isoformat()
    except Exception:
        return None


def parse_hce_text(text: str) -> Dict[str, Any]:
    """
    Devuelve un dict con campos claves extraídos de la HCE.
    Tolerante a acentos/espacios. Basado en tus HCE subidas.
    """
    src = text or ""
    norm = " ".join(src.split())  # compactar espacios/linebreaks para facilitar regex

    out: Dict[str, Any] = {
        "paciente_apellido_nombre": None,
        "sexo": None,               # 'F' / 'M' si se detecta
        "edad": None,               # años (int)
        "edad_meses": None,         # meses (int)
        "hclin": None,              # Historia Clínica nro (si hay)
        "admision_num": None,       # "Nro. Admisión"
        "protocolo": None,
        "fecha_ingreso": None,      # YYYY-MM-DD
        "fecha_egreso": None,       # YYYY-MM-DD
        "sector": None,
        "habitacion": None,
        "cama": None,
        "diagnostico_egreso_principal": None,
        "cie10": None,
        "interconsultas": [],       # lista de servicios
        "medicacion": [],           # lista {farmaco, dosis, via, frecuencia}
        "evolucion": None,
    }

    # --- Identificación paciente ---
    m = re.search(r"Apellido y Nombre\s+([A-ZÁÉÍÓÚÑ ,.\-]+)", norm, flags=re.I)
    if m:
        out["paciente_apellido_nombre"] = m.group(1).strip().replace(" ,", ",")

    m = re.search(r"H\.?Clin\.?\s*([0-9A-Za-z\-\./]+)", norm, flags=re.I)
    if m:
        out["hclin"] = m.group(1).strip()

    # sexo (busco expresiones frecuentes en tus docs)
    if re.search(r"\b(Paciente\s+mujer|femenina)\b", norm, re.I):
        out["sexo"] = "F"
    elif re.search(r"\b(Paciente\s+var[oó]n|masculino|masculina)\b", norm, re.I):
        out["sexo"] = "M"

    # edad
    m = re.search(r"Edad\s+(\d{1,3})\s*a[nñ]os(?:\s+(\d{1,2})\s*meses)?", norm, re.I)
    if m:
        try:
            out["edad"] = int(m.group(1))
        except Exception:
            pass
        if m.group(2):
            try:
                out["edad_meses"] = int(m.group(2))
            except Exception:
                pass

    # --- Admisión / protocolo / fechas ---
    m = re.search(r"Nro\.?\s*Admisi[oó]n\s+([0-9\-]+)", norm, re.I)
    if m:
        out["admision_num"] = m.group(1).strip()

    m = re.search(r"Protocolo\s*:\s*([0-9\-]+)", norm, re.I)
    if m:
        out["protocolo"] = m.group(1).strip()

    mi = re.search(r"Fecha de Ingreso\s*:\s*" + _DATE_RX, norm, re.I)
    out["fecha_ingreso"] = _to_iso_or_none(mi)

    me = re.search(r"Fecha de Egreso\s*:\s*" + _DATE_RX, norm, re.I)
    out["fecha_egreso"] = _to_iso_or_none(me)

    # --- Sector / habitación / cama ---
    m = re.search(
        r"Sector\s+([A-ZÁÉÍÓÚÑ \-]+)\s+Habitacion\s*-\s*Cama\s*([0-9A-Za-z]+)\s*-\s*([0-9A-Za-z]+)",
        norm,
        re.I,
    )
    if m:
        out["sector"] = m.group(1).strip()
        out["habitacion"] = m.group(2).strip()
        out["cama"] = m.group(3).strip()

    # --- Diagnóstico / CIE-10 ---
    # texto del diagnóstico principal (si aparece en “Diagnóstico de Egreso”)
    m = re.search(r"Diagn[oó]stico de Egreso\s+Principal\s+([A-ZÁÉÍÓÚÑ 0-9\.,\-]+)", norm, re.I)
    if m:
        out["diagnostico_egreso_principal"] = m.group(1).strip(" .-")

    m = re.search(r"Codificaci[oó]n\s*CIE\s*([A-Z0-9\.]+)", norm, re.I)
    if m:
        out["cie10"] = m.group(1).strip()

    # --- Interconsultas (ej: "Interconsulta con ORTOPEDIA Y TRAUMATOLOGIA - dd/mm/yyyy ...") ---
    inter = re.findall(r"Interconsulta\s+con\s+([A-ZÁÉÍÓÚÑ &/]+?)(?:\s+-|\s+12/|\s+13/|\s+Fecha|\s+EF:)", norm, re.I)
    if inter:
        out["interconsultas"] = [s.strip(" -") for s in inter]

    # --- Medicación (ej: "KETOROLAC 30 MGR AMPOLLA, 30, MG ... VIA Endovenoso ... Unica Vez") ---
    meds: List[Dict[str, Any]] = []
    for mm in re.finditer(
        r"([A-ZÁÉÍÓÚÑ0-9 /\-]+?)\s+(\d+\s*(?:MG|MGR|ML|G|UI|mcg))[^,]*?,?\s*(?:VIA|v[ií]a)\s*([A-Za-zÁÉÍÓÚÑ ]+)"
        r"(?:.*?\bfrecuencia[: ]\s*([A-Za-zÁÉÍÓÚÑ ]+))?",
        norm,
        re.I,
    ):
        farmaco = mm.group(1).strip(" ,")
        dosis = mm.group(2).strip(" ,") if mm.group(2) else ""
        via = mm.group(3).strip(" ,") if mm.group(3) else ""
        frecuencia = (mm.group(4) or "").strip(" ,")
        meds.append({"farmaco": farmaco, "dosis": dosis, "via": via, "frecuencia": frecuencia})
    if meds:
        out["medicacion"] = meds

    # --- Evolución (última línea típica) ---
    m = re.search(r"Evoluci[oó]n:\s*([A-ZÁÉÍÓÚÑ a-z0-9,\. ]+)", norm, re.I)
    if m:
        out["evolucion"] = m.group(1).strip(" .")

    return out