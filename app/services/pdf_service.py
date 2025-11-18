# backend/app/services/pdf_service.py
# -*- coding: utf-8 -*-
"""
Servicios PDF:
- Render de EPC a PDF con Jinja2 + WeasyPrint
- Extracción de texto omitiendo páginas escaneadas (pdfminer.six)

Requisitos del sistema (WeasyPrint):
  - Cairo, Pango, Harfbuzz instalados (ej. Debian/Ubuntu):
    sudo apt install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libffi-dev fonts-dejavu-core
"""

from __future__ import annotations

import asyncio
import io
import os
from typing import Any, Dict, List, Optional, Union, IO

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

# --- pdfminer.six para extracción de texto (omitiendo escaneadas) ---
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer


# --------------------------------------------------------------------
# Paths base del backend
# --------------------------------------------------------------------
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_APP_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_TEMPLATES_DIR = os.path.join(_APP_DIR, "templates")
_STATIC_DIR = os.path.join(_APP_DIR, "static")

# Base URL para que WeasyPrint resuelva /static/* o rutas relativas en el HTML
# Usamos la carpeta app/ como base para que "static/..." funcione out-of-the-box
_BASE_URL = _APP_DIR

# --------------------------------------------------------------------
# Entorno Jinja2 (templates/)
# --------------------------------------------------------------------
env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convierte objetos (Pydantic model, ORM, dataclass) en dict.
    - dict -> tal cual
    - pydantic -> .dict() si existe
    - resto -> __dict__ si existe; sino {}.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()  # type: ignore[no-any-return]
        except Exception:
            pass
    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()  # type: ignore[no-any-return]
        except Exception:
            pass
    # Fallback genérico
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _render_html(epc: Dict[str, Any], payload: Dict[str, Any], brand: Dict[str, Any]) -> str:
    """
    Renderiza el template principal de impresión (epc_print.html).
    """
    tpl = env.get_template("epc_print.html")
    return tpl.render(epc=epc, p=payload, brand=brand)


# --------------------------------------------------------------------
# API pública: Render EPC → PDF
# --------------------------------------------------------------------
async def render_epc_pdf(
    epc: Any,
    payload: Any,
    brand: Optional[Any] = None,
    *,
    base_url: Optional[str] = None,
) -> bytes:
    """
    Renderiza un PDF de la EPC a partir del template Jinja2.
    - epc: objeto/record de EPC (ORM/Pydantic/dict)
    - payload: datos complementarios (dict/obj)
    - brand: datos de branding (nombre hospital, logos, etc.)
    - base_url: directorio base para resolver rutas de CSS/IMG en el HTML (opcional)

    Retorna: bytes del PDF.
    """
    epc_dict = _to_dict(epc)
    payload_dict = _to_dict(payload)
    brand_dict = _to_dict(brand)

    html_str = _render_html(epc_dict, payload_dict, brand_dict)

    # WeasyPrint es bloqueante; lo ejecutamos en thread para no bloquear el event loop
    def _build_pdf(_html: str, _base: str) -> bytes:
        return HTML(string=_html, base_url=_base).write_pdf()

    return await asyncio.to_thread(_build_pdf, html_str, base_url or _BASE_URL)


# --------------------------------------------------------------------
# (Opcional) Render solo HTML – útil para depurar el template.
# --------------------------------------------------------------------
def render_epc_html(
    epc: Any, payload: Any, brand: Optional[Any] = None
) -> str:
    epc_dict = _to_dict(epc)
    payload_dict = _to_dict(payload)
    brand_dict = _to_dict(brand)
    return _render_html(epc_dict, payload_dict, brand_dict)


# ====================================================================
# UTILIDAD: extracción de texto omitiendo páginas escaneadas
# ====================================================================
def _is_real_text_page(layout, min_chars: int = 20, min_alpha_ratio: float = 0.25) -> bool:
    """
    True si la página parece tener texto 'real' (no escaneada).
    Heurística:
      - Mínimo de caracteres extraídos.
      - Proporción de alfanuméricos respecto del total (evita 'basura' sin ToUnicode).
    """
    total_chars = 0
    alnum_chars = 0

    for element in layout:
        if isinstance(element, LTTextContainer):
            txt = element.get_text()
            total_chars += len(txt)
            alnum_chars += sum(ch.isalnum() for ch in txt)

    if total_chars < min_chars:
        return False
    if (alnum_chars / max(total_chars, 1)) < min_alpha_ratio:
        return False
    return True


def extract_text_skip_scanned(
    pdf_input: Union[str, bytes, IO[bytes]],
    *,
    laparams: Optional[LAParams] = None,
    min_chars: int = 20,
    min_alpha_ratio: float = 0.25,
) -> Dict[str, object]:
    """
    Extrae texto solo de páginas con texto vectorial. Omite escaneadas.

    Parámetros:
      - pdf_input: ruta al PDF, bytes, o file-like (binario).
      - laparams: parámetros de layout de pdfminer.six
      - min_chars: mínimo de caracteres por página para considerarla 'texto real'.
      - min_alpha_ratio: proporción mínima de [a-zA-Z0-9] sobre el total extraído.

    Retorno:
      {
        "text": str,               # texto concatenado
        "kept_pages": List[int],   # páginas incluidas (1-based)
        "skipped_pages": List[int] # páginas omitidas (escaneadas o inválidas)
      }
    """
    if laparams is None:
        laparams = LAParams(line_margin=0.35, char_margin=2.0, word_margin=0.1)

    # Normalizamos input a algo que extract_pages pueda consumir
    source: Union[str, IO[bytes]]
    close_after = False

    if isinstance(pdf_input, (bytes, bytearray)):
        bio = io.BytesIO(pdf_input)
        bio.seek(0)
        source = bio
        close_after = True
    elif hasattr(pdf_input, "read"):  # file-like
        source = pdf_input  # type: ignore[assignment]
        try:
            pdf_input.seek(0)  # type: ignore[attr-defined]
        except Exception:
            pass
    elif isinstance(pdf_input, str):
        source = pdf_input
    else:
        raise TypeError("pdf_input debe ser ruta (str), bytes o file-like binario.")

    kept_pages: List[int] = []
    skipped_pages: List[int] = []
    collected: List[str] = []

    try:
        for page_no, layout in enumerate(extract_pages(source, laparams=laparams), start=1):
            if _is_real_text_page(layout, min_chars=min_chars, min_alpha_ratio=min_alpha_ratio):
                buf = []
                for element in layout:
                    if isinstance(element, LTTextContainer):
                        buf.append(element.get_text())
                collected.append("".join(buf))
                kept_pages.append(page_no)
            else:
                skipped_pages.append(page_no)
    finally:
        if close_after and isinstance(source, io.BytesIO):
            source.close()

    return {
        "text": "\n".join(collected),
        "kept_pages": kept_pages,
        "skipped_pages": skipped_pages,
    }


__all__ = [
    "render_epc_pdf",
    "render_epc_html",
    "extract_text_skip_scanned",
]