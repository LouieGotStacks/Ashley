"""
outlook_tool.py — Microsoft Graph wrapper for the Ashley shared mailbox.

Provides the functions Ashley uses to read, reply to, and send mail from
ashley@southeasthomeworks.com. Auth uses MSAL's client-credentials flow
(no user login required — works headless on GitHub Actions).

Split for safety: leads get DRAFTS (you review before sending), Louis gets
direct sends/replies (Ashley talks to you freely).
"""
import os
from typing import Optional
import requests
import msal
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.environ["MS_TENANT_ID"]
CLIENT_ID     = os.environ["MS_CLIENT_ID"]
CLIENT_SECRET = os.environ["MS_CLIENT_SECRET"]
MAILBOX       = os.environ["ASHLEY_MAILBOX"]

GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# Token cache for this process (good for ~60 min — plenty for one Actions run)
_cached_token: Optional[str] = None


def _get_access_token() -> str:
    """Get an OAuth token via client credentials. Cached for the process."""
    global _cached_token
    if _cached_token:
        return _cached_token

    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

    if "access_token" not in result:
        raise RuntimeError(
            f"Microsoft Graph auth failed: "
            f"{result.get('error')} — {result.get('error_description')}"
        )

    _cached_token = result["access_token"]
    return _cached_token


def _graph(method: str, endpoint: str, json_body: Optional[dict] = None) -> dict:
    """
    Make an authenticated Graph API request.
    `endpoint` starts with "/" — e.g. "/users/ashley@.../messages".
    Returns parsed JSON, or {} for no-content responses.
    """
    token = _get_access_token()
    url = f"{GRAPH_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = requests.request(method, url, headers=headers, json=json_body)

    if not response.ok:
        raise RuntimeError(
            f"Graph {method} {endpoint} failed: "
            f"{response.status_code} {response.text}"
        )

    # 202 Accepted (e.g. sendMail) and 204 No Content return empty bodies
    if response.status_code in (202, 204) or not response.content:
        return {}
    return response.json()


# ---------- Reading mail ----------

HANDLED_CATEGORY = "Ashley-Handled"


def get_new_emails(limit: int = 10, days: int = 14) -> str:
    """
    Fetch recent Inbox messages that Ashley has NOT yet handled,
    oldest first (so forwards process in arrival order).

    "Handled" is tracked via the 'Ashley-Handled' Outlook category, set by
    mark_as_handled. This is independent of the read/unread flag — Louis
    can read/preview without affecting what Ashley sees as new work.

    `days` caps how far back we look so results stay bounded.
    """
    from datetime import datetime, timedelta, timezone

    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Pull a generous batch by date, then filter out handled ones client-side.
    # (Graph $filter on multi-value 'categories' with negation is finicky;
    # filtering in Python is simpler and more reliable.)
    fetch_top = max(limit * 3, 25)
    params = (
        f"?$filter=receivedDateTime ge {cutoff_iso}"
        f"&$top={fetch_top}"
        f"&$orderby=receivedDateTime asc"
        f"&$select=id,conversationId,subject,from,receivedDateTime,body,categories"
    )
    data = _graph("GET", f"/users/{MAILBOX}/mailFolders/Inbox/messages{params}")
    messages = data.get("value", [])

    pending = [
        m for m in messages
        if HANDLED_CATEGORY not in (m.get("categories") or [])
    ][:limit]

    if not pending:
        return "No new (unhandled) messages in Ashley's inbox."

    chunks = []
    for msg in pending:
        sender_obj = msg.get("from", {}).get("emailAddress", {}) or {}
        sender = f"{sender_obj.get('name', '?')} <{sender_obj.get('address', '?')}>"
        chunks.append(
            f"---\n"
            f"MESSAGE_ID: {msg['id']}\n"
            f"CONVERSATION_ID: {msg['conversationId']}\n"
            f"From: {sender}\n"
            f"Received: {msg.get('receivedDateTime', '?')}\n"
            f"Subject: {msg.get('subject', '(no subject)')}\n"
            f"Body:\n{msg.get('body', {}).get('content', '')}\n"
        )
    return "\n".join(chunks)


# Back-compat alias so older callers keep working.
get_unread_emails = get_new_emails


