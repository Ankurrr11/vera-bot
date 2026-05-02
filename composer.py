"""
Core composition logic. Calls Groq LLM to generate messages.
"""
import json
import os
from groq import Groq
from prompts import SYSTEM_PROMPT, build_compose_prompt, build_reply_prompt
from auto_reply import is_auto_reply, is_opt_out

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def call_groq(system: str, user: str) -> dict:
    """Call Groq API and return parsed JSON response."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"error": str(e)}


def compose_message(category: dict, merchant: dict, trigger: dict,
                     customer: dict = None, conversation_history: list = None) -> dict:
    """Main compose function."""
    from rag import retrieve_relevant_digest_items
    
    # Use RAG to filter digest items based on trigger payload
    digest_items = category.get('digest', [])
    filtered_digest = retrieve_relevant_digest_items(
        query=json.dumps(trigger.get('payload', {})), 
        digest_items=digest_items, 
        top_k=2
    )

    user_prompt = build_compose_prompt(
        category=category, merchant=merchant, trigger=trigger,
        customer=customer, conversation_history=conversation_history or [],
        filtered_digest=filtered_digest
    )
    result = call_groq(SYSTEM_PROMPT, user_prompt)

    if "error" in result:
        owner = merchant.get('identity', {}).get('owner_first_name', 'there')
        return {
            "body": f"Hi {owner}, quick update on your magicpin profile — want me to run a check?",
            "cta": "binary_yes_no", "send_as": "vera",
            "rationale": "Fallback message due to composition error."
        }

    if customer:
        result["send_as"] = "merchant_on_behalf"
    else:
        result["send_as"] = "vera"

    return result


def handle_reply(merchant_message: str, conversation_history: list,
                  category: dict, merchant: dict, customer: dict = None) -> dict:
    """Handle an incoming merchant reply."""
    if is_opt_out(merchant_message):
        return {"action": "end", "rationale": "Merchant explicitly opted out. Closing conversation."}

    if is_auto_reply(merchant_message):
        return {"action": "wait", "wait_seconds": 14400,
                "rationale": "Detected auto-reply. Backing off 4 hours to wait for owner."}

    user_prompt = build_reply_prompt(
        merchant_message=merchant_message, conversation_history=conversation_history,
        category=category, merchant=merchant, customer=customer
    )
    result = call_groq(SYSTEM_PROMPT, user_prompt)

    if "error" in result:
        return {"action": "send", "body": "Got it — let me know if there's anything I can help with.",
                "cta": "open_ended", "rationale": "Fallback reply."}

    return result


def select_best_triggers(available_trigger_ids: list, store) -> list:
    """Select which triggers to act on this tick using smart prioritization."""
    candidates = []
    for trigger_id in available_trigger_ids:
        trigger_entry = store.get_trigger(trigger_id)
        if not trigger_entry:
            continue
        trigger = trigger_entry["payload"]
        suppression_key = trigger.get("suppression_key", "")
        if store.is_suppressed(suppression_key):
            continue
        merchant_id = trigger.get("merchant_id", "")
        if not merchant_id or store.get_merchant(merchant_id) is None:
            continue
        conv_id = f"conv_{merchant_id}_{trigger.get('kind', 'msg')}_{trigger_id[-8:]}"
        if store.is_closed(conv_id):
            continue
        candidates.append((trigger.get("urgency", 1), trigger_id, trigger))

    # Pre-filter by highest urgency first
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidates[:5]

    # For hackathon/demo purposes, we can invoke a fast LLM to rank the top 5
    # Since we want to keep latency low, we'll just return the pre-filtered top ones
    # But if we had exactly 1 slot, we could use the LLM here to pick the absolute best.
    # We will return the top 5 directly to process them.
    return [tid for _, tid, _ in top_candidates]
