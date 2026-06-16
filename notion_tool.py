import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])
CRM_DATABASE_ID      = os.environ["NOTION_CRM_DATABASE_ID"]
CALENDAR_DATABASE_ID = os.environ["NOTION_CALENDAR_DATABASE_ID"]


def query_crm(search_name: str = None, status: str = None, lead_source: str = None) -> str:
    """
    Query the Southeast Homeworks Notion CRM database.
    Optionally filter by client name, status, or lead source.
    Returns a plain-text summary of matching records.
    """
    filters = []

    if search_name:
        filters.append({
            "property": "Name",
            "title": {"contains": search_name}
        })

    if status:
        filters.append({
            "property": "Status",
            "status": {"equals": status}
        })

    if lead_source:
        filters.append({
            "property": "Lead Source",
            "select": {"equals": lead_source}
        })

    query_params = {"database_id": CRM_DATABASE_ID}
    if len(filters) == 1:
        query_params["filter"] = filters[0]
    elif len(filters) > 1:
        query_params["filter"] = {"and": filters}

    response = notion.databases.query(**query_params)
    results = response.get("results", [])

    if not results:
        return "No matching records found in the CRM."

    lines = []
    for page in results:
        props = page["properties"]
        line_parts = []

        name         = _get_title(props, "Name")
        status_val   = _get_status(props, "Status")
        lead_src     = _get_select(props, "Lead Source")
        address      = _get_place(props, "Address")
        phone        = _get_phone(props, "Phone")
        email        = _get_email(props, "Email")
        price        = _get_number(props, "Price")
        zip_code     = _get_number(props, "ZIP")
        lead_date    = _get_date(props, "Lead Date")
        follow_up    = _get_date(props, "Follow Up ")  # trailing space is intentional — that's how it's named in Notion
        quote_date   = _get_date(props, "Quote Date")
        install_date = _get_date(props, "Install Date")

        line_parts.append(f"**{name}**")
        if status_val:    line_parts.append(f"Status: {status_val}")
        if lead_src:      line_parts.append(f"Source: {lead_src}")
        if address:       line_parts.append(f"Address: {address}")
        if zip_code:      line_parts.append(f"ZIP: {int(zip_code)}")
        if phone:         line_parts.append(f"Phone: {phone}")
        if email:         line_parts.append(f"Email: {email}")
        if price:         line_parts.append(f"Price: ${price:,.0f}")
        if lead_date:     line_parts.append(f"Lead Date: {lead_date}")
        if quote_date:    line_parts.append(f"Quote Date: {quote_date}")
        if install_date:  line_parts.append(f"Install Date: {install_date}")
        if follow_up:     line_parts.append(f"Follow Up: {follow_up}")

        lines.append(" | ".join(line_parts))

    return "\n".join(lines)


def query_notion_calendar(start_date: str = None, end_date: str = None, search_name: str = None) -> str:
    """
    Query Louis's Notion Calendar database.
    Optionally filter by date range or event name.
    Returns a plain-text list of events.
    """
    filters = []

    if start_date:
        filters.append({
            "property": "Date",
            "date": {"on_or_after": start_date}
        })

    if end_date:
        filters.append({
            "property": "Date",
            "date": {"on_or_before": end_date}
        })

    if search_name:
        filters.append({
            "property": "Name",
            "title": {"contains": search_name}
        })

    query_params = {
        "database_id": CALENDAR_DATABASE_ID,
        "sorts": [{"property": "Date", "direction": "ascending"}],
    }
    if len(filters) == 1:
        query_params["filter"] = filters[0]
    elif len(filters) > 1:
        query_params["filter"] = {"and": filters}

    response = notion.databases.query(**query_params)
    results = response.get("results", [])

    if not results:
        return "No events found in the Notion Calendar for that range."

    lines = []
    for page in results:
        props = page["properties"]
        name     = _get_title(props, "Name")
        date     = _get_date(props, "Date")
        location = _get_rich_text(props, "Location")

        parts = [f"- {name}"]
        if date:     parts.append(f"Date: {date}")
        if location: parts.append(f"Location: {location}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


def create_notion_calendar_event(name: str, date: str, location: str = None) -> str:
    """
    Create a new event in Louis's Notion Calendar database.
    date should be an ISO 8601 date or datetime string (e.g. '2025-04-23' or '2025-04-23T10:00:00').
    """
    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Date": {"date": {"start": date}},
    }
    if location:
        properties["Location"] = {"rich_text": [{"text": {"content": location}}]}

    notion.pages.create(
        parent={"database_id": CALENDAR_DATABASE_ID},
        properties=properties,
    )
    return f"Notion calendar event created: '{name}' on {date}" + (f" at {location}" if location else "")


