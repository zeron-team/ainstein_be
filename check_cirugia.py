import asyncio
from app.adapters.mongo_client import get_mongo_db

async def get_test():
    db = get_mongo_db()
    
    # Try different ID formats depending on how it is requested
    doc = await db.hce_docs.find_one({"source.inteCodigo": 403003})
    if not doc:
        doc = await db.hce_docs.find_one({"source.inteCodigo": "403003"})
    if not doc:
        print("Document not found")
        return
        
    print(f"Doc found: hce_id={str(doc.get('_id'))}")
    historia = doc.get("ainstein", {}).get("historia", [])
    
    for entry in historia:
        procs = entry.get("indicacionProcedimientos", []) or []
        for p in procs:
            desc = p.get("procDescripcion", "")
            if "irug" in desc.lower() or "irug" in desc:
                print(f"PROCEDURE RAW: {repr(desc)}")
            
        # Also check plantillas just in case
        for plant in entry.get("plantillas", []) or []:
            for prop in plant.get("propiedades", []) or []:
                valor = prop.get("engpValor", "")
                if valor and "irug" in str(valor).lower():
                    print(f"PLANTILLA VALOR RAW: {repr(valor)}")

asyncio.run(get_test())
