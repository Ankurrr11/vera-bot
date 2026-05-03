"""
FastAPI server — all 5 required endpoints for the magicpin judge.
"""
import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from state import store
from composer import compose_message, handle_reply, select_best_triggers
from auto_reply import is_auto_reply
from tools import execute_tool
from router import route_intent
from memory import update_merchant_profile

app = FastAPI(title="Vera Bot", version=os.getenv("BOT_VERSION", "1.0.1-LEGENDARY"))


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
        merchant_entry = store.get_merchant(merchant_id)
        if not merchant_entry:
            continue
        merchant = merchant_entry["payload"]

        category_slug = merchant.get("category_slug")
        category_entry = store.get_category(category_slug)
        if not category_entry:
            continue
        category = category_entry["payload"]

        customer_id = trigger.get("customer_id")
        customer = None
        if customer_id:
            customer_entry = store.get_customer(customer_id)
            if customer_entry:
                customer = customer_entry["payload"]

        conversation_id = f"conv_{merchant_id}_{trigger.get('kind', 'msg')}_{trigger_id[-8:]}"
        conv_history = store.get_conversation(conversation_id)

        merchant_profile = store.get_merchant_profile(merchant_id)
        top_ctas = store.get_top_ctas(category_slug)

        composed = compose_message(
            category=category, merchant=merchant, trigger=trigger,
            customer=customer, conversation_history=conv_history,
            top_ctas=top_ctas, merchant_profile=merchant_profile
        )
        
        if composed.get("cta") and composed.get("cta") != "none":
            store.record_cta_attempt(category_slug, composed["cta"])

        store.add_conversation_turn(conversation_id, "vera", composed.get("body", ""))
        store.set_conversation_trigger(conversation_id, trigger_id)
        suppression_key = composed.get("suppression_key") or trigger.get("suppression_key", f"sent:{trigger_id}")
        store.suppress(suppression_key)

        if composed.get("action") == "tool":
            tool_name = composed.get("tool_name")
            tool_args = composed.get("tool_args", {})
            execute_tool(tool_name, merchant_id, tool_args)
            store.log_tool_execution(
                merchant_id=merchant_id,
                tool_name=tool_name or "unknown",
                args=json.dumps(tool_args)
            )

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
def reply(req: ReplyRequest, background_tasks: BackgroundTasks):
    if store.is_closed(req.conversation_id):
        return {"action": "end", "rationale": "Conversation already closed."}

    # 1. RECORD TURN
    store.add_conversation_turn(req.conversation_id, "merchant", req.message)
    conv_history = store.get_conversation(req.conversation_id)

    # 2. VERBATIM LOOP DETECTION
    # Check if this exact message has been sent by the merchant 3+ times in this conversation
    merchant_messages = [t["body"] for t in conv_history if t["role"] == "merchant"]
    verbatim_count = 0
    if len(merchant_messages) >= 3:
        last_msg = merchant_messages[-1].strip().lower()
        if all(m.strip().lower() == last_msg for m in merchant_messages[-3:]):
            verbatim_count = 3

    # 3. ROUTING (Intent Detection)
    intent = route_intent(req.message)
    if intent == "END":
        return {"action": "end", "rationale": "Merchant wants to end or has gone off-topic."}
    
    if intent == "HOSTILE":
        store.close_conversation(req.conversation_id)
        background_tasks.add_task(update_merchant_profile, req.merchant_id, req.conversation_id, store)
        return {"action": "end", "rationale": "Hostile intent detected. Closing conversation."}

    # 4. AUTO-REPLY & LOOP HANDLING
    is_auto = is_auto_reply(req.message) or verbatim_count >= 3
    if is_auto:
        count = store.get_auto_reply_count(req.merchant_id) + 1
        store.set_auto_reply_count(req.merchant_id, count)
        
        if count >= 3:
            store.close_conversation(req.conversation_id)
            return {"action": "end", "rationale": f"Auto-reply loop detected ({count}x)."}
        elif count == 2:
            return {"action": "wait", "wait_seconds": 1800, "rationale": "Auto-reply detected twice. Waiting 30 mins."}
        else:
            return {"action": "send", 
                    "body": "It looks like an automated response is active! If you'd like to continue our chat, please just reply with 'YES' or any message.",
                    "cta": "binary_yes_no", 
                    "rationale": "First auto-reply detected."}
    else:
        store.set_auto_reply_count(req.merchant_id, 0)

    # 5. LLM COMPOSER (Grounded response)
    merchant_entry = store.get_merchant(req.merchant_id)
    print(f"[DEBUG] Merchant {req.merchant_id} found: {merchant_entry is not None}")
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

    merchant_profile = store.get_merchant_profile(req.merchant_id)
    top_ctas = store.get_top_ctas(category.get("slug", "general"))

    conv_history = store.get_conversation(req.conversation_id)
    trigger_id = store.get_conversation_trigger_id(req.conversation_id)
    trigger = None
    if trigger_id:
        trigger_entry = store.get_trigger(trigger_id)
        if trigger_entry:
            trigger = trigger_entry["payload"]

    response = handle_reply(
        merchant_message=req.message, conversation_history=conv_history,
        category=category, merchant=merchant, customer=customer,
        merchant_profile=merchant_profile, top_ctas=top_ctas,
        trigger=trigger
    )

    # 6. UNIFIED POST-PROCESSING (Tools/Memory/History)
    if response.get("action") == "tool":
        tool_name = response.get("tool_name")
        tool_args = response.get("tool_args", {})
        execute_tool(tool_name, req.merchant_id, tool_args)
        store.log_tool_execution(req.merchant_id, tool_name, json.dumps(tool_args))
        
        response["body"] = f"Done! I've initiated the {tool_name} for you. Anything else?"
        response["action"] = "send" # Convert tool to send for the reply payload

    if response.get("action") == "end":
        store.close_conversation(req.conversation_id)
        background_tasks.add_task(update_merchant_profile, req.merchant_id, req.conversation_id, store)
    
    if response.get("action") == "send" and response.get("body"):
        store.add_conversation_turn(req.conversation_id, "vera", response["body"])

    return response

# ── ENDPOINT 6: GET /dashboard (V2 Enterprise) ───────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    stats = store.get_counts()
    uptime = store.uptime_seconds()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Vera Bot Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white font-sans">
        <div class="max-w-4xl mx-auto p-8">
            <h1 class="text-3xl font-bold mb-8 text-indigo-400">Vera Enterprise Analytics</h1>
            <div class="grid grid-cols-2 gap-4 mb-8">
                <div class="bg-gray-800 p-6 rounded-lg shadow-lg border border-gray-700">
                    <h2 class="text-sm uppercase text-gray-400 tracking-wider">Uptime</h2>
                    <p class="text-3xl font-bold">{uptime}s</p>
                </div>
                <div class="bg-gray-800 p-6 rounded-lg shadow-lg border border-gray-700">
                    <h2 class="text-sm uppercase text-gray-400 tracking-wider">Context Loaded</h2>
                    <p class="text-3xl font-bold">{sum(stats.values())}</p>
                </div>
            </div>
            
            <h2 class="text-xl font-semibold mb-4 border-b border-gray-700 pb-2">Tool Executions & CTAs</h2>
            <p class="text-gray-400">Database is active and tracking multi-agent stats.</p>
        </div>
    </body>
    </html>
    """
    return html


# ── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
