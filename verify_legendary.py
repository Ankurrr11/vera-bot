import httpx
import json
import asyncio
import sys
from datetime import datetime

# Ensure UTF-8 output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BOT_URL = "http://localhost:8080"

async def test_legendary_suite():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("--- 1. LOADING LEGENDARY CONTEXT ---")
        # Load Category
        with open("dataset/categories/dentists.json") as f:
            await client.post(f"{BOT_URL}/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": json.load(f)})
        
        # Load Merchant
        merchant_payload = {
            "merchant_id": "m_legend_1", "identity": {"name": "Legend Dental", "owner_first_name": "Ankur"},
            "performance": {"ctr": 0.012}, "category_slug": "dentists",
            "customer_aggregate": {"high_risk_count": 50, "total_roster": 200}
        }
        await client.post(f"{BOT_URL}/v1/context", json={"scope": "merchant", "context_id": "m_legend_1", "version": 1, "payload": merchant_payload})
        
        # Load Trigger 1
        await client.post(f"{BOT_URL}/v1/context", json={"scope": "trigger", "context_id": "t1", "version": 1, "payload": {"id": "t1", "kind": "research", "merchant_id": "m_legend_1"}})
        
        print("\n--- 2. TURN 1: Initial Research Message ---")
        resp1 = await client.post(f"{BOT_URL}/v1/tick", json={"now": datetime.utcnow().isoformat() + "Z", "available_triggers": ["t1"]})
        body1 = resp1.json()["actions"][0]["body"]
        print(f"VERA TURN 1:\n\"{body1}\"")
        
        # Load Trigger 2
        await client.post(f"{BOT_URL}/v1/context", json={"scope": "trigger", "context_id": "t2", "version": 1, "payload": {"id": "t2", "kind": "trend", "merchant_id": "m_legend_1"}})
        
        print("\n--- 3. TURN 2: Follow-up Continuity Check ---")
        resp2 = await client.post(f"{BOT_URL}/v1/tick", json={"now": datetime.utcnow().isoformat() + "Z", "available_triggers": ["t2"]})
        body2 = resp2.json()["actions"][0]["body"]
        print(f"VERA TURN 2 (FOLLOW-UP):\n\"{body2}\"")

        print("\n--- 4. TURN 3: Agentic Tool Execution ---")
        reply_resp = await client.post(f"{BOT_URL}/v1/reply", json={
            "conversation_id": "conv_m_legend_1_t2",
            "merchant_id": "m_legend_1",
            "message": "Yes, please pause my low-CTR ads for now.",
            "from_role": "merchant",
            "received_at": datetime.utcnow().isoformat() + "Z",
            "turn_number": 2
        })
        print(f"VERA TOOL RESPONSE:\n{json.dumps(reply_resp.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_legendary_suite())
