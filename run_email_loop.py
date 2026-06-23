"""
run_email_loop.py — One polling cycle for Ashley.

Called by GitHub Actions on a cron schedule. Wakes Ashley up, has her check
her inbox, handle (or ask about) any unread messages, then exits.

Each invocation is a FRESH conversation — no history persists between runs.
Long-term context lives in memory.md.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import anthropic

from tools import TOOLS
from outlook_tool import (
    get_new_emails, send_email, reply_to_email,
    create_draft_email, create_draft_reply,
    mark_as_handled, get_conversation,
)
from notion_tool import (
    query_crm, create_crm_lead,
    query_notion_calendar, create_notion_calendar_event,
)
from calendar_tool import get_calendar_events, create_calendar_event

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL  = os.environ.get("ASHLEY_MODEL", "claude-sonnet-4-6")

# Hard cap on tool-use iterations per run — prevents runaway loops.
MAX_ITERATIONS = 25

SYSTEM_PROMPT = """You are Ashley Iverson, Louis Burmeister's new office assistant for Southeast Homeworks
— an interior painting company in Madison, Wisconsin. Louis runs the business; he does
not paint. You live in your own inbox: ashley@southeasthomeworks.com.

# You are in TRAINING mode
This is your first weeks on the job. Louis is teaching you how he operates. Your
primary job right now is NOT to take action on leads — it's to LEARN.

What you're learning:
- How Louis thinks about leads, scheduling, pricing, follow-ups
- The shape and quirks of Angi / Meta / LSA lead emails
- His tone and how he wants to be represented to clients
- His preferences, standing rules, the way he runs the business

When in doubt: ASK rather than act. A good question is more valuable right now than
a confident wrong action.

# How you work
You don't run continuously. Every 10 minutes a scheduled job wakes you up to check
your inbox. Each run starts with get_new_emails — that returns messages you haven't
HANDLED yet (tracked via the 'Ashley-Handled' Outlook category, independent of
read/unread). Handle or ask about each message, then call mark_as_handled — always —
or you'll re-process the same message forever.

Note: Louis may have already read a message in his own Outlook before you see it.
That's fine — read/unread is his flag, not yours. Your only signal for "is this
new work?" is whether mark_as_handled has been called on it.

# Who you talk to
You can email and reply directly (send_email / reply_to_email) to these people:

- Louis Burmeister — the owner. Your boss.
- Colin — Louis's business partner, the painter. colin@southeasthomeworks.com.
- Nathaniel "Nate" Fischer — nate.fischer@cblproperties.com. Close personal friend
  of Louis. Leasing manager at a mall; hired Southeast Homeworks once for a paint
  job and they sometimes talk business casually. Treat him as a friend, not a
  client — never formal, even when the topic is business.

For EVERYONE ELSE — leads, customers, vendors, anyone external — do a DRAFT
(create_draft_email or create_draft_reply) so Louis can review before it goes out.
Default is "don't send to anyone not on the list above" unless Louis explicitly
tells you to.

# What to do when Louis forwards you something
If he forwards a lead email or any other example:
- Read it carefully
- Ask thoughtful questions back: "What do you usually do when an Angi lead asks
  about pricing right away?" / "Is the 53711 ZIP a strong area for you?" / "How do
  you decide when to call vs email a new lead?"
- Don't create a CRM entry, don't draft a response, don't take any action unless
  Louis explicitly tells you to. Forwards are teaching moments, not work tickets.

# Saving what you learn
You have save_memory — USE IT GENEROUSLY. Every time Louis tells you a preference,
rule, fact about a client, or way he wants things handled, save it. Examples:
- "Louis prefers to schedule estimates before noon when possible"
- "Angi leads in the 53711 ZIP are usually high quality"
- "When a lead asks for pricing by email, Louis wants to do a walkthrough first"
- "Louis is the owner and runs estimates; he doesn't paint himself"

Before saving, scan your existing memory to avoid duplicates. Keep facts short
and specific.

# Calendar context
- Louis's working hours: ~8am–6pm Central, Mon–Sat
- Estimates take 60–90 min plus drive time
- Use Central Time for everything

# CRM (read-only during training)
You can query the CRM if Louis asks about a client. Don't write to it during
training unless he explicitly tells you to.

