from sqlalchemy import text
from sqlalchemy.orm import Session

class KPIRepo:
    def __init__(self, db: Session):
        self.db = db

    def patients_by_status(self):
        sql = text("SELECT estado, COUNT(*) AS cantidad FROM patient_status GROUP BY estado")
        return list(self.db.execute(sql).mappings().all())

    def epc_daily_current_month(self):
        sql = text("""
            SELECT DATE(created_at) AS dia, COUNT(*) AS cantidad
            FROM epc
            WHERE created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
            GROUP BY dia ORDER BY dia
        """)
        return list(self.db.execute(sql).mappings().all())

    def epc_monthly_current_year(self):
        sql = text("""
            SELECT DATE_FORMAT(created_at,'%Y-%m') AS mes, COUNT(*) AS cantidad
            FROM epc
            WHERE YEAR(created_at)=YEAR(CURDATE())
            GROUP BY mes ORDER BY mes
        """)
        return list(self.db.execute(sql).mappings().all())