def create_crm_lead(
    name: str,
    lead_source: str = None,
    address: str = None,
    phone: str = None,
    email: str = None,
    zip_code: int = None,
    notes: str = None,
    status: str = "New",
    lead_date: str = None,
) -> str:
    """
    Create a new lead record in the Southeast Homeworks Notion CRM.
    Used when Louis forwards a new lead email — Ashley parses the forward
    and drops the details in. lead_date defaults to today if not given.

    Address is written to "Address Line 2" (regular text) because the
    "Address" column is a Notion place/search field that's awkward to populate.
    Notes go into the page body as paragraph blocks.
    """
    from datetime import date as _date

    if lead_date is None:
        lead_date = _date.today().isoformat()

    properties = {
        "Name":      {"title": [{"text": {"content": name}}]},
        "Status":    {"status": {"name": status}},
        "Lead Date": {"date": {"start": lead_date}},
    }
    if lead_source:
        properties["Lead Source"] = {"select": {"name": lead_source}}
    if address:
        properties["Address Line 2"] = {"rich_text": [{"text": {"content": address}}]}
    if phone:
        properties["Phone"] = {"phone_number": phone}
    if email:
        properties["Email"] = {"email": email}
    if zip_code:
        properties["ZIP"] = {"number": zip_code}

    create_kwargs = {
        "parent":     {"database_id": CRM_DATABASE_ID},
        "properties": properties,
    }
    children = _build_lead_page_blocks(notes)
    if children:
        create_kwargs["children"] = children

    page = notion.pages.create(**create_kwargs)

    url = page.get("url", "")
    return f"Lead created in CRM: '{name}'" + (f" — {url}" if url else "")


def _build_lead_page_blocks(notes: str = None) -> list:
    """
    Build the children blocks for a new lead page using the lead template.
    Copies the template's heading + paragraph structure and replaces the empty
    paragraph immediately following the "Lead Notes:" heading with the parsed notes.

    Notion limitation: child_page blocks can't be copied via the API in a single
    create call, so they're skipped. Re-attach manually if needed.
    """
    template_id = os.environ.get("NOTION_LEAD_TEMPLATE_PAGE_ID")
    if not template_id:
        # No template configured — fall back to plain notes
        return _notes_to_paragraph_blocks(notes) if notes else []

    template_blocks = notion.blocks.children.list(block_id=template_id).get("results", [])

    new_blocks = []
    just_saw_lead_notes_heading = False
    notes_inserted = False

    for block in template_blocks:
        btype = block["type"]

        # Skip blocks we can't easily clone
        if btype == "child_page":
            continue
        if btype not in ("heading_1", "heading_2", "heading_3", "paragraph"):
            continue

        content   = block[btype]
        rich_text = content.get("rich_text", [])
        plain     = "".join(rt.get("plain_text", "") for rt in rich_text)

        # Replace the empty paragraph right after "Lead Notes:" with our notes
        if (
            just_saw_lead_notes_heading
            and btype == "paragraph"
            and not plain.strip()
            and notes
            and not notes_inserted
        ):
            new_blocks.extend(_notes_to_paragraph_blocks(notes))
            notes_inserted = True
            just_saw_lead_notes_heading = False
            continue

        # Otherwise copy the block as-is
        new_blocks.append({
            "type": btype,
            btype:  {"rich_text": rich_text},
        })

        just_saw_lead_notes_heading = (
            btype.startswith("heading_") and "lead notes" in plain.lower()
        )

    # Fallback: notes never got inserted (no Lead Notes section?), append at end
    if notes and not notes_inserted:
        new_blocks.extend(_notes_to_paragraph_blocks(notes))

    return new_blocks


def _notes_to_paragraph_blocks(notes: str) -> list:
    """
    Convert a notes string into a list of Notion paragraph blocks for page body.
    Splits on newlines, chunks any paragraph over 2000 chars (Notion's limit).
    """
    blocks = []
    for paragraph in notes.split("\n"):
        if not paragraph.strip():
            continue
        for i in range(0, len(paragraph), 2000):
            chunk = paragraph[i:i + 2000]
            blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })
    return blocks


# --- Helper functions to extract each property type cleanly ---

def _get_title(props, key):
    try:
        return props[key]["title"][0]["plain_text"]
    except (KeyError, IndexError):
        return "(no name)"

def _get_place(props, key):
    """Extract a Notion 'place' type property."""
    try:
        raw = props[key]
        # Try every known structure
        for sub_key in ("rich_text", "url", "place", "text"):
            val = raw.get(sub_key)
            if val and isinstance(val, list) and val:
                return val[0].get("plain_text") or val[0].get("text", {}).get("content")
            if val and isinstance(val, str):
                return val
            if val and isinstance(val, dict):
                return val.get("address") or str(val)
        return None
    except (KeyError, TypeError, IndexError):
        return None

def _get_rich_text(props, key):
    try:
        return props[key]["rich_text"][0]["plain_text"]
    except (KeyError, IndexError):
        return None

def _get_status(props, key):
    try:
        return props[key]["status"]["name"]
    except (KeyError, TypeError):
        return None

def _get_select(props, key):
    try:
        return props[key]["select"]["name"]
    except (KeyError, TypeError):
        return None

def _get_phone(props, key):
    try:
        return props[key]["phone_number"]
    except (KeyError, TypeError):
        return None

def _get_email(props, key):
    try:
        return props[key]["email"]
    except (KeyError, TypeError):
        return None

def _get_number(props, key):
    try:
        return props[key]["number"]
    except (KeyError, TypeError):
        return None

def _get_date(props, key):
    try:
        return props[key]["date"]["start"]
    except (KeyError, TypeError):
        return None
