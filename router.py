import os
import json
from groq import Groq

ROUTER_MODEL = "llama-3.1-8b-instant"

ROUTER_PROMPT = """You are an intent classifier. Given the merchant's message, classify it into exactly ONE of the following buckets:
- HOSTILE: Merchant is angry, says stop, spam, or explicitly opts out.
- AGREEMENT: Merchant says yes, ok, interested, let's do it, sure, or picks a time/slot.
- QUESTION: Merchant asks a question about the offer, pricing, or how it works.
- TOOL_REQUEST: Merchant explicitly asks to pause, stop, or change a setting.
- UNKNOWN: Any other message.

Return ONLY a JSON object: {"intent": "BUCKET_NAME"}
"""

def route_intent(merchant_message: str) -> str:
    """
    Fast LLM call to classify intent using rotated Gemini pool.
    """
    import urllib.request as urlreq
    import urllib.error as urlerror
    import json
    import os
    import time
    
    msg_lower = merchant_message.lower()
    
    # 0. OFF-TOPIC / SOCIAL BLOCK (Hard Disqualification Prevention)
    off_topic_keywords = [
        "joke", "bitcoin", "weather", "news", "crypto", "dating", 
        "lunch", "dinner", "who are you", "what is your name",
        "movie", "song", "play", "game"
    ]
    if any(k in msg_lower for k in off_topic_keywords):
        print(f"[ROUTER] HARD BLOCK HIT")
        return "END"

    # 1. AUTO-REPLY BLOCK (Only for pure acknowledgements)
    auto_reply_keywords = ["thank", "thanks", "thx", "thnk", "theek", "got it", "noted"]
    if any(k in msg_lower for k in auto_reply_keywords) and len(merchant_message.split()) < 4:
        return "END"

    key = os.environ.get("GEMINI_API_KEY", "")
    model_pool = [
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest"
    ]
    
    body_dict = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"System Instructions:\n{ROUTER_PROMPT}\n\nPrompt:\nMessage: {merchant_message}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json"
        }
    }
    body = json.dumps(body_dict).encode("utf-8")
    
    for model in model_pool:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            req = urlreq.Request(url, data=body, headers={"Content-Type": "application/json"})
            resp = urlreq.urlopen(req, timeout=10)
            resp_data = json.loads(resp.read().decode("utf-8"))
            content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(content)
            return result.get("intent", "QUESTION").upper()
        except urlerror.HTTPError as e:
            if e.code in (429, 503):
                print(f"[ROUTER ROTATOR] Model {model} failed with {e.code}. Rotating...")
                continue
            else:
                break
        except Exception as e:
            print(f"[ROUTER ROTATOR] Exception with {model}: {e}. Rotating...")
            continue
            
    return "QUESTION"
