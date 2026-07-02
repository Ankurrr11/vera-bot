import httpx
import json
import asyncio
from datetime import datetime

# TESTING LOCAL FIXES NOW
LIVE_URL = "http://localhost:8080"

async def chaotic_audit():
    async with httpx.AsyncClient(timeout=45.0) as client:
        print("--- STARTING CHAOTIC JUDGE AUDIT (LOCAL) ---")
        
        scenarios = [
            ("HOSTILITY", "You are a piece of trash spammer. Stop this now!"),
            ("AGREEMENT_YES", "Yes"),
            ("AGREEMENT_OK", "Ok"),
            ("SLOT_PICK", "I pick Sunday at 11am sharp."),
        ]
        
        for name, msg in scenarios:
            print(f"\n[TESTING: {name}] Message: \"{msg}\"")
            resp = await client.post(f"{LIVE_URL}/v1/reply", json={
                "conversation_id": f"conv_chaotic_{name}", "merchant_id": "m_test",
                "message": msg, "from_role": "merchant", "turn_number": 2,
                "received_at": datetime.utcnow().isoformat() + "Z"
            })
            
            res = resp.json()
            print(f"  Action: {res.get('action').upper()}")
            if "body" in res:
                print(f"  Response: \"{res.get('body')}\"")

if __name__ == "__main__":
    asyncio.run(chaotic_audit())
