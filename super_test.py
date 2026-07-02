import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "http://localhost:8080"

async def super_test():
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("--- STARTING SUPER TEST (CONTEXT + LOGIC) ---")
        
        # 1. PUSH CONTEXT
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": "m_test", "version": 1,
            "payload": {
                "merchant_id": "m_test",
                "identity": {"name": "Test Clinic", "owner_first_name": "Ankur"},
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

        # 2. TEST AGREEMENT (Should NOT be fallback anymore)
        print("\n[TEST: AGREEMENT]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": "conv_1", "merchant_id": "m_test",
            "message": "Yes, let's do it", "from_role": "merchant", "turn_number": 2,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print(f"  Action: {resp.json().get('action').upper()}")
        print(f"  Body: \"{resp.json().get('body')}\"")

        # 3. TEST SLOT PICK (Should be specific)
        print("\n[TEST: SLOT PICK]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": "conv_2", "merchant_id": "m_test",
            "message": "Sunday at 11am", "from_role": "merchant", "turn_number": 2,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print(f"  Action: {resp.json().get('action').upper()}")
        print(f"  Body: \"{resp.json().get('body')}\"")

if __name__ == "__main__":
    asyncio.run(super_test())
