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
        store=store
    )

    if not trigger_ids:
        return {"actions": []}

    actions = []

    for trigger_id in trigger_ids:
        trigger_entry = store.get_trigger(trigger_id)
        if not trigger_entry:
            continue
        trigger = trigger_entry["payload"]

        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")

        merchant_entry = store.get_merchant(merchant_id)
        if not merchant_entry:
            continue
        merchant = merchant_entry["payload"]

        category_slug = merchant.get("category_slug")
        category_entry = store.get_category(category_slug)
        if not category_entry:
            continue
        category = category_entry["payload"]

        customer = None
        if customer_id:
            customer_entry = store.get_customer(customer_id)
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
        if "attachment_url" in composed:
            actions[-1]["attachment_url"] = composed["attachment_url"]

    return {"actions": actions}


# ── ENDPOINT 5: POST /v1/reply ───────────────────────────────────────────────

@app.post("/v1/reply")
def reply(req: ReplyRequest):
    if store.is_closed(req.conversation_id):
        return {"action": "end", "rationale": "Conversation already closed."}

    store.add_conversation_turn(req.conversation_id, "merchant", req.message)

    if is_auto_reply(req.message):
        count = store.get_auto_reply_count(req.merchant_id) + 1
        store.set_auto_reply_count(req.merchant_id, count)
        if count >= 3:
            store.close_conversation(req.conversation_id)
            return {"action": "end", "rationale": f"Auto-reply {count}x in a row. Closing conversation."}
        elif count == 2:
            return {"action": "wait", "wait_seconds": 86400, "rationale": "Auto-reply twice. Waiting 24h."}
        else:
            return {"action": "send", "body": "Looks like an auto-reply 😊 When you see this, just reply YES to continue.",
                    "cta": "binary_yes_no", "rationale": "First auto-reply detected. Flagging for owner."}
    else:
        store.set_auto_reply_count(req.merchant_id, 0)

    merchant_entry = store.get_merchant(req.merchant_id)
    if not merchant_entry:
        return {"action": "send", "body": "Thanks for your reply! How can I help?",
                "cta": "open_ended", "rationale": "Merchant context not found."}
    merchant = merchant_entry["payload"]

    category_entry = store.get_category(merchant.get("category_slug"))
    category = category_entry["payload"] if category_entry else {}

    customer = None
    if req.customer_id:
        customer_entry = store.get_customer(req.customer_id)
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
