# VERA BOT — COMPLETE BUILD INSTRUCTIONS FOR ANTIGRAVITY

Read this entire file before writing a single line of code. This is your complete spec.

---

## WHAT YOU ARE BUILDING

A Python HTTP server (FastAPI) that acts as a smart message-composing AI bot for magicpin's Vera product. The bot receives merchant data, reads it intelligently, and generates high-quality WhatsApp messages for Indian merchants (dentists, salons, restaurants, gyms, pharmacies).

The bot will be tested by magicpin's automated judge system which will call your API endpoints, send you merchant context, and score your message quality.

**Prize if this wins: a full-time job at magicpin in Gurgaon.**

---

## FOLDER STRUCTURE YOU ARE WORKING IN

This folder already contains the challenge dataset:
```
vera-bot-complete/
├── ANTIGRAVITY_MASTER_PROMPT.md     ← this file
├── challenge-brief.md               ← full challenge spec, READ THIS
├── challenge-testing-brief.md       ← API contract, READ THIS
├── engagement-design.md             ← engagement patterns
├── engagement-research.md           ← research on what works
├── judge_simulator.py               ← local test harness
├── dataset/
│   ├── categories/
│   │   ├── dentists.json
│   │   ├── salons.json
│   │   ├── restaurants.json
│   │   ├── gyms.json
│   │   └── pharmacies.json
│   ├── merchants_seed.json
│   ├── customers_seed.json
│   ├── triggers_seed.json
│   └── generate_dataset.py
└── examples/
    ├── api-call-examples.md
    └── case-studies.md
```

## FILES YOU MUST CREATE (inside this same folder)

```
vera-bot-complete/
├── main.py              ← FastAPI app with all 5 endpoints
├── composer.py          ← The brain — reads context, calls Groq, returns message
├── state.py             ← In-memory state store
├── auto_reply.py        ← Auto-reply detection
├── prompts.py           ← LLM prompt templates
├── requirements.txt     ← Dependencies
├── .env                 ← API keys
└── README.md            ← One-page description
```

---

## TECH STACK

- Python 3.11+
- FastAPI (web framework)
- Uvicorn (server)
- Groq API (FREE LLM — use `llama-3.3-70b-versatile` model)
- python-dotenv (for env vars)

No database needed. Store everything in memory (Python dicts).

---

## STEP 1 — CREATE requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
groq==0.9.0
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.7.1
```

---

## STEP 2 — CREATE .env

```
GROQ_API_KEY=FILL_IN_FROM_GROQ_CONSOLE
BOT_VERSION=1.0.0
TEAM_NAME=Ankur Kumar
CONTACT_EMAIL=your@email.com
```

**To get Groq API key**: Go to https://console.groq.com, sign up with Google (free, no credit card), go to API Keys, create new key. Paste it above.

---

## STEP 3 — CREATE state.py

```python
"""
In-memory state store. Holds all context pushed by the judge.
Never restarts between requests — this is critical.
"""
from datetime import datetime
from typing import Optional


