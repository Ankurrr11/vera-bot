import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "http://localhost:8081"

async def hammer_audit():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- STARTING THE DEFINITIVE HAMMER AUDIT ---")
        
        scenarios = [
            ("EMOJI_ONLY", "😊🚀📉"),
            ("MEMORY_TEST", "Wait, what did you say about my CTR earlier?"),
            ("LONG_RANT", "I am very unhappy with the current performance. " * 30),
            ("EMPTY_MSG", ""),
        ]
        
        # Setup context
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant", "context_id": "m_hammer", "version": 1,
            "payload": {
                "merchant_id": "m_hammer",
                "identity": {"name": "Hammer Clinic", "owner_first_name": "Ankur"},
                "category_slug": "dentists",
                "performance": {"ctr": 0.008}
            }
        })
        
        for name, msg in scenarios:
            print(f"\n[TESTING: {name}]")
            # Use a FRESH conversation_id for each test to avoid state pollution
            conv_id = f"conv_hammer_{name}"
            
            # 1. Warm up conversation with a real business message first
            await client.post(f"{LIVE_URL}/v1/reply", json={
                "conversation_id": conv_id, "merchant_id": "m_hammer",
                "message": "Hello Vera", "from_role": "merchant", "turn_number": 1,
                "received_at": datetime.utcnow().isoformat() + "Z"
            })
            
            # 2. Send the Hammer message
            resp = await client.post(f"{LIVE_URL}/v1/reply", json={
                "conversation_id": conv_id, "merchant_id": "m_hammer",
                "message": msg, "from_role": "merchant", "turn_number": 2,
                "received_at": datetime.utcnow().isoformat() + "Z"
            })
            res = resp.json()
            print(f"  Action: {res.get('action', 'ERROR').upper()}")
            if "body" in res:
                print(f"  Response: \"{res.get('body')[:100]}...\"")

if __name__ == "__main__":
    asyncio.run(hammer_audit())
