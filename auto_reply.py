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


import re

def is_opt_out(message: str) -> bool:
    msg_lower = message.lower().strip()
    if any(s in msg_lower for s in OPT_OUT_SIGNALS):
        return True
    # Fast path regex for hostile/angry intent
    hostile_pattern = r'\b(fuck|shit|leave me alone|fuck off|f off|f\*\*\*|bullshit)\b'
    if re.search(hostile_pattern, msg_lower):
        return True
    return False


def is_intent_to_act(message: str) -> bool:
    msg_lower = message.lower().strip()
    return any(s in msg_lower for s in ACTION_SIGNALS)
