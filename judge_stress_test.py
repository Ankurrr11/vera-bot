import httpx
import json
import asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def stress_test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- PHASE 1: WARMUP & SCHEMA ---")
        try:
            h = await client.get(f"{LIVE_URL}/v1/healthz")
            m = await client.get(f"{LIVE_URL}/v1/metadata")
            print(f"[PASS] Health: {h.status_code}")
            print(f"[PASS] Metadata: {m.json()}")
        except Exception as e:
            print(f"[FAIL] Warmup failed: {e}")
            return

        print("\n--- PHASE 2: ADAPTIVE INJECTION (DENTIST) ---")
        # Load Category
        with open("dataset/categories/dentists.json") as f:
            cat_data = json.load(f)
        await client.post(f"{LIVE_URL}/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat_data})
        
        # Load Merchant with poor stats
        merch_payload = {
            "merchant_id": "m_live_test", "identity": {"name": "Live Demo Clinic", "owner_first_name": "Ankur"},
            "performance": {"ctr": 0.008}, "category_slug": "dentists",
            "customer_aggregate": {"high_risk_count": 88, "total_roster": 400}
        }
        await client.post(f"{LIVE_URL}/v1/context", json={"scope": "merchant", "context_id": "m_live_test", "version": 1, "payload": merch_payload})

        # Scenario: Research Trigger
        print("\n--- PHASE 3: COMPULSION & SPECIFICITY TEST ---")
        resp = await client.post(f"{LIVE_URL}/v1/tick", json={
            "now": datetime.utcnow().isoformat() + "Z", 
            "available_triggers": ["t_live_1"]
        }, params={"trigger_id": "t_live_1"}) # Mocking trigger push internally
        
        # Note: Since I can't push a trigger from outside easily without the correct ID, 
        # I'll just push it via context first
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "trigger", "context_id": "t_live_1", "version": 1, 
            "payload": {"id": "t_live_1", "kind": "research", "merchant_id": "m_live_test"}
        })
        
        resp = await client.post(f"{LIVE_URL}/v1/tick", json={
            "now": datetime.utcnow().isoformat() + "Z", 
            "available_triggers": ["t_live_1"]
        })
        
        actions = resp.json().get("actions", [])
        if actions:
            body = actions[0]["body"]
            print(f"JUDGE VERDICT ON COMPOSITION:\n\"{body}\"")
            if "JIDA" in body and "0.8%" in body and "88" in body:
                print("[PASS] 10/10: Specificity & Citations detected!")
            else:
                print("[WARN] Missing specificity or citations.")
        else:
            print("[FAIL] No actions generated!")

        print("\n--- PHASE 4: REPLAY LOOP PREVENTION ---")
        reply_resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": "conv_live_1", "merchant_id": "m_live_test",
            "message": "Thank you", "from_role": "merchant",
            "received_at": datetime.utcnow().isoformat() + "Z", "turn_number": 2
        })
        if reply_resp.json().get("action") == "end":
            print("[PASS] Loop Prevention: Bot correctly ended on 'Thank you'")
        else:
            print(f"[FAIL] Bot kept talking on auto-reply: {reply_resp.json().get('action')}")

if __name__ == "__main__":
    asyncio.run(stress_test())
