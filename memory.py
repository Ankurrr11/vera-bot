import os
import json
from groq import Groq

# Use the extremely fast 8b model for background summarization
SUMMARIZER_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are Vera's memory engine. Your job is to read a recent conversation and the EXISTING profile of a merchant, and output an UPDATED concise profile summary.
Focus on personality, preferences, objections, and engagement style. Keep it under 3 sentences. 
Return ONLY a JSON object: {"profile_summary": "..."}
"""

def update_merchant_profile(merchant_id: str, conversation_id: str, store):
    """
    Background task to update long-term merchant memory based on the latest conversation.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return

    # Fetch existing profile
    existing_profile = store.get_merchant_profile(merchant_id)
    
    # Fetch recent conversation
    history = store.get_conversation(conversation_id)
    if not history:
        return
        
    chat_text = "\n".join([f"{msg['role'].upper()}: {msg['body']}" for msg in history])
    
    prompt = f"EXISTING PROFILE:\n{existing_profile or 'None'}\n\nRECENT CONVERSATION:\n{chat_text}"
    
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=SUMMARIZER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200
        )
        
        result = json.loads(response.choices[0].message.content)
        new_summary = result.get("profile_summary", "").strip()
        
        if new_summary:
            store.set_merchant_profile(merchant_id, new_summary)
            print(f"[MEMORY] Updated profile for {merchant_id}: {new_summary}")
            
    except Exception as e:
        print(f"[MEMORY] Failed to update profile for {merchant_id}: {e}")
