import httpx
import json
import asyncio
from datetime import datetime

# CHECKING LOCALHOST NOW
LIVE_URL = "http://localhost:8080"

async def audit_off_topic():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("--- AUDITING OFF-TOPIC HANDLING (LOCAL FIX) ---")
        
        test_messages = ["What is the price of Bitcoin?", "Tell me a joke", "Weather in Mumbai?"]
        
        for msg in test_messages:
            try:
                resp = await client.post(f"{LIVE_URL}/v1/reply", json={
                    "conversation_id": "conv_off_topic",
                    "merchant_id": "m_test",
                    "message": msg,
                    "from_role": "merchant",
                    "received_at": datetime.utcnow().isoformat() + "Z",
                    "turn_number": 3
                })
                
                action = resp.json().get("action")
                print(f"Merchant asked: \"{msg}\" -> Vera Action: {action.upper()}")
            except Exception as e:
                print(f"Failed to call local server: {e}")

if __name__ == "__main__":
    asyncio.run(audit_off_topic())
