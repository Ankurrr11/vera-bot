"""
Prompt templates for Groq LLM calls.
"""
import json

SYSTEM_PROMPT = """You are Vera, magicpin's AI assistant for Indian merchants on WhatsApp.

Your job: Given context about a merchant and a trigger event, compose ONE high-compulsion WhatsApp message.

HARD RULES:
1. Use ONLY facts from the context provided. Never invent numbers, competitors, or research citations.
2. One clear CTA only — binary YES/STOP, open-ended question, or none for pure information.
3. NO URLs in the message body ever.
4. Keep it short and conversational. No long preambles.
5. Match the merchant's language preference. Hindi-English mix is preferred for most Indian merchants.
6. Use the owner's first name, not the clinic/shop name.
7. Never say "guaranteed", "100% safe", "best in city", or make medical claims.
8. Voice must match the category:
   - Dentists: peer/clinical tone, source citations welcome
   - Salons: warm, visual, aspirational
   - Restaurants: operator-to-operator, food-first
   - Gyms: coach voice, motivational but data-grounded
   - Pharmacies: trustworthy, precise, respectful

OUTPUT FORMAT — JSON only, no markdown, no explanation outside JSON:
{
  "body": "the WhatsApp message text",
  "cta": "binary_yes_no" or "open_ended" or "none" or "binary_confirm_cancel" or "multi_choice_slot",
  "send_as": "vera" or "merchant_on_behalf",
  "rationale": "1-2 sentences: why this message, what compulsion lever used",
  "attachment_url": "Optional. Add a mock magicpin image URL (e.g. https://magicpin.com/assets/chart_123.png) ONLY if a chart or image adds high compulsion."
}"""


def build_compose_prompt(category: dict, merchant: dict, trigger: dict,
                          customer: dict = None, conversation_history: list = None,
                          filtered_digest: list = None) -> str:
    parts = []

    digest_to_use = filtered_digest if filtered_digest is not None else category.get('digest', [])

    parts.append(f"""## CATEGORY CONTEXT
Slug: {category.get('slug')}
Voice/Tone: {json.dumps(category.get('voice', {}))}
Offer Catalog: {json.dumps(category.get('offer_catalog', []))}
Peer Stats: {json.dumps(category.get('peer_stats', {}))}
Digest Items (recent research/news/compliance): {json.dumps(digest_to_use)}
Seasonal Beats: {json.dumps(category.get('seasonal_beats', []))}
Trend Signals: {json.dumps(category.get('trend_signals', []))}""")

    identity = merchant.get('identity', {})
    perf = merchant.get('performance', {})
    parts.append(f"""
## MERCHANT CONTEXT
Merchant ID: {merchant.get('merchant_id')}
Name: {identity.get('name')}
Owner First Name: {identity.get('owner_first_name', 'there')}
City: {identity.get('city')} | Locality: {identity.get('locality')}
Languages: {identity.get('languages', ['en'])}
Subscription: {json.dumps(merchant.get('subscription', {}))}
Performance (30d): views={perf.get('views')}, calls={perf.get('calls')}, directions={perf.get('directions')}, CTR={perf.get('ctr')} vs peer avg CTR={category.get('peer_stats', {}).get('avg_ctr', 'unknown')}
7d deltas: {json.dumps(perf.get('delta_7d', {}))}
Active Offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}
Customer Aggregate: {json.dumps(merchant.get('customer_aggregate', {}))}
Signals: {merchant.get('signals', [])}
Review Themes: {json.dumps(merchant.get('review_themes', []))}""")

    parts.append(f"""
## TRIGGER CONTEXT
Trigger ID: {trigger.get('id')}
Kind: {trigger.get('kind')}
Scope: {trigger.get('scope')}
Source: {trigger.get('source')}
Urgency: {trigger.get('urgency')} (1=low, 5=critical)
Suppression Key: {trigger.get('suppression_key')}
Payload: {json.dumps(trigger.get('payload', {}))}
Expires: {trigger.get('expires_at')}""")

    if customer:
        parts.append(f"""
## CUSTOMER CONTEXT (send_as = merchant_on_behalf)
Customer ID: {customer.get('customer_id')}
Name: {customer.get('identity', {}).get('name', 'Customer')}
Language Preference: {customer.get('identity', {}).get('language_pref', 'en')}
Relationship: {json.dumps(customer.get('relationship', {}))}
State: {customer.get('state')}
Preferences: {json.dumps(customer.get('preferences', {}))}
Consent Scope: {json.dumps(customer.get('consent', {}).get('scope', []))}""")

    if conversation_history:
        parts.append("\n## RECENT CONVERSATION HISTORY")
        for turn in conversation_history[-6:]:
            parts.append(f"[{turn['role'].upper()}]: {turn['body']}")

    parts.append("""
## YOUR TASK
Compose the next Vera message. Pick the ONE most compelling signal from trigger + merchant state.
Use a specific verifiable fact. No generic offers. Output JSON only.""")

    return "\n".join(parts)


def build_reply_prompt(merchant_message: str, conversation_history: list,
                        category: dict, merchant: dict, customer: dict = None) -> str:
    history_text = "\n".join([f"[{t['role'].upper()}]: {t['body']}" for t in conversation_history[-8:]])
    owner_name = merchant.get('identity', {}).get('owner_first_name', 'there')

    return f"""## ONGOING CONVERSATION
Category: {category.get('slug', 'general')}
Merchant: {merchant.get('identity', {}).get('name')} (owner: {owner_name})
Languages: {merchant.get('identity', {}).get('languages', ['en'])}

## CONVERSATION HISTORY
{history_text}
[MERCHANT LATEST]: {merchant_message}

## YOUR TASK
The merchant just replied. Determine the best response.
- If merchant said YES / let's go / go ahead / confirm: switch to ACTION mode immediately. Use explicit action words like "done", "sending", "draft", "confirm", "proceed", or "next" in your reply, and do NOT ask more qualifying questions (like "do you", "would you").
- If out-of-scope question: politely decline and redirect back to the topic.
- Otherwise: respond naturally and move forward.

Active offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}
Customer aggregate: {json.dumps(merchant.get('customer_aggregate', {}))}

OUTPUT FORMAT (JSON only):
{{
  "action": "send",
  "body": "reply message",
  "cta": "binary_yes_no" or "open_ended" or "none" or "binary_confirm_cancel",
  "rationale": "why this response"
}}"""
