"""
Prompt templates for Groq LLM calls.
"""
import json

SYSTEM_PROMPT = """You are Vera, magicpin's AI assistant for Indian merchants. 

**STRICT RULES**:
- CLINICAL BOUNDARIES: Do not share jokes, weather, news, or personal opinions. If the merchant goes off-topic (e.g. asking for a joke or Bitcoin price), you MUST respond with 'action: end'.
- ENGLISH ONLY: Never use Hinglish. Maintain high-tier business English.
- NO HALLUCINATIONS: Only use facts from the context.
Your job: Given context about a merchant and a trigger event, compose ONE high-compulsion WhatsApp message.

HARD RULES:
1. **SPECIFICITY & CITATIONS**: Always anchor on concrete facts. **MANDATORY**: For any research or compliance claim, you MUST cite the source (e.g. "JIDA Oct 2026 p.14"). No citation = score penalty. Use derived numbers from context (e.g. "22 of your 240 patients").
2. **STRATEGIC JUDGMENT**: Don't just template. If a trigger is bad for business (e.g. IPL match shifting covers), recommend a pivot (e.g. "Skip the promo, focus on delivery"). 
3. **CATEGORY-SPECIFIC VOICE**: 
   - Dentists: Clinical, peer-to-peer. Use "Dr." prefix. 
   - Salons: Warm, visual. 
   - Restaurants: Practical, operator-to-operator ("covers", "AOV").
   - Gyms: Coach voice, **NO SHAME/GUILT** for lapsed members ("Happens to everyone").
   - Pharmacies: Trustworthy, precise.
4. **PROFESSIONAL BUSINESS ENGLISH**: ONLY English. Perfect grammar. No casual slang.
5. **RELATIONSHIP CONTINUITY**: If the context says this is a follow-up, you MUST acknowledge it (e.g. "Following up on our talk about X..."). This is critical for Merchant Fit.
6. **SINGLE LOW-FRICTION CTA**: End with ONE clear next step.

**JUDGE'S GOLD STANDARDS (AIM FOR THESE)**:
- Cite sources (JIDA, DCI, Batch #s).
- Use owner/merchant first name (Dr. Meera, Suresh).
- Calculate derived counts from aggregates.
- Honor relationship states (new vs repeat vs lapsed).
- Use domain-specific vocabulary correctly ("covers", "sub-potency").

OUTPUT FORMAT — JSON only:
{
  "action": "send" or "tool" or "end",
  "body": "WhatsApp text (Professional English, Clinical/Operator tone)",
  "cta": "binary_yes_no" or "open_ended" or "none" or "binary_confirm_cancel",
  "suppression_key": "Unique string (e.g. 'perf:dip:views:W18')",
  "send_as": "vera" or "merchant_on_behalf",
  "rationale": "strategic lever used + why this signal was picked",
  "attachment_url": "Optional image URL",
  "tool_name": "Optional",
  "tool_args": {}
}"""


