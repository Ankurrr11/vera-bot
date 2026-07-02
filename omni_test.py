import httpx
import json
import asyncio
from datetime import datetime

# USING PORT 8081 TO AVOID PORT CONFLICTS
LIVE_URL = "http://localhost:8081"

async def omni_test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- STARTING OMNI-TEST (PORT 8081) ---")
        
        # 1. SETUP DATA
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": "m_omni", "version": 1,
            "payload": {
                "merchant_id": "m_omni",
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
            "scope": "trigger", "context_id": "t_omni", "version": 1,
            "payload": {
                "trigger_id": "t_omni", "merchant_id": "m_omni", "kind": "research",
                "payload": {"insight": "low_ctr"}
            }
        })

        # 2. FEATURE: DATA SIEVE + TICK
        print("\n[FEATURE: DATA SIEVE + TICK]")
        resp = await client.post(f"{LIVE_URL}/v1/tick", json={
            "now": datetime.utcnow().isoformat() + "Z",
            "available_triggers": ["t_omni"]
        })
        tick_res = resp.json()
        conv_id = tick_res["actions"][0]["conversation_id"]
        print(f"  Vera Body: \"{tick_res['actions'][0]['body']}\"")

        # 3. FEATURE: TOOL EXECUTION
        print("\n[FEATURE: TOOL EXECUTION]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": conv_id, "merchant_id": "m_omni",
            "message": "Pause my listing campaign now.", "from_role": "merchant", "turn_number": 2,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        res = resp.json()
        print(f"  Action: {res.get('action').upper()}")
        print(f"  Body: \"{res.get('body')}\"")

        # 4. FEATURE: SAFETY (JOKE BLOCK)
        print("\n[FEATURE: SAFETY (JOKE BLOCK)]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": conv_id, "merchant_id": "m_omni",
            "message": "Tell me a dentist joke.", "from_role": "merchant", "turn_number": 3,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print(f"  Action: {resp.json().get('action').upper()}")

if __name__ == "__main__":
    asyncio.run(omni_test())
