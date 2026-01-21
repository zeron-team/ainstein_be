# app/repositories/kpi_repo.py
from __future__ import annotations

from datetime import date
from typing import List, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.models import Patient, EPC
from app.repositories.patient_repo import PatientRepo  # por si lo necesitás en otros métodos
import logging

log = logging.getLogger(__name__)


class KPIRepo:
    """
    Repositorio de KPIs para el dashboard.

    - Usa directamente patients.estado para la distribución de estados
      (internacion, falta_epc, epc_generada, alta, etc.).
    - Usa la tabla EPC para contar epicrisis generadas (hoy, mes actual, totales).
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _count_by_estado(self) -> Dict[str, int]:
        """
        Devuelve un dict {estado: cantidad} agrupando por patients.estado.
        """
        rows = (
            self.db.query(Patient.estado, func.count(Patient.id))
            .group_by(Patient.estado)
            .all()
        )

        dist: Dict[str, int] = {}
        for estado, cnt in rows:
            key = (estado or "").strip() or "sin_estado"
            dist[key] = int(cnt or 0)

        log.info("[KPIRepo] Distribución de estados: %s", dist)
        return dist

    # ------------------------------------------------------------------
    # KPIs principales para el dashboard
    # ------------------------------------------------------------------
    def kpis(self) -> Dict:
        # Total de pacientes activos (tabla patients)
        total_pacientes = int(
            self.db.query(func.count(Patient.id)).scalar() or 0
        )

        # Distribución de estados (directo desde patients.estado)
        dist_estados = self._count_by_estado()

        internacion = dist_estados.get("internacion", 0)
        falta_epc = dist_estados.get("falta_epc", 0)
        epc_generada_pacientes = dist_estados.get("epc_generada", 0)
        alta = dist_estados.get("alta", 0)

        # Objeto exactamente como lo espera el front: data.pacientes_por_estado
        pacientes_por_estado: Dict[str, int] = {
            "internacion": internacion,
            "falta_epc": falta_epc,
            "epc_generada": epc_generada_pacientes,
            "alta": alta,
        }
        # Incluimos cualquier otro estado adicional que pueda aparecer
        for k, v in dist_estados.items():
            if k not in pacientes_por_estado:
                pacientes_por_estado[k] = v

        # Ocupación (porcentaje de pacientes internados sobre el total)
        ocupacion_pct = (
            round((internacion / total_pacientes) * 100, 1)
            if total_pacientes > 0 and internacion > 0
            else 0.0
        )

        # KPIs de epicrisis (tabla EPC)
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        # Total de EPC registradas en tabla EPC
        total_epc = int(
            self.db.query(func.count(EPC.id)).scalar() or 0
        )

        # Columna de fecha para agrupar/filtrar: preferimos fecha_emision, si no, created_at
        fecha_col = func.date(
            func.coalesce(EPC.fecha_emision, EPC.created_at)
        )

        # EPC generadas hoy
        epc_hoy = int(
            self.db.query(func.count(EPC.id))
            .filter(fecha_col == hoy)
            .scalar()
            or 0
        )

        # EPC generadas en el mes actual (desde el 1 del mes hasta hoy)
        epc_mes_actual = int(
            self.db.query(func.count(EPC.id))
            .filter(fecha_col >= inicio_mes)
            .filter(fecha_col <= hoy)
            .scalar()
            or 0
        )

        # Log para ver rápidamente qué está devolviendo
        log.info(
            "[KPIRepo] KPIs calculados | total_pacientes=%s, internacion=%s, "
            "falta_epc=%s, epc_generada_pacientes=%s, alta=%s, "
            "total_epc=%s, epc_hoy=%s, epc_mes_actual=%s",
            total_pacientes,
            internacion,
            falta_epc,
            epc_generada_pacientes,
            alta,
            total_epc,
            epc_hoy,
            epc_mes_actual,
        )

        # Devolvemos varias keys “amigables” y alias para no romper el front
        return {
            # Totales de pacientes
            "pacientes_totales": total_pacientes,
            "total_pacientes": total_pacientes,

            # 👈 EXACTO como lo espera el Dashboard
            "pacientes_por_estado": pacientes_por_estado,

            # Distribución por estado (cards principales, alias antiguos)
            "internacion": internacion,
            "pacientes_internacion": internacion,

            "falta_epc": falta_epc,
            "pacientes_falta_epc": falta_epc,

            # Pacientes con EPC generada (usa patients.estado = 'epc_generada')
            "epc_generadas": epc_generada_pacientes,
            "pacientes_epc_generadas": epc_generada_pacientes,
            "epc_generadas_pacientes": epc_generada_pacientes,
            "total_pacientes_epc_generada": epc_generada_pacientes,

            "altas": alta,
            "pacientes_alta": alta,

            # Porcentaje de ocupación (para Internación)
            "internacion_ocupacion_pct": ocupacion_pct,

            # EPC (hoy, mes, total) desde tabla EPC
            "epc_totales": total_epc,
            "epc_total": total_epc,
            "total_epc": total_epc,

            "epc_hoy": epc_hoy,
            "epc_dia": epc_hoy,
            "epc_today": epc_hoy,

            # 👈 alias EXACTO para el front: epc_mtd
            "epc_mes_actual": epc_mes_actual,
            "epc_mes": epc_mes_actual,
            "epc_mes_en_curso": epc_mes_actual,
            "epc_mtd": epc_mes_actual,

            # Distribución completa (para gráfica “Distribución por estado”)
            "distribucion_estados": dist_estados,
            "estado_counts": dist_estados,
        }

    # ------------------------------------------------------------------
    # Series: EPC por día en el mes actual
    # ------------------------------------------------------------------
    def epc_daily_current_month(self) -> List[Dict]:
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        fecha_col = func.date(
            func.coalesce(EPC.fecha_emision, EPC.created_at)
        )

        rows = (
            self.db.query(
                fecha_col.label("dia"),
                func.count(EPC.id).label("total"),
            )
            .filter(fecha_col >= inicio_mes)
            .filter(fecha_col <= hoy)
            .group_by(fecha_col)
            .order_by(fecha_col)
            .all()
        )

        return [
            {
                "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                "count": int(total or 0),
            }
            for d, total in rows
        ]

    # ------------------------------------------------------------------
    # Series: EPC mensuales en los últimos 12 meses
    # ------------------------------------------------------------------
    def epc_monthly_last_12(self) -> List[Dict]:
        # Agrupamos por año/mes de fecha_emision (o created_at si es nulo)
        fecha_base = func.coalesce(EPC.fecha_emision, EPC.created_at)
        year_col = func.year(fecha_base)
        month_col = func.month(fecha_base)

        rows = (
            self.db.query(
                year_col.label("anio"),
                month_col.label("mes"),
                func.count(EPC.id).label("total"),
            )
            .group_by(year_col, month_col)
            .order_by(year_col, month_col)
            .all()
        )

        # Nos quedamos con los últimos 12 registros
        rows = rows[-12:]

        series: List[Dict] = []
        for anio, mes, total in rows:
            label = f"{int(anio):04d}-{int(mes):02d}"
            series.append(
                {
                    "month": label,
                    "label": label,
                    "count": int(total or 0),
                }
            )
        return series