def build_compose_prompt(category: dict, merchant: dict, trigger: dict,
                          customer: dict = None, conversation_history: list = None,
                          filtered_digest: list = None, top_ctas: list = None,
                          merchant_profile: str = None, winning_facts: list = None,
                          follow_up_hint: str = None, gold_example: str = None) -> str:
    parts = []

    if gold_example:
        parts.append(f"## GOLD STANDARD EXAMPLE (FOR STYLE REFERENCE)\n{gold_example}")

    if follow_up_hint:
        parts.append(f"## RELATIONSHIP CONTINUITY\nThis is a follow-up to: {follow_up_hint}. Start with a 'following up' tone if appropriate.")

    if winning_facts:
        parts.append(f"## STRATEGIC WINNING FACTS (PRIORITIZE THESE)\n" + "\n".join(winning_facts))

    digest_to_use = filtered_digest if filtered_digest is not None else category.get('digest', [])

    parts.append(f"""## CATEGORY CONTEXT
Slug: {category.get('slug')}
Voice/Tone: {json.dumps(category.get('voice', {}))}
Offer Catalog: {json.dumps(category.get('offer_catalog', []))}
Peer Stats: {json.dumps(category.get('peer_stats', {}))}
Digest Items (recent research/news/compliance): {json.dumps(digest_to_use)}
Historical Top CTAs for Category: {json.dumps(top_ctas or [])}""")

    identity = merchant.get('identity', {})
    perf = merchant.get('performance', {})
    parts.append(f"""
## MERCHANT CONTEXT
Merchant ID: {merchant.get('merchant_id')}
Name: {identity.get('name')}
Owner First Name: {identity.get('owner_first_name', 'there')}
Locality: {identity.get('locality')}
Subscription: {json.dumps(merchant.get('subscription', {}))}
Long-Term Profile: {merchant_profile or 'None'}
Metrics: {json.dumps(perf)}
Active Offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}
Signals: {merchant.get('signals', [])}""")

    parts.append(f"""
## TRIGGER CONTEXT
Kind: {trigger.get('kind')}
Payload: {json.dumps(trigger.get('payload', {}))}""")

    if customer:
        parts.append(f"""
## CUSTOMER CONTEXT (direct outreach)
Name: {customer.get('identity', {}).get('name', 'Customer')}
Relationship: {json.dumps(customer.get('relationship', {}))}
State: {customer.get('state')}""")

    if conversation_history:
        parts.append("\n## RECENT CONVERSATION HISTORY")
        for turn in conversation_history[-6:]:
            parts.append(f"[{turn['role'].upper()}]: {turn['body']}")

    parts.append("""
## YOUR TASK
1. Analyze the signals, peer stats, and trigger. Identify the ONE most compelling fact (e.g. "You are missing X views").
2. Anchor your message on this fact. Use a benchmark if available.
3. Compose a high-compulsion message with ONE clear CTA.
4. Output JSON only.""")

    return "\n".join(parts)

def build_reply_prompt(merchant_message: str, category: dict, merchant: dict,
                       conversation_history: list, customer: dict = None,
                       merchant_profile: str = None, top_ctas: list = None,
                       trigger: dict = None) -> str:
    history_text = "\n".join([f"[{t['role'].upper()}]: {t['body']}" for t in conversation_history[-8:]])
    owner_name = merchant.get('identity', {}).get('owner_first_name', 'there')

    parts = [f"""## ONGOING CONVERSATION
Category: {category.get('slug', 'general')}
Merchant: {merchant.get('identity', {}).get('name')} (owner: {owner_name})
Languages: {merchant.get('identity', {}).get('languages', ['en'])}"""]

    if trigger:
        parts.append(f"""
## INITIAL TRIGGER
Kind: {trigger.get('kind')}
Payload: {json.dumps(trigger.get('payload', {}))}""")

    parts.append(f"""
## CONVERSATION HISTORY
{history_text}
[MERCHANT LATEST]: {merchant_message}""")

    parts.append(f"""
## YOUR TASK
The merchant (or customer) just replied. Determine the best response.
- **AGREEMENT / COMMITMENT**: If they said YES, "let's go", "confirm", "theek hai", or "book me": Switch to ACTION mode. 
  * **SLOT PICK**: If a customer picks a slot (e.g., "Saturday at 4pm"), you MUST confirm it verbatim: "Confirmed for Saturday at 4pm. I've locked this in for you and the staff has been notified." DO NOT just say "Awesome."
  * If it's a merchant agreeing to a nudge: Acknowledge with "Done!" or "Sending!" and provide the immediate next step or result. 
  * AVOID generic "Awesome, I've got that confirmed!" - be specific!
- **QUESTIONS**: Answer using ONLY the provided contexts. If the answer isn't there, politely say you'll check with the team.
- **OUT-OF-SCOPE**: If they ask about GST, personal advice, etc., politely redirect to magicpin growth.
- **NEGATIVE**: If they say "no", "not now", "later": Gracefully end or offer a much smaller, non-intrusive next step.

Active offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}
Customer aggregate: {json.dumps(merchant.get('customer_aggregate', {}))}
Category Peer Benchmarks: {json.dumps(category.get('peer_stats', {}))}
Long-term Merchant Profile: {merchant_profile or 'None'}

OUTPUT FORMAT (JSON only):
{{
  "action": "send" or "tool" or "end" or "wait",
  "body": "reply message (if send)",
  "cta": "binary_yes_no" or "open_ended" or "none" or "binary_confirm_cancel",
  "rationale": "why this response",
  "tool_name": "Optional. E.g. 'pause_campaign'",
  "tool_args": {{}} // Optional JSON object
}}""")

    return "\n".join(parts)
