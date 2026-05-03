import json

def pause_campaign(merchant_id: str, args: dict):
    # Mock implementation
    return {"status": "success", "message": f"Campaign paused for merchant {merchant_id}"}

def update_listing(merchant_id: str, args: dict):
    # Mock implementation
    return {"status": "success", "message": f"Listing updated for merchant {merchant_id}"}

def create_wa_promo(merchant_id: str, args: dict):
    # Mock implementation
    return {"status": "success", "message": f"WhatsApp promo drafted for merchant {merchant_id}"}

TOOL_REGISTRY = {
    "pause_campaign": pause_campaign,
    "update_listing": update_listing,
    "create_wa_promo": create_wa_promo
}

def execute_tool(name: str, merchant_id: str, args: dict):
    if name in TOOL_REGISTRY:
        print(f"Executing tool: {name} for merchant {merchant_id} with args {args}")
        return TOOL_REGISTRY[name](merchant_id, args)
    return {"status": "error", "message": f"Tool {name} not found"}