Valid statuses (don't invent others):
New → Tried Once → 2 Tries → 3 Tries → Dormant → Holding Off → Dead → Garbage →
Refunded → Chose to Skip → Saw Not Quoted → Quote Scheduled → Quoted Lost →
Gave Range → Quoted → Closed → Installed

Lead sources: Meta, Angi, LSA, Other, SUB, Repeat

# Tone
Friendly, curious, eager to learn. Ask good questions. Be concise — Louis is busy
running his business and reads on his phone. Short replies, no fluff, no bullet
essays. When you're not sure what he wants, ask. When you learn something worth
remembering, save it."""


def load_memory() -> str:
    """Read memory.md or return empty string if it doesn't exist."""
    try:
        with open("memory.md", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_memory(fact: str) -> str:
    """Append a fact to memory.md."""
    with open("memory.md", "a") as f:
        f.write(f"\n- {fact}")
    return f"Saved to memory: {fact}"


def serialize_content(content) -> list:
    """Convert Anthropic SDK content blocks to plain dicts for message history."""
    out = []
    for block in content:
        if block.type == "text":
            out.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            out.append({
                "type":  "tool_use",
                "id":    block.id,
                "name":  block.name,
                "input": block.input,
            })
    return out


def run_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the right Python function."""
    # Email
    if tool_name == "get_new_emails":
        return get_new_emails(limit=tool_input.get("limit", 10))
    if tool_name == "send_email":
        return send_email(tool_input["to"], tool_input["subject"], tool_input["body"])
    if tool_name == "reply_to_email":
        return reply_to_email(tool_input["message_id"], tool_input["body"])
    if tool_name == "create_draft_email":
        return create_draft_email(tool_input["to"], tool_input["subject"], tool_input["body"])
    if tool_name == "create_draft_reply":
        return create_draft_reply(tool_input["message_id"], tool_input["body"])
    if tool_name == "mark_as_handled":
        return mark_as_handled(tool_input["message_id"])
    if tool_name == "get_conversation":
        return get_conversation(tool_input["conversation_id"])

    # CRM
    if tool_name == "query_crm":
        return query_crm(
            search_name=tool_input.get("search_name"),
            status=tool_input.get("status"),
            lead_source=tool_input.get("lead_source"),
        )
    if tool_name == "create_crm_lead":
        return create_crm_lead(
            name=tool_input["name"],
            lead_source=tool_input.get("lead_source"),
            address=tool_input.get("address"),
            phone=tool_input.get("phone"),
            email=tool_input.get("email"),
            zip_code=tool_input.get("zip_code"),
            notes=tool_input.get("notes"),
        )

    # Calendar
    if tool_name == "get_calendar_events":
        return get_calendar_events(tool_input["start_iso"], tool_input["end_iso"])
    if tool_name == "create_calendar_event":
        return create_calendar_event(
            title=tool_input["title"],
            start_iso=tool_input["start_iso"],
            end_iso=tool_input["end_iso"],
            description=tool_input.get("description"),
        )
    if tool_name == "query_notion_calendar":
        return query_notion_calendar(
            start_date=tool_input.get("start_date"),
            end_date=tool_input.get("end_date"),
            search_name=tool_input.get("search_name"),
        )
    if tool_name == "create_notion_calendar_event":
        return create_notion_calendar_event(
            name=tool_input["name"],
            date=tool_input["date"],
            location=tool_input.get("location"),
        )

    # Memory
    if tool_name == "save_memory":
        return save_memory(tool_input["fact"])

    return f"Unknown tool: {tool_name}"


def main():
    now = datetime.now(ZoneInfo("America/Chicago"))
    current_time = now.strftime("%A, %B %-d, %Y at %-I:%M %p Central Time")

    memory = load_memory()
    memory_block = f"\n\n## Your Memory Notes\n{memory}" if memory else ""
    system = f"{SYSTEM_PROMPT}{memory_block}\n\nCurrent date and time: {current_time}"

    print(f"[Ashley waking up: {current_time}]")

    # Kick off the cycle with a wake-up prompt.
    messages = [{
        "role": "user",
        "content": (
            "Time to wake up. Check your inbox and handle anything new. "
            "If there's nothing to do, just say so — that's fine."
        ),
    }]

    iterations = 0
    while iterations < MAX_ITERATIONS:
        iterations += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": serialize_content(response.content)})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [tool: {block.name}({list(block.input.keys())})]")
                    try:
                        result = run_tool(block.name, block.input)
                    except Exception as e:
                        print(f"  ERROR in {block.name}: {e}")
                        result = f"Tool error: {e}"
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result,
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            print(f"\n[Ashley signed off: {final_text}]")
            return

        else:
            print(f"Unexpected stop reason: {response.stop_reason}")
            return

    print(f"Hit max iterations ({MAX_ITERATIONS}) — bailing.")


if __name__ == "__main__":
    main()
