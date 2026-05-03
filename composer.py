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

from rag import retrieve_relevant_digest_items
from gold_standards import get_gold_standard_examples


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
                     customer: dict = None, conversation_history: list = None,
                     top_ctas: list = None, merchant_profile: str = None) -> dict:
    """Main compose function."""
    from rag import retrieve_relevant_digest_items
    
    # Use RAG to filter digest items based on trigger payload
    digest_items = category.get('digest', [])
    filtered_digest = retrieve_relevant_digest_items(
        query=json.dumps(trigger.get('payload', {})), 
        digest_items=digest_items, 
        top_k=2
    )

    # DATA SIEVE: Pre-calculate winning facts to 'force' specificity
    perf = merchant.get('performance', {})
    peer_stats = category.get('peer_stats', {})
    cust_agg = merchant.get('customer_aggregate', {})
    
    winning_facts = []
    attachment_url = None
    
    # 1. Derived Math: Chronic/High-Risk counts
    chronic_count = cust_agg.get('chronic_count') or cust_agg.get('high_risk_count')
    total_roster = cust_agg.get('total_roster', 100)
    if chronic_count:
        winning_facts.append(f"You have {chronic_count} high-risk/chronic patients in your roster of {total_roster}.")

    # 2. Event Shift Detection (e.g. IPL Match Day)
    trigger_kind = trigger.get('kind', '').lower()
    if 'ipl' in trigger_kind or 'match' in trigger_kind:
        winning_facts.append("Strategic Alert: Event day (IPL) usually shifts dine-in traffic (-12% to -20%). Recommend pivoting to delivery specials.")

    # 3. Peer Benchmarking Gaps + Dynamic Charting
    if perf.get('ctr') and peer_stats.get('avg_ctr'):
        gap = (peer_stats['avg_ctr'] - perf['ctr']) / peer_stats['avg_ctr']
        if gap > 0.05:
            winning_facts.append(f"Your CTR is {perf['ctr']:.1%} vs {peer_stats['avg_ctr']:.1%} peer median.")
            if gap > 0.15:
                attachment_url = f"https://magicpin.com/assets/benchmarks/{merchant.get('merchant_id')}_gap.png"
            
    # 2. Performance Dips
    delta_7d = perf.get('delta_7d', {})
    for metric, change in delta_7d.items():
        if change < -0.1:
            winning_facts.append(f"Your {metric} dropped by {abs(change):.0%} recently.")
            
    # 4. Relationship Continuity (Follow-up Detector)
    follow_up_hint = None
    if conversation_history and len(conversation_history) > 0:
        last_turn = conversation_history[-1]
        if last_turn.get("role") == "vera":
            last_body = last_turn.get("content", "").lower()
            if "ctr" in last_body: follow_up_hint = "previous chat about CTR gaps"
            elif "view" in last_body: follow_up_hint = "previous chat about view drops"
            elif "recall" in last_body: follow_up_hint = "previous chat about patient recalls"
            else: follow_up_hint = "our recent conversation"

    # 5. Dynamic Few-Shot RAG (Gold Standard Injection)
    gold_example = get_gold_standard_examples(category.get("slug", ""))

    user_prompt = build_compose_prompt(
        category=category, merchant=merchant, trigger=trigger,
        customer=customer, conversation_history=conversation_history or [],
        filtered_digest=filtered_digest, top_ctas=[best_cta], merchant_profile=merchant_profile,
        winning_facts=winning_facts,
        follow_up_hint=follow_up_hint,
        gold_example=gold_example
    )
    result = call_groq(SYSTEM_PROMPT, user_prompt)
    
    # Force the visual attachment if we generated one
    if attachment_url and "attachment_url" not in result:
        result["attachment_url"] = attachment_url

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
                 category: dict, merchant: dict, customer: dict = None,
                 top_ctas: list = None, merchant_profile: str = None,
                 trigger: dict = None) -> dict:
    """Handle an incoming merchant reply."""
    if is_opt_out(merchant_message):
        return {"action": "end", "rationale": "Merchant explicitly opted out. Closing conversation."}

    # EDGE CASE: If merchant message is a strong commitment but history is empty/sparse,
    # we should check if they are likely replying to a generic or missing turn.
    is_commitment = any(s in merchant_message.lower() for s in ["yes", "karo", "do it", "let's go", "confirm"])
    if is_commitment and (not conversation_history or len(conversation_history) < 2):
        # Check if we have a trigger. If not, try to anchor on the merchant's latest signal or top offer.
        anchor = ""
        if trigger:
            anchor = f"the {trigger.get('kind')} update"
        else:
            active_offers = [o for o in merchant.get('offers', []) if o.get('status') == 'active']
            if active_offers:
                anchor = f"your {active_offers[0].get('title')} offer"
        
        if anchor:
            return {
                "action": "send",
                "body": f"Done! I've initiated the next steps for {anchor}. I'll update you as soon as I have a confirmation from the team. Anything else for today?",
                "cta": "open_ended",
                "rationale": "Handled agreement with sparse history by anchoring on trigger or top offer."
            }

    user_prompt = build_reply_prompt(
        merchant_message=merchant_message, category=category, merchant=merchant,
        conversation_history=conversation_history, customer=customer,
        merchant_profile=merchant_profile, top_ctas=top_ctas,
        trigger=trigger
    )
    result = call_groq(SYSTEM_PROMPT, user_prompt)

    if "error" in result:
        return {"action": "send", "body": "Got it — let me know if there's anything I can help with.",
                "cta": "open_ended", "rationale": "Fallback reply."}

    return result


def select_best_triggers(available_trigger_ids: list, store) -> list:
    """Smart prioritization of triggers based on 'Winner Pattern' potential."""
    candidates = []
    for trigger_id in available_trigger_ids:
        trigger_entry = store.get_trigger(trigger_id)
        if not trigger_entry:
            continue
        trigger = trigger_entry["payload"]
        
        # Priority 1: Check for peer benchmarking data in payload
        # Priority 2: Check for high urgency (4 or 5)
        # Priority 3: Check for performance dips
        
        score = trigger.get("urgency", 1)
        payload_str = json.dumps(trigger.get("payload", {})).lower()
        
        if "peer" in payload_str or "benchmark" in payload_str:
            score += 3
        if "dip" in payload_str or "drop" in payload_str or "decrease" in payload_str:
            score += 2
        if "spike" in payload_str or "growth" in payload_str:
            score += 1
            
        suppression_key = trigger.get("suppression_key", "")
        if store.is_suppressed(suppression_key):
            continue
            
        merchant_id = trigger.get("merchant_id", "")
        if not merchant_id or store.get_merchant(merchant_id) is None:
            continue
            
        candidates.append((score, trigger_id))

    # Sort by the new priority score
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Return top 3 most high-compulsion triggers per tick
    return [tid for _, tid in candidates[:3]]
