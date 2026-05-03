import httpx, asyncio
from datetime import datetime

LIVE_URL = "https://vera-bot-vwrr.onrender.com"

async def run_checks():
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Check version endpoint
        try:
            r = await client.get(f"{LIVE_URL}/")
            version_info = r.json()
            print("[VERSION]", version_info)
        except Exception as e:
            print("[VERSION ERROR]", e)
            return

        # 2. Push fresh merchant and category context
        merchant_id = f"m_final_{int(datetime.utcnow().timestamp())}"
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "merchant",
            "context_id": merchant_id,
            "version": 1,
            "payload": {
                "merchant_id": merchant_id,
                "identity": {"name": "Royal Dental", "owner_first_name": "Ankur"},
                "category_slug": "dentists",
                "performance": {"ctr": 0.008}
            }
        })
        await client.post(f"{LIVE_URL}/v1/context", json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {
                "slug": "dentists",
                "peer_stats": {"avg_ctr": 0.03}
            }
        })
        print(f"[CONTEXT] Pushed merchant {merchant_id} and category.")

        # 3. Test data-driven reasoning
        resp = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": f"conv_{merchant_id}",
            "merchant_id": merchant_id,
            "message": "Vera, how is my CTR?",
            "from_role": "merchant",
            "turn_number": 1,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        data = resp.json()
        print("[DATA REASONING]", data)
        if "0.8%" in data.get('body', '') and "3.0%" in data.get('body', ''):
            print("[PASS] Data Sieve cites benchmarks.")
        else:
            print("[FAIL] Data Sieve did NOT cite benchmarks.")

        # 4. Emoji test
        resp_emoji = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": f"conv_emoji_{merchant_id}",
            "merchant_id": merchant_id,
            "message": "😊🚀📉",
            "from_role": "merchant",
            "turn_number": 1,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print("[EMOJI]", resp_emoji.json())

        # 5. Joke test
        resp_joke = await client.post(f"{LIVE_URL}/v1/reply", json={
            "conversation_id": f"conv_joke_{merchant_id}",
            "merchant_id": merchant_id,
            "message": "Tell me a joke.",
            "from_role": "merchant",
            "turn_number": 1,
            "received_at": datetime.utcnow().isoformat() + "Z"
        })
        print("[JOKE]", resp_joke.json())

if __name__ == "__main__":
    asyncio.run(run_checks())
