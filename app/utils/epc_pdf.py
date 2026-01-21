# backend/app/utils/epc_pdf.py
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib import colors


def _safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip()


def _fmt_date(v: Any) -> str:
    # Acepta string/fecha; deja lo que venga si no puede parsear
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    s = str(v).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return s


def _dict_to_text(d: Dict[str, Any]) -> str:
    if not d:
        return ""
    if d.get("farmaco"):
        parts = [d.get("farmaco"), d.get("dosis"), d.get("via"), d.get("frecuencia")]
        return " · ".join([_safe(p) for p in parts if p])
    if d.get("especialidad") or d.get("resumen"):
        parts = [d.get("especialidad"), d.get("resumen")]
        return " · ".join([_safe(p) for p in parts if p])
    for k in ("descripcion", "detalle", "resumen", "texto", "texto_completo"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    try:
        import json

        return json.dumps(d, ensure_ascii=False)
    except Exception:
        return str(d)


def _value_to_text(v: Any) -> str:
    """
    Convierte valores de sections a texto:
    - str -> str
    - list -> bullets
    - dict -> dict_to_text
    - otros -> str
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        lines: List[str] = []
        for it in v:
            if it is None:
                continue
            if isinstance(it, str):
                s = it.strip()
                if s:
                    lines.append(f"• {s}")
                continue
            if isinstance(it, dict):
                t = _dict_to_text(it).strip()
                if t:
                    lines.append(f"• {t}")
                continue
            s = str(it).strip()
            if s:
                lines.append(f"• {s}")
        return "\n".join(lines).strip()
    if isinstance(v, dict):
        return _dict_to_text(v).strip()
    return str(v).strip()


def _coalesce_sections(sections: Optional[Dict[str, Any]]) -> List[tuple[str, Any]]:
    """
    Ordena secciones para salida profesional:
    1) Orden preferido.
    2) Luego el resto (en orden original).
    """
    if not isinstance(sections, dict) or not sections:
        return []

    preferred = [
        "Título",
        "Datos clínicos",
        "Motivo de internación",
        "Evolución",
        "Procedimientos",
        "Interconsultas",
        "Tratamiento / Medicación",
        "Indicaciones de alta",
        "Recomendaciones",
    ]

    out: List[tuple[str, Any]] = []
    used = set()

    for k in preferred:
        if k in sections:
            out.append((k, sections.get(k)))
            used.add(k)

    for k, v in sections.items():
        if k in used:
            continue
        # Protección: evitamos imprimir claves típicas “ruido” si vienen de payloads raros
        # (no rompe si no existen).
        if str(k).strip().lower() in {"diagnóstico principal (cie-10)", "diagnostico principal (cie-10)"}:
            continue
        out.append((str(k), v))

    return out


def build_epicrisis_pdf(epc: Dict[str, Any]) -> bytes:
    """
    epc: dict con la epicrisis ya armada para exportación PDF.

    Formato esperado (flexible):
    {
      "id": "...",
      "fecha_emision": datetime | str,
      "clinic": {"name": "...", "address": "..."},
      "patient": {"full_name": "...", "dni": "...", "age": "...", "sex": "..."},
      "doctor": {"full_name": "...", "matricula": "..."},
      "sections": { "Título": "...", "Evolución": "...", "Procedimientos": ["..."] }
    }

    Retorna bytes del PDF.
    """
    buf = BytesIO()

    # Branding (multi-tenant friendly)
    brand_name = _safe(
        epc.get("brand_name")
        or epc.get("system_name")
        or epc.get("app_name")
        or "AINSTEIN"
    )
    site_url = _safe(epc.get("watermark_url") or epc.get("site_url") or "www.demo-aistein.ovh")

    clinic = epc.get("clinic") or {}
    clinic_name = _safe(epc.get("clinic_name") or clinic.get("name") or "Clínica / Consultorio")
    clinic_addr = _safe(epc.get("clinic_address") or clinic.get("address") or "")

    issued_at = _fmt_date(
        epc.get("fecha_emision")
        or epc.get("created_at")
        or epc.get("updated_at")
        or datetime.utcnow()
    )

    # Dejamos márgenes “reales” para header/footer y que nada se pise
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=28 * mm,     # header band + aire
        bottomMargin=22 * mm,  # footer band + aire
        title="Epicrisis",
        author=brand_name,
    )

    styles = getSampleStyleSheet()

    # Base
    base_body = ParagraphStyle(
        "EpcBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        splitLongWords=0,  # evita “Document o”
    )
    base_small = ParagraphStyle(
        "EpcSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11.5,
        textColor=colors.grey,
        splitLongWords=0,
    )

    title = ParagraphStyle(
        "EpcTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,  # centered
        spaceAfter=6,
        splitLongWords=0,
    )

    sub = ParagraphStyle(
        "EpcSub",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=12.5,
        alignment=1,
        textColor=colors.grey,
        splitLongWords=0,
    )

    h = ParagraphStyle(
        "EpcH",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.black,
        splitLongWords=0,
    )

    # Helpers visuales
    def P(txt: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(_safe(txt).replace("\n", "<br/>"), style)

    def _draw_page(canvas, _doc):
        w, hgt = _doc.pagesize

        header_h = 16 * mm
        footer_h = 14 * mm
        pad_x = 18 * mm

        canvas.saveState()

        # Header / Footer bands
        canvas.setFillColor(colors.whitesmoke)
        canvas.rect(0, hgt - header_h, w, header_h, fill=1, stroke=0)
        canvas.rect(0, 0, w, footer_h, fill=1, stroke=0)

        # Watermark diagonal (centro) - sutil
        try:
            canvas.setFillAlpha(0.08)
        except Exception:
            pass
        canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.08))
        canvas.setFont("Helvetica-Bold", 44)
        canvas.translate(w / 2.0, hgt / 2.0)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, site_url)
        canvas.rotate(-45)
        canvas.translate(-w / 2.0, -hgt / 2.0)

        # Header text
        canvas.setFillColor(colors.grey)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(pad_x, hgt - header_h + 5.2 * mm, f"{brand_name} · {clinic_name}")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(w - pad_x, hgt - header_h + 5.2 * mm, f"Emitido: {issued_at}")

        # Footer text
        canvas.setFont("Helvetica", 8)
        canvas.drawString(pad_x, 4.6 * mm, f"{brand_name} · Epicrisis / HCE")
        canvas.drawCentredString(w / 2.0, 4.6 * mm, site_url)
        canvas.drawRightString(w - pad_x, 4.6 * mm, f"Pág. {canvas.getPageNumber()}")

        canvas.restoreState()

    patient = epc.get("patient") or {}
    doctor = epc.get("doctor") or {}

    patient_name = _safe(
        patient.get("full_name")
        or f"{_safe(patient.get('first_name'))} {_safe(patient.get('last_name'))}".strip()
    )
    patient_dni = _safe(patient.get("dni"))
    patient_age = _safe(patient.get("age"))
    patient_sex = _safe(patient.get("sex"))

    doctor_name = _safe(
        doctor.get("full_name")
        or f"{_safe(doctor.get('first_name'))} {_safe(doctor.get('last_name'))}".strip()
    )
    doctor_license = _safe(
        doctor.get("license")
        or doctor.get("matricula")
        or doctor.get("matricula_profesional")
        or ""
    )

    epc_id = _safe(epc.get("id") or epc.get("_id") or epc.get("epc_id") or "")
    sections = epc.get("sections")

    story: List[Any] = []

    # Encabezado del documento (contenido)
    story.append(P("EPICRISIS", title))
    story.append(P(f"{clinic_name}", sub))
    if clinic_addr:
        story.append(P(clinic_addr, base_small))
    meta_line = f"Fecha de emisión: {issued_at}"
    if epc_id:
        meta_line += f" · ID: {epc_id}"
    story.append(P(meta_line, base_small))
    story.append(Spacer(1, 10))

    # ---- Bloque paciente / médico (sin pisarse) ----
    label_style = ParagraphStyle(
        "Lbl",
        parent=base_small,
        fontName="Helvetica-Bold",
        textColor=colors.black,
        splitLongWords=0,
    )
    value_style = ParagraphStyle(
        "Val",
        parent=base_body,
        fontSize=10,
        leading=12.5,
        splitLongWords=0,
    )

    patient_table = Table(
        [
            [P("Paciente", label_style), P(patient_name or "-", value_style)],
            [P("DNI", label_style), P(patient_dni or "-", value_style)],
            [P("Edad", label_style), P(patient_age or "-", value_style)],
            [P("Sexo", label_style), P(patient_sex or "-", value_style)],
        ],
        colWidths=[22 * mm, (doc.width / 2.0) - (22 * mm) - 4],
    )
    patient_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("LINEBEFORE", (0, 0), (0, -1), 0.6, colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
            ]
        )
    )

    doctor_table = Table(
        [
            [P("Médico", label_style), P(doctor_name or "-", value_style)],
            [P("Matrícula", label_style), P(doctor_license or "-", value_style)],
        ],
        colWidths=[22 * mm, (doc.width / 2.0) - (22 * mm) - 4],
    )
    doctor_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("LINEBEFORE", (0, 0), (0, -1), 0.6, colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
            ]
        )
    )

    info_wrap = Table(
        [[patient_table, doctor_table]],
        colWidths=[doc.width / 2.0, doc.width / 2.0],
    )
    info_wrap.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(info_wrap)
    story.append(Spacer(1, 12))

    # ---- Secciones ----
    ordered_sections = _coalesce_sections(sections)

    if ordered_sections:
        for k, v in ordered_sections:
            title_txt = _safe(k) or "Sección"
            val_txt = _value_to_text(v)

            story.append(Paragraph(title_txt, h))
            if val_txt:
                story.append(Paragraph(val_txt.replace("\n", "<br/>"), base_body))
            else:
                story.append(Paragraph("-", base_body))
    else:
        main_text = epc.get("result_text") or epc.get("epicrisis_text") or epc.get("text")
        story.append(Paragraph("Contenido", h))
        if main_text:
            story.append(Paragraph(_safe(main_text).replace("\n", "<br/>"), base_body))
        else:
            story.append(Paragraph("No hay contenido disponible para esta epicrisis.", base_body))

    story.append(Spacer(1, 16))

    # ---- Firma ----
    firma_line = Table(
        [[P(doctor_name or "_________________________", base_small), P("_________________________", base_small)]],
        colWidths=[doc.width / 2.0, doc.width / 2.0],
        style=TableStyle(
            [
                ("LINEABOVE", (0, 0), (0, 0), 0.8, colors.black),
                ("LINEABOVE", (1, 0), (1, 0), 0.8, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )

    firma = KeepTogether(
        [
            Paragraph("Firma y sello", h),
            Spacer(1, 10),
            firma_line,
        ]
    )
    story.append(firma)

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buf.getvalue()