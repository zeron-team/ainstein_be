import httpx, json
from app.core.config import settings

class GeminiAIService:
    BASE = "https://generativelanguage.googleapis.com/v1beta"
    def __init__(self, model: str | None = None):
        self.model = model or settings.GEMINI_MODEL
        self.key = settings.GEMINI_API_KEY

    async def generate_epc(self, prompt: str) -> dict:
        url = f"{self.BASE}/models/{self.model}:generateContent?key={self.key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            text = data.get("candidates", [{}])[0].get("content",{}).get("parts", [{}])[0].get("text", "{}")
            return json.loads(text)
