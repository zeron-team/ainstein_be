# app/routers/snomed.py
"""SNOMED CT Argentina – endpoints de consulta."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.deps import get_db, get_current_user

router = APIRouter(prefix="/snomed", tags=["SNOMED CT"])


@router.get("/interconsultas")
def list_interconsultas(
    q: str = "",
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lista interconsultas (consultas con especialistas)."""
    base = text("""
        SELECT snomed_id, interconsulta
        FROM v_snomed_interconsultas
        WHERE (:q = '' OR interconsulta ILIKE :pat)
        ORDER BY interconsulta
    """)
    rows = db.execute(base, {"q": q, "pat": f"%{q}%"}).fetchall()
    return [{"snomed_id": str(r[0]), "interconsulta": r[1]} for r in rows]


@router.get("/estudios")
def list_estudios(
    q: str = "",
    tipo: str = "",
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lista estudios (diagnóstico por imágenes + laboratorio)."""
    base = text("""
        SELECT snomed_id, estudio, tipo_estudio
        FROM v_snomed_estudios
        WHERE (:q = '' OR estudio ILIKE :pat)
          AND (:tipo = '' OR tipo_estudio = :tipo)
        ORDER BY tipo_estudio, estudio
    """)
    rows = db.execute(base, {"q": q, "pat": f"%{q}%", "tipo": tipo}).fetchall()
    return [
        {"snomed_id": str(r[0]), "estudio": r[1], "tipo_estudio": r[2]}
        for r in rows
    ]


@router.get("/procedimientos")
def list_procedimientos(
    q: str = "",
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lista procedimientos clínicos."""
    base = text("""
        SELECT snomed_id, procedimiento
        FROM v_snomed_procedimientos_clinicos
        WHERE (:q = '' OR procedimiento ILIKE :pat)
        ORDER BY procedimiento
    """)
    rows = db.execute(base, {"q": q, "pat": f"%{q}%"}).fetchall()
    return [{"snomed_id": str(r[0]), "procedimiento": r[1]} for r in rows]