def get_conversation(conversation_id: str) -> str:
    """
    Fetch all messages in a thread for context (e.g. when a lead replies
    and Ashley needs to recall earlier exchanges).
    """
    params = (
        f"?$filter=conversationId eq '{conversation_id}'"
        f"&$orderby=receivedDateTime asc"
        f"&$select=id,subject,from,receivedDateTime,bodyPreview"
    )
    data = _graph("GET", f"/users/{MAILBOX}/messages{params}")
    messages = data.get("value", [])

    if not messages:
        return f"No messages found in conversation {conversation_id}."

    lines = []
    for msg in messages:
        sender_obj = msg.get("from", {}).get("emailAddress", {}) or {}
        sender = f"{sender_obj.get('name', '?')} <{sender_obj.get('address', '?')}>"
        preview = (msg.get("bodyPreview") or "")[:200]
        lines.append(f"- {msg.get('receivedDateTime')} | {sender} | {msg.get('subject')} | {preview}")
    return "\n".join(lines)


# ---------- Writing mail ----------

def send_email(to: str, subject: str, body: str) -> str:
    """
    Send a new email immediately FROM the Ashley mailbox.
    For emails to LOUIS only (status updates, scheduling questions).
    For emails to LEADS, use create_draft_email.
    """
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True,
    }
    _graph("POST", f"/users/{MAILBOX}/sendMail", json_body=payload)
    return f"Sent email to {to} — subject: '{subject}'"


def reply_to_email(message_id: str, body: str) -> str:
    """
    Reply in-thread to an existing message, sent immediately.
    For replies to LOUIS only. For lead replies, use create_draft_reply.
    """
    # createReply gives us a draft with threading already set up;
    # we patch the body, then send it.
    draft = _graph("POST", f"/users/{MAILBOX}/messages/{message_id}/createReply")
    draft_id = draft["id"]
    _graph(
        "PATCH",
        f"/users/{MAILBOX}/messages/{draft_id}",
        json_body={"body": {"contentType": "Text", "content": body}},
    )
    _graph("POST", f"/users/{MAILBOX}/messages/{draft_id}/send")
    return f"Replied to message {message_id}"


def create_draft_email(to: str, subject: str, body: str) -> str:
    """
    Create a DRAFT new email in Ashley's Drafts folder (NOT sent).
    For LEAD intros during draft-review mode — Louis will open the
    Ashley mailbox, review the draft, and hit Send.
    """
    payload = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": to}}],
    }
    result = _graph("POST", f"/users/{MAILBOX}/messages", json_body=payload)
    return f"Draft created for {to} — subject: '{subject}' (draft id: {result.get('id', '?')})"


def create_draft_reply(message_id: str, body: str) -> str:
    """
    Create a DRAFT reply in Ashley's Drafts folder (NOT sent),
    threaded to the original message.
    For replies to LEADS during draft-review mode.
    """
    draft = _graph("POST", f"/users/{MAILBOX}/messages/{message_id}/createReply")
    draft_id = draft["id"]
    _graph(
        "PATCH",
        f"/users/{MAILBOX}/messages/{draft_id}",
        json_body={"body": {"contentType": "Text", "content": body}},
    )
    return f"Draft reply created (draft id: {draft_id})"


# ---------- State management ----------

def mark_as_handled(message_id: str) -> str:
    """
    Tag a message with the 'Ashley-Handled' category so future poll cycles
    skip it. Preserves any categories the message already has.

    Read/unread flag is left alone — Louis controls that as a normal user.
    """
    # Fetch current categories so we can append without clobbering.
    msg = _graph(
        "GET",
        f"/users/{MAILBOX}/messages/{message_id}?$select=categories",
    )
    existing = msg.get("categories") or []
    if HANDLED_CATEGORY in existing:
        return f"Message {message_id} was already marked handled."

    _graph(
        "PATCH",
        f"/users/{MAILBOX}/messages/{message_id}",
        json_body={"categories": existing + [HANDLED_CATEGORY]},
    )
    return f"Marked message {message_id} as handled"


# Back-compat alias — old code/prompts that call mark_as_read still work.
mark_as_read = mark_as_handled


# ---------- Local test ----------

if __name__ == "__main__":
    print("Testing Microsoft Graph connection to Ashley's mailbox...\n")
    try:
        result = get_new_emails(limit=5)
        print(result)
        print("\n✅ Connection works. Auth is set up correctly.")
    except Exception as e:
        print(f"❌ Something went wrong: {e}")
        raise
