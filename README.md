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