class StateStore:
    def __init__(self):
        self.categories: dict = {}
        self.merchants: dict = {}
        self.customers: dict = {}
        self.triggers: dict = {}
        self.conversations: dict = {}
        self.suppressions: dict = {}
        self.closed_conversations: set = set()
        self.auto_reply_counts: dict = {}
        self.started_at: datetime = datetime.utcnow()

    def store_context(self, scope: str, context_id: str, version: int, payload: dict, delivered_at: str) -> dict:
        store = self._get_store(scope)
        existing = store.get(context_id)
        if existing:
            if existing["version"] == version:
                return {"accepted": True, "ack_id": f"ack_{context_id}_v{version}_noop", "stored_at": existing["stored_at"]}
            if existing["version"] > version:
                return {"accepted": False, "reason": "stale_version", "current_version": existing["version"]}
        stored_at = datetime.utcnow().isoformat() + "Z"
        store[context_id] = {"version": version, "payload": payload, "stored_at": stored_at, "delivered_at": delivered_at}
        return {"accepted": True, "ack_id": f"ack_{context_id}_v{version}", "stored_at": stored_at}

    def _get_store(self, scope: str) -> dict:
        return {"category": self.categories, "merchant": self.merchants, "customer": self.customers, "trigger": self.triggers}[scope]

    def get_context(self, scope: str, context_id: str) -> Optional[dict]:
        store = self._get_store(scope)
        entry = store.get(context_id)
        return entry["payload"] if entry else None

    def add_conversation_turn(self, conversation_id: str, role: str, body: str):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append({"role": role, "body": body, "ts": datetime.utcnow().isoformat() + "Z"})

    def get_conversation(self, conversation_id: str) -> list:
        return self.conversations.get(conversation_id, [])

    def suppress(self, key: str):
        self.suppressions[key] = datetime.utcnow().isoformat() + "Z"

    def is_suppressed(self, key: str) -> bool:
        return key in self.suppressions

    def close_conversation(self, conversation_id: str):
        self.closed_conversations.add(conversation_id)

    def is_closed(self, conversation_id: str) -> bool:
        return conversation_id in self.closed_conversations

    def get_counts(self) -> dict:
        return {"category": len(self.categories), "merchant": len(self.merchants), "customer": len(self.customers), "trigger": len(self.triggers)}

    def uptime_seconds(self) -> int:
        return int((datetime.utcnow() - self.started_at).total_seconds())


store = StateStore()
```

---

## STEP 4 — CREATE auto_reply.py

```python
"""
Detect WhatsApp Business auto-replies and merchant intent signals.
"""

AUTO_REPLY_PATTERNS = [
    "thank you for contacting",
    "our team will respond",
    "we will get back to you",
    "automated response",
    "i am currently unavailable",
    "this is an automated message",
    "aapki jaankari ke liye bahut-bahut shukriya",
    "main aapki yeh sabhi baatein",
    "main ek automated assistant hoon",
    "we are currently closed",
    "outside of our business hours",
    "your message has been received",
]

OPT_OUT_SIGNALS = [
    "stop messaging", "stop sending", "not interested", "do not contact",
    "remove me", "unsubscribe", "band karo", "mat bhejo", "nahi chahiye",
    "disturb mat karo", "why are you bothering", "useless", "spam",
]

ACTION_SIGNALS = [
    "yes", "haan", "ha ", "ok let", "let's do", "lets do",
    "go ahead", "please proceed", "karo", "kar do", "theek hai",
    "sure", "confirm", "agreed", "sounds good", "mujhe join",
    "judrna hai", "i want to join",
]


