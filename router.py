import os
import json
from groq import Groq

ROUTER_MODEL = "llama-3.1-8b-instant"

ROUTER_PROMPT = """You are an intent classifier. Given the merchant's message, classify it into exactly ONE of the following buckets:
- HOSTILE: Merchant is angry, says stop, spam, or explicitly opts out.
- AGREEMENT: Merchant says yes, ok, interested, let's do it, sure.
- QUESTION: Merchant asks a question about the offer, pricing, or how it works.
- NEGOTIATION: Merchant wants a better deal or suggests different terms.
- TOOL_REQUEST: Merchant explicitly asks to pause, stop, or change a setting (e.g. "pause my campaign", "update my discount").
- OUT_OF_SCOPE: Merchant is asking for jokes, weather, news, personal info, or anything not related to their business growth on magicpin.

Return ONLY a JSON object: {"intent": "BUCKET_NAME"}
"""

def route_intent(merchant_message: str) -> str:
    """
    Fast LLM call to classify intent and potentially skip the heavy 70B model.
    """
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return "QUESTION" # default fallback
        
    msg_lower = merchant_message.lower()
    
    # 0. OFF-TOPIC / SOCIAL BLOCK (Hard Disqualification Prevention)
    off_topic_keywords = [
        "joke", "bitcoin", "weather", "news", "crypto", "dating", 
        "lunch", "dinner", "who are you", "what is your name",
        "movie", "song", "play", "game"
    ]
    if any(k in msg_lower for k in off_topic_keywords):
        print(f"[ROUTER] HARD BLOCK HIT: {merchant_message}")
        return "END"

    # 1. AUTO-REPLY BLOCK
    auto_reply_keywords = ["thank", "thanks", "ok", "okay", "thx", "thnk", "theek", "got it", "noted"]
    if any(k in msg_lower for k in auto_reply_keywords) and len(merchant_message.split()) < 4:
        return "END"

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=ROUTER_MODEL,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": f"Message: {merchant_message}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=30
        )
        
        result = json.loads(response.choices[0].message.content)
        intent = result.get("intent", "QUESTION").upper()
        return "END" if intent == "OUT_OF_SCOPE" else intent
    except Exception as e:
        print(f"[ROUTER] Failed to route: {e}")
        return "QUESTION"
