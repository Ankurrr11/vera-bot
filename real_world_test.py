import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "http://localhost:8080"

async def real_world_test():
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("--- STARTING REAL-WORLD FLOW TEST ---")
        
        # 1. SETUP DATA
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": "m_real", "version": 1,
            "payload": {
                "merchant_id": "m_real",
                "identity": {"name": "Royal Dental", "owner_first_name": "Ankur"},
                "category_slug": "dentists",
                "performance": {"ctr": 0.008}
            }
        })
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": {
                "slug": "dentists",
                "peer_stats": {"avg_ctr": 0.03}
            }
        })
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "trigger", "context_id": "t_real", "version": 1,
            "payload": {
                "trigger_id": "t_real", "merchant_id": "m_real", "kind": "research",
                "payload": {"insight": "CTR is low"}
            }
        })

        # 2. VERA INITIATES (TICK)
        print("\n[VERA INITIATES]")
        resp = await client.post(f"{LIVE_URL}/v1/tick", json={
            "now": datetime.utcnow().isoformat() + "Z",
            "available_triggers": ["t_real"]
        })
        tick_res = resp.json()
        conv_id = tick_res["actions"][0]["conversation_id"]
        print(f"  Vera said: \"{tick_res['actions'][0]['body']}\"")

        # 3. MERCHANT REPLIES "YES"
        print("\n[MERCHANT SAYS YES]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": conv_id, "merchant_id": "m_real",
            "message": "Yes, please do it.", "from_role": "merchant", "turn_number": 2,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print(f"  Action: {resp.json().get('action').upper()}")
        print(f"  Body: \"{resp.json().get('body')}\"")

if __name__ == "__main__":
    asyncio.run(real_world_test())
