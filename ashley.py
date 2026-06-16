import os
from dotenv import load_dotenv
import anthropic
from tools import TOOLS
from calendar_tool import get_calendar_events

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are Ashley Iverson, a sharp and friendly scheduling assistant for Louis Burmeister, who runs Southeast Homeworks — an interior painting company in Madison, Wisconsin.

Louis's working hours are roughly 8am–6pm Central Time, Monday through Saturday.
Estimates and consultations typically take 60–90 minutes plus drive time.
Today's date and current time will be provided in each system message so you always know what "today", "tomorrow", and "next week" mean.

Your job:
- Answer scheduling questions conversationally and concisely — no essays
- Always fetch real calendar data before answering availability questions
- When flagging open time, proactively mention tight spots (e.g. "only a 20-minute gap before your next thing")
- Use Central Time for all times
- Be friendly but efficient — Louis is busy"""

def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_calendar_events":
        return get_calendar_events(tool_input["start_iso"], tool_input["end_iso"])
    return f"Unknown tool: {tool_name}"

def chat(conversation_history: list, user_message: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/Chicago"))
    current_time_str = now.strftime("%A, %B %-d, %Y at %-I:%M %p Central Time")
    system_with_time = f"{SYSTEM_PROMPT}\n\nCurrent date and time: {current_time_str}"

    conversation_history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=system_with_time,
            tools=TOOLS,
            messages=conversation_history,
        )

        # Claude wants to call a tool
        if response.stop_reason == "tool_use":
            # Add Claude's response (which contains the tool call) to history
            conversation_history.append({"role": "assistant", "content": response.content})

            # Find and execute all tool calls in the response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [fetching calendar: {block.input.get('start_iso')} → {block.input.get('end_iso')}]")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Add tool results to history and loop back so Claude can respond
            conversation_history.append({"role": "user", "content": tool_results})

        # Claude is done — return the final text response
        elif response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            conversation_history.append({"role": "assistant", "content": response.content})
            return final_text

        else:
            return f"Unexpected stop reason: {response.stop_reason}"

def main():
    print("Ashley Iverson — Southeast Homeworks Scheduling Assistant")
    print("Type your question, or 'quit' to exit.\n")

    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTalk soon, Louis.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("Ashley: Talk soon, Louis.")
            break

        response = chat(conversation_history, user_input)
        print(f"\nAshley: {response}\n")

if __name__ == "__main__":
    main()
