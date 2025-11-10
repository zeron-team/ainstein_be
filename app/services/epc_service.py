from app.repositories.epc_repo import EPCRepo
from app.repositories.patient_repo import PatientRepo
from app.repositories.branding_repo import BrandingRepo
from app.services.ai_gemini_service import GeminiAIService
from app.services.hce_parser import extract_text_from_hce

PROMPT_EPC = """
Eres un médico especialista en clínica médica en Argentina. Redacta una Epicrisis (EPC) a partir de la siguiente Historia Clínica Electrónica (HCE).
Formato de salida: JSON ESTRICTO con las claves:
{
"datos_paciente": {"apellido": "...", "nombre": "...", "dni": "...", "obra_social": "...", "nro_beneficiario": "..."},
"admision": {"sector": "...", "habitacion": "...", "cama": "...", "fecha_ingreso": "YYYY-MM-DD", "fecha_egreso": "YYYY-MM-DD?"},
"motivo_internacion": "...",
"diagnostico_principal_cie10": "CODIGO",
"evolucion": "...",
"procedimientos": ["..."],
"interconsultas": ["..."],
"medicacion": [{"farmaco":"...", "dosis":"...", "via":"...", "frecuencia":"..."}],
"indicaciones_alta": ["..."],
"recomendaciones": ["..."],
"observaciones": "..."
}
Restricciones: usar terminología local (AR) y CIE-10 si se infiere. No inventes; si falta, "PENDIENTE".
HCE:\n---\n{HCE_TEXTO}\n---
"""

class EPCService:
        def __init__(self, epc_repo: EPCRepo, patient_repo: PatientRepo, mongo, branding_repo: BrandingRepo):
            self.repo = epc_repo
            self.patients = patient_repo
            self.mongo = mongo
            self.branding = branding_repo
            self.ai = GeminiAIService()

        async def generate_from_hce(self, patient_id: str, admission_id: str | None, hce_oid: str | None, user_id: str):
            hce_text = await extract_text_from_hce(self.mongo, hce_oid)
            prompt = PROMPT_EPC.replace("{HCE_TEXTO}", (hce_text or "")[:40000])
            epc_json = await self.ai.generate_epc(prompt)
            epc = await self.repo.upsert_draft(patient_id, admission_id, epc_json, user_id)
            self.patients.update_estado(patient_id, 'epc_generada')
            return epc

        async def get_latest(self, epc_id: str):
            return await self.repo.get_with_latest_version(epc_id)
