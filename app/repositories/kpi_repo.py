# app/repositories/kpi_repo.py
from __future__ import annotations

from datetime import date
from typing import List, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.models import Patient, EPC
from app.repositories.patient_repo import PatientRepo


class KPIRepo:
    """
    Repositorio de KPIs para el dashboard clínico.

    - Usa PatientRepo.count_by_estado() para la distribución de estados
      (internacion, falta_epc, epc_generada, alta).
    - Usa la tabla EPC para contar epicrisis generadas (hoy, mes actual, totales).
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # KPIs principales para el dashboard
    # ------------------------------------------------------------------
    def kpis(self) -> Dict:
        # Total de pacientes activos (tabla patients)
        total_pacientes = int(self.db.query(func.count(Patient.id)).scalar() or 0)

        # Distribución de estados lógicos
        # (usa patients.estado como fuente de verdad, con fallback a patient_status)
        dist_estados = PatientRepo(self.db).count_by_estado()
        internacion = dist_estados.get("internacion", 0)
        falta_epc = dist_estados.get("falta_epc", 0)
        epc_generada = dist_estados.get("epc_generada", 0)
        alta = dist_estados.get("alta", 0)

        # Ocupación (porcentaje de pacientes internados sobre el total)
        ocupacion_pct = (
            round((internacion / total_pacientes) * 100, 1)
            if total_pacientes > 0 and internacion > 0
            else 0.0
        )

        # ------------------------------------------------------------------
        # KPIs de Epicrisis (tabla EPC)
        # ------------------------------------------------------------------
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        # Usamos created_at como fecha básica; si luego usás fecha_emision
        # y es un Date/DateTime, se puede hacer coalesce.
        fecha_col = func.date(func.coalesce(EPC.fecha_emision, EPC.created_at))

        # Total de EPC generadas (todas las filas en EPC)
        total_epc = int(self.db.query(func.count(EPC.id)).scalar() or 0)

        # EPC generadas hoy
        epc_hoy = int(
            self.db.query(func.count(EPC.id))
            .filter(fecha_col == hoy)
            .scalar()
            or 0
        )

        # EPC generadas en el mes actual (month-to-date)
        epc_mtd = int(
            self.db.query(func.count(EPC.id))
            .filter(fecha_col >= inicio_mes)
            .filter(fecha_col <= hoy)
            .scalar()
            or 0
        )

        # ------------------------------------------------------------------
        # Estructura EXACTA que espera el frontend (Dashboard.tsx)
        # ------------------------------------------------------------------
        return {
            # Totales
            "total_pacientes": total_pacientes,

            # Distribución por estado para las cards y el gráfico
            "pacientes_por_estado": {
                "internacion": internacion,
                "falta_epc": falta_epc,
                "epc_generada": epc_generada,
                "alta": alta,
            },

            # Para compatibilidad / posibles usos futuros
            "pacientes_totales": total_pacientes,
            "distribucion_estados": dist_estados,
            "estado_counts": dist_estados,
            "internacion": internacion,
            "falta_epc": falta_epc,
            "epc_generadas": epc_generada,
            "altas": alta,
            "internacion_ocupacion_pct": ocupacion_pct,

            # EPC: hoy y mes en curso (MTD)
            "epc_totales": total_epc,
            "epc_hoy": epc_hoy,
            "epc_mtd": epc_mtd,
        }

    # ------------------------------------------------------------------
    # Series: EPC por día en el mes actual
    # ------------------------------------------------------------------
    def epc_daily_current_month(self) -> List[Dict]:
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        fecha_col = func.date(func.coalesce(EPC.fecha_emision, EPC.created_at))

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

        # Últimos 12 registros
        rows = rows[-12:]

        series: List[Dict] = []
        for anio, mes, total in rows:
            label = f"{int(anio):04d}-{int(mes):02d}"  # YYYY-MM
            series.append(
                {
                    "month": label,
                    "label": label,
                    "count": int(total or 0),
                }
            )
        return series