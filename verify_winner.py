import httpx
import json
import asyncio
import sys

# Ensure UTF-8 output for Windows terminal
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BOT_URL = "http://localhost:8080"

async def run_scenario(client, name, cat_slug, merchant_payload, trigger_payload):
    print(f"\n--- SCENARIO: {name} ({cat_slug.upper()}) ---")
    
    # 1. Category
    with open(f"dataset/categories/{cat_slug}.json") as f:
        cat_data = json.load(f)
    await client.post(f"{BOT_URL}/v1/context", json={"scope": "category", "context_id": cat_slug, "version": 1, "payload": cat_data})
    
    # 2. Merchant
    merchant_payload["category_slug"] = cat_slug
    await client.post(f"{BOT_URL}/v1/context", json={"scope": "merchant", "context_id": merchant_payload["merchant_id"], "version": 1, "payload": merchant_payload})
    
    # 3. Trigger
    await client.post(f"{BOT_URL}/v1/context", json={"scope": "trigger", "context_id": trigger_payload["id"], "version": 1, "payload": trigger_payload})
    
    # 4. Tick
    resp = await client.post(f"{BOT_URL}/v1/tick", json={
        "now": "2026-05-03T10:00:00Z",
        "available_triggers": [trigger_payload["id"]]
    })
    
    actions = resp.json().get("actions", [])
    if actions:
        action = actions[0]
        print(f"WINNER MESSAGE:\n\"{action['body']}\"")
        print(f"RATIONALE: {action['rationale']}")
    else:
        print("No actions generated.")

async def test_global_suite():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Restaurant IPL Scenario
        await run_scenario(client, "Strategic Pivot (IPL)", "restaurants", {
            "merchant_id": "m_rest_1",
            "identity": {"name": "SK Pizza Junction", "owner_first_name": "Suresh", "locality": "Sant Nagar"},
            "performance": {"ctr": 0.04, "delta_7d": {"covers": -0.15}},
            "offers": [{"id": "o2", "title": "BOGO Pizza", "status": "active"}]
        }, {
            "id": "t_ipl", "kind": "ipl_match_today", "merchant_id": "m_rest_1",
            "payload": {"match": "DC vs MI", "suppression_key": "ipl:2026:W17"}
        })

        # 2. Pharmacy Supply Alert Scenario
        await run_scenario(client, "Derived Math (Supply Alert)", "pharmacies", {
            "merchant_id": "m_pharm_1",
            "identity": {"name": "Apollo Pharmacy", "owner_first_name": "Ramesh", "locality": "Malviya Nagar"},
            "performance": {"ctr": 0.05},
            "customer_aggregate": {"chronic_count": 22, "total_roster": 240},
            "offers": []
        }, {
            "id": "t_recall", "kind": "supply_alert", "merchant_id": "m_pharm_1",
            "payload": {"mfr": "Mfr Z", "batches": ["AT2024-1102"]}
        })

if __name__ == "__main__":
    asyncio.run(test_global_suite())
