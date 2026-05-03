import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def audit_loops():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("--- AUDITING AUTO-REPLY LOOP PREVENTION ---")
        
        test_messages = ["Thank you", "Ok", "Thanks doc", "Theek hai"]
        
        for msg in test_messages:
            resp = await client.post(f"{LIVE_URL}/v1/reply", json={
                "conversation_id": "conv_loop_test",
                "merchant_id": "m_test",
                "message": msg,
                "from_role": "merchant",
                "received_at": datetime.utcnow().isoformat() + "Z",
                "turn_number": 2
            })
            
            action = resp.json().get("action")
            print(f"Merchant said: \"{msg}\" -> Vera Action: {action.upper()}")
            
            if action != "end":
                print(f"[FAIL] Bot kept talking! Response: {resp.json().get('body')}")
            else:
                print(f"[PASS] Loop broken.")

if __name__ == "__main__":
    asyncio.run(audit_loops())
