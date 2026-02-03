from app.core.config import settings
print(f"Gemini Key: {settings.GEMINI_API_KEY[:5]}...")
print(f"Markey Key: '{settings.AINSTEIN_API_KEY}'")
print(f"Markey Token: '{settings.AINSTEIN_TOKEN}'")
print(f"Qdrant Enabled: {settings.QDRANT_ENABLED}")
