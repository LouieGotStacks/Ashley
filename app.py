import os
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
import anthropic
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from tools import TOOLS
from calendar_tool import get_calendar_events, create_calendar_event
from notion_tool import query_crm, query_notion_calendar, create_notion_calendar_event

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SMS_SYSTEM_PROMPT = """You are Ashley Iverson, Louis Burmeister's scheduling assistant for Southeast Homeworks, an interior painting company in Madison, Wisconsin.

You are responding via SMS so replies must be SHORT. Aim for under 300 characters, 500 max. No bullet points, no long lists. Be direct and conversational.

Louis's working hours are roughly 8am to 6pm Central Time, Monday through Saturday. Estimates take 60 to 90 minutes plus drive time. Today's date and time will be provided.

Writing style: NEVER use the em dash character. Not anywhere. Use periods, commas, parentheses, or rephrase. Two hyphens (--) are also off-limits as a substitute. En dashes are off-limits too."""

SYSTEM_PROMPT = """You are Ashley Iverson, a sharp and friendly scheduling assistant for Louis Burmeister, who runs Southeast Homeworks, an interior painting company in Madison, Wisconsin.

Louis's working hours are roughly 8am to 6pm Central Time, Monday through Saturday.
Estimates and consultations typically take 60 to 90 minutes plus drive time.
Today's date and current time will be provided in each system message so you always know what "today", "tomorrow", and "next week" mean.

Your job:
- Answer scheduling questions conversationally and concisely. No essays.
- Always fetch real calendar data before answering availability questions
- When flagging open time, proactively mention tight spots (e.g. "only a 20-minute gap before your next thing")
- Use Central Time for all times
- Be friendly but efficient. Louis is busy.

Writing style: NEVER use the em dash character. Not anywhere. Use periods, commas, parentheses, or rephrase. Two hyphens (--) are also off-limits as a substitute. En dashes are off-limits too."""

# Single in-memory conversation history (one user, one session)
conversation_history = []

def load_memory() -> str:
    """Read the memory.md file and return its contents, or empty string if missing."""
    try:
        with open("memory.md", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def save_memory(fact: str) -> str:
    """Append a new fact to the Other Notes section of memory.md."""
    with open("memory.md", "a") as f:
        f.write(f"\n- {fact}")
    return f"Saved to memory: {fact}"

def serialize_content(content):
    """Convert Anthropic SDK content blocks to plain dicts for history storage."""
    result = []
    for block in content:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return result

def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_calendar_events":
        return get_calendar_events(tool_input["start_iso"], tool_input["end_iso"])
    if tool_name == "create_calendar_event":
        return create_calendar_event(
            title=tool_input["title"],
            start_iso=tool_input["start_iso"],
            end_iso=tool_input["end_iso"],
            description=tool_input.get("description"),
        )
    if tool_name == "create_notion_calendar_event":
        return create_notion_calendar_event(
            name=tool_input["name"],
            date=tool_input["date"],
            location=tool_input.get("location"),
        )
    if tool_name == "query_notion_calendar":
        return query_notion_calendar(
            start_date=tool_input.get("start_date"),
            end_date=tool_input.get("end_date"),
            search_name=tool_input.get("search_name"),
        )
    if tool_name == "save_memory":
        return save_memory(tool_input["fact"])
    if tool_name == "query_crm":
        return query_crm(
            search_name=tool_input.get("search_name"),
            status=tool_input.get("status"),
            lead_source=tool_input.get("lead_source"),
        )
    return f"Unknown tool: {tool_name}"

def chat(user_message: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/Chicago"))
    current_time_str = now.strftime("%A, %B %-d, %Y at %-I:%M %p Central Time")
    memory = load_memory()
    memory_block = f"\n\n## Your Memory Notes\n{memory}" if memory else ""
    system_with_time = f"{SYSTEM_PROMPT}{memory_block}\n\nCurrent date and time: {current_time_str}"

    conversation_history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_with_time,
            tools=TOOLS,
            messages=conversation_history,
        )

        if response.stop_reason == "tool_use":
            conversation_history.append({"role": "assistant", "content": serialize_content(response.content)})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = run_tool(block.name, block.input)
                    except Exception as e:
                        print(f"Tool error ({block.name}): {e}")
                        result = f"Tool error: {str(e)}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            conversation_history.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            conversation_history.append({"role": "assistant", "content": serialize_content(response.content)})
            return final_text

        else:
            return f"Unexpected stop reason: {response.stop_reason}"

def chat_sms(user_message: str) -> str:
    """Standalone single-turn chat for SMS — no conversation history."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/Chicago"))
    current_time_str = now.strftime("%A, %B %-d, %Y at %-I:%M %p Central Time")
    memory = load_memory()
    memory_block = f"\n\nMemory notes:\n{memory}" if memory else ""
    system_with_time = f"{SMS_SYSTEM_PROMPT}{memory_block}\n\nCurrent date and time: {current_time_str}"

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=system_with_time,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": serialize_content(response.content)})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = run_tool(block.name, block.input)
                    except Exception as e:
                        result = f"Tool error: {str(e)}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            return "".join(block.text for block in response.content if hasattr(block, "text"))

        else:
            return "Sorry, something went wrong. Try again."

@app.route("/sms", methods=["POST"])
def sms_endpoint():
    # Validate the request is actually from Twilio
    # On Railway, requests come in as http internally but Twilio signs with https
    # so we reconstruct the correct public URL manually
    validator = RequestValidator(os.environ.get("TWILIO_AUTH_TOKEN", ""))
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "https")
    url = request.url.replace("http://", f"{forwarded_proto}://", 1)
    post_params = request.form.to_dict()
    signature = request.headers.get("X-Twilio-Signature", "")

    if not validator.validate(url, post_params, signature):
        print(f"Twilio signature validation failed. URL: {url}")
        return "Unauthorized", 403

    incoming_message = request.form.get("Body", "").strip()
    reply_text = chat_sms(incoming_message)

    response = MessagingResponse()
    response.message(reply_text)
    return str(response), 200, {"Content-Type": "text/xml"}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    reply = chat(user_message)
    return jsonify({"reply": reply})

@app.route("/reset", methods=["POST"])
def reset():
    conversation_history.clear()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RAILWAY_ENVIRONMENT") is None  # debug only when running locally
    app.run(host="0.0.0.0", port=port, debug=debug)
