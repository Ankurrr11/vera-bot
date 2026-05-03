import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def omni_test_live():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- FORCING FRESH CONTEXT PUSH ---")
        
        # Use a BRAND NEW ID to ensure no old data interference
        M_ID = f"m_final_{int(datetime.utcnow().timestamp())}"
        
        # 1. SETUP DATA
        r1 = await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": M_ID, "version": 1,
            "payload": {
                "merchant_id": M_ID,
                "identity": {"name": "Fresh Dental", "owner_first_name": "Ankur"},
                "category_slug": "dentists",
                "performance": {"ctr": 0.008}
            }
        })
        print(f"  Merchant Push ({M_ID}): {r1.status_code} - {r1.text}")
        
        # 2. TEST: DATA-DRIVEN REASONING
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
