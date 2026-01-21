# app/services/epc_history.py
from __future__ import annotations

from typing import List, Optional
import logging

from sqlalchemy.orm import Session

from app.domain import models

log = logging.getLogger(__name__)


def log_epc_event(
    db: Session,
    epc_id: str,
    user_name: Optional[str],
    action: str,
) -> None:
    """
    Registra un evento en el historial de una EPC.

    - epc_id: UUID de la EPC (es el mismo _id de Mongo, guardado como texto).
    - user_name: username del usuario que realizó la acción (o None para 'sistema').
    - action: descripción humana de la acción (ej.: 'EPC generada por IA', 'EPC validada').
    """
    # Si por alguna razón no llega usuario, dejamos explícito "sistema"
    if not user_name:
        user_name = "sistema"

    try:
        ev = models.EPCEvent(epc_id=epc_id, by=user_name, action=action)
        db.add(ev)
        db.commit()
    except Exception as exc:
        db.rollback()
        log.warning(
            "[log_epc_event] Error guardando evento de EPC "
            "(epc_id=%s, user=%s, action=%s): %s",
            epc_id,
            user_name,
            action,
            exc,
        )


def get_epc_history(db: Session, epc_id: str) -> List[models.EPCEvent]:
    """
    Devuelve la lista de eventos de una EPC, ordenados del más reciente al más antiguo.
    """
    try:
        return (
            db.query(models.EPCEvent)
            .filter(models.EPCEvent.epc_id == epc_id)
            .order_by(models.EPCEvent.at.desc())
            .all()
        )
    except Exception as exc:
        log.warning(
            "[get_epc_history] Error consultando historial de EPC (epc_id=%s): %s",
            epc_id,
            exc,
        )
        return []