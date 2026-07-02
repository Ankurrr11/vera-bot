import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def stress_test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- PHASE 1: WARMUP ---")
        h = await client.get(f"{LIVE_URL}/v1/healthz")
        print(f"Health: {h.status_code}")

        print("\n--- PHASE 2: CONTEXT PUSH ---")
        # Category
        with open("dataset/categories/dentists.json") as f:
            cat_data = json.load(f)
        c_resp = await client.post(f"{LIVE_URL}/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat_data})
        print(f"Category Push: {c_resp.status_code} - {c_resp.text}")
        
        # Merchant
        merch_payload = {
            "merchant_id": "m_test", "identity": {"name": "Test Clinic", "owner_first_name": "Ankur"},
            "performance": {"ctr": 0.008}, "category_slug": "dentists"
        }
        m_resp = await client.post(f"{LIVE_URL}/v1/context", json={"scope": "merchant", "context_id": "m_test", "version": 1, "payload": merch_payload})
        print(f"Merchant Push: {m_resp.status_code} - {m_resp.text}")

        # Trigger
        t_resp = await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "trigger", "context_id": "t1", "version": 1, 
            "payload": {"id": "t1", "kind": "research", "merchant_id": "m_test"}
        })
        print(f"Trigger Push: {t_resp.status_code} - {t_resp.text}")

        print("\n--- PHASE 3: TICK (THE CRASH POINT) ---")
        resp = await client.post(f"{LIVE_URL}/v1/tick", json={
            "now": datetime.utcnow().isoformat() + "Z", 
            "available_triggers": ["t1"]
        })
        
        print(f"Tick Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"!!!! ERROR FROM SERVER !!!!\n{resp.text}")
        else:
            print(f"Success! Response: {json.dumps(resp.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(stress_test())
