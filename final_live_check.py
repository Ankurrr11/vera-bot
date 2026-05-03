import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def omni_test_live():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- VERIFYING LIVE DEPLOYMENT ---")
        
        # 1. Check Version
        r0 = await client.get(f"{LIVE_URL}/")
        print(f"  Live Version: {r0.json().get('version', 'unknown')}")
        
        if "1.0.2" not in r0.json().get('version', ''):
            print("  [WAIT] Server still on old version. Waiting...")
            return

        # 2. SETUP DATA
        M_ID = f"m_final_{int(datetime.utcnow().timestamp())}"
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": M_ID, "version": 1,
            "payload": {
                "merchant_id": M_ID,
                "identity": {"name": "Royal Dental", "owner_first_name": "Ankur"},
                "category_slug": "dentists",
                "performance": {"ctr": 0.008}
            }
        })
        print(f"  Fresh Context ({M_ID}) Pushed.")
        
        # 3. TEST: DATA-DRIVEN REASONING
        print("\n[TEST: DATA-DRIVEN REASONING]")
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": f"conv_{M_ID}", "merchant_id": M_ID,
            "message": "Vera, how is my CTR doing?", "from_role": "merchant", "turn_number": 1,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        res = resp.json()
        print(f"  Vera: \"{res.get('body')}\"")
        if "0.8%" in res.get('body', '') and "3.0%" in res.get('body', ''):
            print("  [PASS] Data Sieve is LIVE.")
        else:
            print("  [FAIL] Data Sieve failed to cite benchmarks.")

if __name__ == "__main__":
    asyncio.run(omni_test_live())