def is_auto_reply(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(p in msg_lower for p in AUTO_REPLY_PATTERNS)


def is_opt_out(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(s in msg_lower for s in OPT_OUT_SIGNALS)


def is_intent_to_act(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(s in msg_lower for s in ACTION_SIGNALS)
```

---

## STEP 5 — CREATE prompts.py

```python
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
  "rationale": "1-2 sentences: why this message, what compulsion lever used"
}"""


def build_compose_prompt(category: dict, merchant: dict, trigger: dict,
                          customer: dict = None, conversation_history: list = None) -> str:
    parts = []

    parts.append(f"""## CATEGORY CONTEXT
Slug: {category.get('slug')}
Voice/Tone: {json.dumps(category.get('voice', {}))}
Offer Catalog: {json.dumps(category.get('offer_catalog', []))}
Peer Stats: {json.dumps(category.get('peer_stats', {}))}
Digest Items (recent research/news/compliance): {json.dumps(category.get('digest', []))}
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
- If merchant said YES / let's go / go ahead / confirm: switch to ACTION mode immediately. Draft the thing, do NOT ask more qualifying questions.
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
```

---

## STEP 6 — CREATE composer.py

```python
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
    user_prompt = build_compose_prompt(
        category=category, merchant=merchant, trigger=trigger,
        customer=customer, conversation_history=conversation_history or []
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


def select_best_triggers(available_trigger_ids: list, triggers_store: dict,
                          merchants_store: dict, suppressions: dict,
                          closed_conversations: set) -> list:
    """Select which triggers to act on this tick. Returns list of trigger IDs."""
    candidates = []
    for trigger_id in available_trigger_ids:
        trigger_entry = triggers_store.get(trigger_id)
        if not trigger_entry:
            continue
        trigger = trigger_entry["payload"]
        suppression_key = trigger.get("suppression_key", "")
        if suppression_key in suppressions:
            continue
        merchant_id = trigger.get("merchant_id", "")
        if not merchant_id or merchant_id not in merchants_store:
            continue
        conv_id = f"conv_{merchant_id}_{trigger.get('kind', 'msg')}_{trigger_id[-8:]}"
        if conv_id in closed_conversations:
            continue
        candidates.append((trigger.get("urgency", 1), trigger_id))

    candidates.sort(reverse=True)
    return [tid for _, tid in candidates[:20]]
```

---

## STEP 7 — CREATE main.py

```python
"""
FastAPI server — all 5 required endpoints for the magicpin judge.
"""
import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from state import store
from composer import compose_message, handle_reply, select_best_triggers
from auto_reply import is_auto_reply

app = FastAPI(title="Vera Bot", version=os.getenv("BOT_VERSION", "1.0.0"))


# ── MODELS ──────────────────────────────────────────────────────────────────

class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict
    delivered_at: Optional[str] = None

class TickRequest(BaseModel):
    now: str
    available_triggers: list[str]

class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


# ── ENDPOINT 1: GET /v1/healthz ─────────────────────────────────────────────

@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": store.uptime_seconds(),
        "contexts_loaded": store.get_counts()
    }


# ── ENDPOINT 2: GET /v1/metadata ────────────────────────────────────────────

@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": os.getenv("TEAM_NAME", "Ankur Kumar"),
        "team_members": [os.getenv("TEAM_NAME", "Ankur Kumar")],
        "model": "llama-3.3-70b-versatile (Groq)",
        "approach": "Single-prompt composer with trigger-kind dispatch. In-memory state with version control. Rule-based auto-reply detection. Groq Llama 3.3 70B at temperature=0.",
        "contact_email": os.getenv("CONTACT_EMAIL", ""),
        "version": os.getenv("BOT_VERSION", "1.0.0"),
        "submitted_at": datetime.utcnow().isoformat() + "Z"
    }


# ── ENDPOINT 3: POST /v1/context ────────────────────────────────────────────

@app.post("/v1/context")
def receive_context(req: ContextRequest):
    valid_scopes = {"category", "merchant", "customer", "trigger"}
    if req.scope not in valid_scopes:
        return {"accepted": False, "reason": "invalid_scope", "details": f"must be one of {valid_scopes}"}

    result = store.store_context(
        scope=req.scope, context_id=req.context_id, version=req.version,
        payload=req.payload, delivered_at=req.delivered_at or datetime.utcnow().isoformat() + "Z"
    )

    if not result["accepted"] and result.get("reason") == "stale_version":
        return JSONResponse(status_code=409, content=result)

    return result


# ── ENDPOINT 4: POST /v1/tick ────────────────────────────────────────────────

@app.post("/v1/tick")
def tick(req: TickRequest):
    if not req.available_triggers:
        return {"actions": []}

    trigger_ids = select_best_triggers(
        available_trigger_ids=req.available_triggers,
        triggers_store=store.triggers,
        merchants_store=store.merchants,
        suppressions=store.suppressions,
        closed_conversations=store.closed_conversations
    )

    if not trigger_ids:
        return {"actions": []}

    actions = []

    for trigger_id in trigger_ids:
        trigger_entry = store.triggers.get(trigger_id)
        if not trigger_entry:
            continue
        trigger = trigger_entry["payload"]

        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")

        merchant_entry = store.merchants.get(merchant_id)
        if not merchant_entry:
            continue
        merchant = merchant_entry["payload"]

        category_slug = merchant.get("category_slug")
        category_entry = store.categories.get(category_slug)
        if not category_entry:
            continue
        category = category_entry["payload"]

        customer = None
        if customer_id:
            customer_entry = store.customers.get(customer_id)
            if customer_entry:
                customer = customer_entry["payload"]

        conversation_id = f"conv_{merchant_id}_{trigger.get('kind', 'msg')}_{trigger_id[-8:]}"
        conv_history = store.get_conversation(conversation_id)

        composed = compose_message(
            category=category, merchant=merchant, trigger=trigger,
            customer=customer, conversation_history=conv_history
        )

        store.add_conversation_turn(conversation_id, "vera", composed.get("body", ""))
        suppression_key = trigger.get("suppression_key", f"sent:{trigger_id}")
        store.suppress(suppression_key)

        identity = merchant.get("identity", {})
        template_params = []
        if customer:
            template_params.append(customer.get("identity", {}).get("name", "Customer"))
        else:
            template_params.append(identity.get("owner_first_name", identity.get("name", "there")))
        template_params.append(identity.get("name", ""))

        actions.append({
            "conversation_id": conversation_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": composed.get("send_as", "vera"),
            "trigger_id": trigger_id,
            "template_name": f"vera_{trigger.get('kind', 'generic')}_v1",
            "template_params": template_params,
            "body": composed.get("body", ""),
            "cta": composed.get("cta", "open_ended"),
            "suppression_key": suppression_key,
            "rationale": composed.get("rationale", "")
        })

    return {"actions": actions}


# ── ENDPOINT 5: POST /v1/reply ───────────────────────────────────────────────

@app.post("/v1/reply")
def reply(req: ReplyRequest):
    if store.is_closed(req.conversation_id):
        return {"action": "end", "rationale": "Conversation already closed."}

    store.add_conversation_turn(req.conversation_id, "merchant", req.message)

    if is_auto_reply(req.message):
        count = store.auto_reply_counts.get(req.conversation_id, 0) + 1
        store.auto_reply_counts[req.conversation_id] = count
        if count >= 3:
            store.close_conversation(req.conversation_id)
            return {"action": "end", "rationale": f"Auto-reply {count}x in a row. Closing conversation."}
        elif count == 2:
            return {"action": "wait", "wait_seconds": 86400, "rationale": "Auto-reply twice. Waiting 24h."}
        else:
            return {"action": "send", "body": "Looks like an auto-reply 😊 When you see this, just reply YES to continue.",
                    "cta": "binary_yes_no", "rationale": "First auto-reply detected. Flagging for owner."}
    else:
        store.auto_reply_counts[req.conversation_id] = 0

    merchant_entry = store.merchants.get(req.merchant_id)
    if not merchant_entry:
        return {"action": "send", "body": "Thanks for your reply! How can I help?",
                "cta": "open_ended", "rationale": "Merchant context not found."}
    merchant = merchant_entry["payload"]

    category_entry = store.categories.get(merchant.get("category_slug"))
    category = category_entry["payload"] if category_entry else {}

    customer = None
    if req.customer_id:
        customer_entry = store.customers.get(req.customer_id)
        if customer_entry:
            customer = customer_entry["payload"]

    conv_history = store.get_conversation(req.conversation_id)
    response = handle_reply(
        merchant_message=req.message, conversation_history=conv_history,
        category=category, merchant=merchant, customer=customer
    )

    if response.get("action") == "end":
        store.close_conversation(req.conversation_id)
    if response.get("action") == "send" and response.get("body"):
        store.add_conversation_turn(req.conversation_id, "vera", response["body"])

    return response


# ── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
```

---

## STEP 8 — CREATE README.md

```markdown
# Vera Bot — magicpin AI Challenge Submission

## Approach

Single-prompt composer with trigger-kind dispatch and rule-based conversation management.

**Architecture:**
- FastAPI server with 5 endpoints as required by the judge harness
- In-memory state store with version control for all 4 context scopes
- Groq Llama 3.3 70B (free, fast, under 2s latency) with temperature=0 for determinism
- Rule-based auto-reply detection (pattern matching, no LLM needed)
- LLM handles message composition and conversational reply handling

**Composition strategy:**
Each tick, the bot selects the highest-urgency unsuppressed trigger, builds a full prompt with all 4 context layers, and asks the LLM to produce one specific merchant-aware WhatsApp message using only facts from the given context.

**Compulsion levers used:**
- Specificity: real numbers, real offers, real citations from context
- Loss aversion: framing around what the merchant is missing
- Effort externalization: "I'll draft it, just say go"
- Curiosity: open-ended hooks that invite a reply
- Social proof: peer benchmarks from category stats

**What I optimized for:**
- Specificity over generic copy (real numbers, real offers, real citations)
- Category voice accuracy (clinical for dentists, warm for salons, operator for restaurants)
- Fast response time under 5s per compose call
- Graceful handling of auto-replies, opt-outs, and intent transitions

**Tradeoffs:**
- Using Groq Llama 3.3 70B (free) instead of a frontier model. Performs well at temperature=0 for structured JSON output.
- Single prompt for all trigger kinds rather than specialized per-kind prompts. Simpler to maintain and generalizes well.

**What would help with more time:**
- Retrieval over digest items using embeddings
- Specialized prompt templates per trigger kind
- Conversation planning layer for 24h session sequencing
```

---

## STEP 9 — HOW TO RUN

### Install dependencies
```bash
pip install -r requirements.txt
```

### Get Groq API key (free)
1. Go to https://console.groq.com
2. Sign up with Google (free, no credit card needed)
3. Click API Keys in sidebar
4. Create new key
5. Open .env and paste it as GROQ_API_KEY=your_key_here

### Run the server
```bash
python main.py
```
Server starts at http://localhost:8080

### Test with curl
```bash
# Health check
curl http://localhost:8080/v1/healthz

# Metadata
curl http://localhost:8080/v1/metadata

# Push dentist category context (use the real file)
curl -X POST http://localhost:8080/v1/context \
  -H "Content-Type: application/json" \
  -d "{\"scope\":\"category\",\"context_id\":\"dentists\",\"version\":1,\"payload\":$(cat dataset/categories/dentists.json)}"

# Push merchant
curl -X POST http://localhost:8080/v1/context \
  -H "Content-Type: application/json" \
  -d "{\"scope\":\"merchant\",\"context_id\":\"m_001_drmeera_dentist_delhi\",\"version\":1,\"payload\":$(python3 -c \"import json; d=json.load(open('dataset/merchants_seed.json')); print(json.dumps(d['merchants'][0]))\")}"

# Push trigger
curl -X POST http://localhost:8080/v1/context \
  -H "Content-Type: application/json" \
  -d "{\"scope\":\"trigger\",\"context_id\":\"trg_001_research_digest_dentists\",\"version\":1,\"payload\":$(python3 -c \"import json; d=json.load(open('dataset/triggers_seed.json')); print(json.dumps(d['triggers'][0]))\")}"

# Fire a tick
curl -X POST http://localhost:8080/v1/tick \
  -H "Content-Type: application/json" \
  -d '{"now":"2026-04-26T10:35:00Z","available_triggers":["trg_001_research_digest_dentists"]}'
```

### Deploy to Render (get public URL for submission)
1. Push this entire folder to a GitHub repo
2. Go to https://render.com, sign up free
3. New → Web Service → connect your GitHub repo
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. Add environment variables: GROQ_API_KEY, TEAM_NAME, CONTACT_EMAIL
7. Deploy. You get a URL like https://vera-bot-xxxx.onrender.com
8. Submit that URL on magicpin.com/vera/ai-challenge under the Submit tab

---

## SUBMISSION DEADLINE: 2 May 2026, 11:59 PM IST

Submit at: https://magicpin.com/vera/ai-challenge (Submit tab)
Enter: your public Render URL + name + email

---

## IMPORTANT RULES FOR THE BOT

1. The state store (store object in state.py) must be module-level singleton — never recreate it per request
2. Temperature MUST be 0 for determinism
3. Never put URLs in message body (instant penalty)
4. /v1/tick response must always have "actions" key even if empty list
5. /v1/reply response must always have "action" key (send/wait/end)
6. Max 20 actions per tick
7. Must respond within 30 seconds on every endpoint
