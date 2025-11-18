from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, List

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


def _safe_json(text: str) -> Optional[Dict[str, Any]]:
    # Regex to find a JSON object within backticks or just as a block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```|(\{.*?\})", text, re.DOTALL)
    if match:
        # Prioritize the first capturing group (with backticks), fallback to the second
        json_str = match.group(1) or match.group(2)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None


def _extract_text(resp_json: Dict[str, Any]) -> str:
    """
    Respuesta típica:
    {
      "candidates":[
        {"content":{"parts":[{"text":"..."}]}}
      ]
    }
    """
    try:
        candidates = resp_json.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "\n".join([t for t in texts if t])
    except Exception:
        return ""


def _json_or_text_from_resp(resp: httpx.Response) -> str:
    try:
        return json.dumps(resp.json(), ensure_ascii=False)
    except Exception:
        return resp.text


def _build_hce_prompt(hce_text: str) -> str:
    return f"""
Eres un experto extrayendo datos de Historias Clínicas Electrónicas (HCE).
Analiza el siguiente texto de una HCE y extrae los datos demográficos del paciente y los datos de admisión.

**Reglas estrictas:**
1.  Responde **SOLO** con un objeto JSON. No incluyas texto adicional, explicaciones, ni la palabra "json".
2.  La estructura del JSON debe ser la siguiente. Si un campo no se encuentra, usa `null` como valor.
    {{
      "apellido": "string | null",
      "nombre": "string | null",
      "dni": "string | null",
      "sexo": "string | null",
      "fecha_nacimiento": "string (formato AAAA-MM-DD) | null",
      "obra_social": "string | null",
      "nro_beneficiario": "string | null",
      "admision_num": "string | null",
      "motivo_ingreso": "string | null",
      "cama": "string | null",
      "habitacion": "string | null",
      "protocolo": "string | null",
      "sector": "string | null",
      "diagnostico_ingreso": "string | null"
    }}
3.  Para el campo "sexo", normalízalo a "Masculino" o "Femenino" si es posible.
4.  Para el campo "fecha_nacimiento", formatéalo como AAAA-MM-DD si es posible.

**Texto de la HCE a analizar:**

---
{hce_text}
---
"""


class GeminiAIService:
    """
    Cliente REST mínimo para Google Gemini con:
      - header 'x-goog-api-key' (recomendado)
      - fallback automático de modelos si el principal no está disponible (404)
      - control de errores 401/403 con hint claro
      - responseMimeType opcional a JSON

    Variables:
      settings.GEMINI_API_HOST      (ej: https://generativelanguage.googleapis.com)
      settings.GEMINI_API_VERSION   (ej: v1beta)
      settings.GEMINI_MODEL         (ej: gemini-1.5-flash-8b)
    """

    _FALLBACK_MODELS: List[str] = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-pro",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        host: Optional[str] = None,
        version: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.host = (host or settings.GEMINI_API_HOST).rstrip("/")
        self.version = version or settings.GEMINI_API_VERSION

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY no configurada.")

    async def _call_gemini(
        self,
        prompt: str,
        want_json: bool = True,
        extra_system_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        models_to_try: List[str] = []
        if self.model:
            models_to_try.append(self.model)
        models_to_try.extend([m for m in self._FALLBACK_MODELS if m not in models_to_try])

        last_resp: Optional[httpx.Response] = None

        for mdl in models_to_try:
            url = f"{self.host}/{self.version}/models/{mdl}:generateContent"
            headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

            payload: Dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            }
            if extra_system_instructions:
                payload["system_instruction"] = {"parts": [{"text": extra_system_instructions}]}

            if want_json:
                payload["generationConfig"] = {"responseMimeType": "application/json"}

            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                last_resp = resp

                if resp.status_code == 404:
                    log.warning("Gemini 404 con modelo '%s' → pruebo siguiente fallback…", mdl)
                    continue

                if resp.status_code in (401, 403):
                    detail = _json_or_text_from_resp(resp)
                    raise RuntimeError(
                        f"Gemini auth/config error ({resp.status_code}): {detail}. "
                        "Revisá que tu proyecto tenga habilitada la 'Generative Language API' "
                        "y que la API key sea de Google AI Studio o de GCP con esa API habilitada."
                    )

                resp.raise_for_status()
                data = resp.json()
                text = _extract_text(data)

                if want_json:
                    parsed = _safe_json(text)
                    if parsed is not None:
                        return {"json": parsed, "_provider": "gemini", "_model": mdl}
                    return {"raw_text": text, "_provider": "gemini", "_model": mdl}

                return {"raw_text": text, "_provider": "gemini", "_model": mdl}

            except httpx.HTTPStatusError as e:
                detail = _json_or_text_from_resp(last_resp) if last_resp is not None else str(e)
                raise RuntimeError(f"Gemini API error ({e.response.status_code}): {detail}") from e

            except httpx.RequestError as e:
                raise RuntimeError(f"Gemini network error: {e}") from e

        last_detail = _json_or_text_from_resp(last_resp) if last_resp is not None else "sin respuesta"
        tried = ", ".join(models_to_try)
        raise RuntimeError(
            f"No se pudo generar con Gemini (modelos intentados: {tried}). Último detalle: {last_detail}"
        )

    async def generate_epc(
        self,
        prompt: str,
        want_json: bool = True,
        extra_system_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._call_gemini(
            prompt, want_json=want_json, extra_system_instructions=extra_system_instructions
        )

    async def extract_patient_data_from_hce(self, hce_text: str) -> Dict[str, Any]:
        prompt = _build_hce_prompt(hce_text)
        result = await self._call_gemini(prompt, want_json=True)
        
        if "json" not in result or not isinstance(result["json"], dict):
            raise RuntimeError("La respuesta de la IA no contenía un JSON válido para los datos del paciente.")
            
        return result["json"]