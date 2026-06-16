TOOLS = [
    {
        "name": "get_calendar_events",
        "description": (
            "Fetches Louis's Google Calendar events within a given time range. "
            "Use this whenever the user asks about their schedule, availability, "
            "free time, or whether a specific time slot is open. "
            "Always call this before answering scheduling questions — do not guess."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_iso": {
                    "type": "string",
                    "description": (
                        "Start of the time range to check, in ISO 8601 format with timezone offset. "
                        "Example: '2025-04-22T08:00:00-05:00'"
                    ),
                },
                "end_iso": {
                    "type": "string",
                    "description": (
                        "End of the time range to check, in ISO 8601 format with timezone offset. "
                        "Example: '2025-04-22T18:00:00-05:00'"
                    ),
                },
            },
            "required": ["start_iso", "end_iso"],
        },
    },
    {
        "name": "query_crm",
        "description": (
            "Search Louis's Notion CRM database for client records. "
            "Use this when the user asks about a specific client, lead, or job — "
            "or wants to filter by status (e.g. 'active jobs'), lead source (e.g. 'Meta leads'), "
            "or any other CRM field. All parameters are optional — omit any you don't need."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Partial or full client name to search for. Example: 'Johnson'",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by job status. Use the exact status name as it appears in Notion.",
                },
                "lead_source": {
                    "type": "string",
                    "description": "Filter by lead source. Options: Meta, Angi, LSA, Other, SUB, Repeat",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a new event on Louis's Google Calendar. "
            "Use this when Louis asks you to add, schedule, or block something on his calendar. "
            "Always confirm the title, date, and time with Louis before calling this — do not create events without confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The event title. Example: 'Estimate — Johnson Residence'",
                },
                "start_iso": {
                    "type": "string",
                    "description": "Event start time in ISO 8601 format with timezone. Example: '2025-04-23T10:00:00-05:00'",
                },
                "end_iso": {
                    "type": "string",
                    "description": "Event end time in ISO 8601 format with timezone. Example: '2025-04-23T11:30:00-05:00'",
                },
                "description": {
                    "type": "string",
                    "description": "Optional notes or details to add to the event body.",
                },
            },
            "required": ["title", "start_iso", "end_iso"],
        },
    },
    {
        "name": "query_notion_calendar",
        "description": (
            "Query Louis's Notion Calendar database for scheduled events. "
            "Use this when Louis asks about items in his Notion calendar specifically. "
            "Supports filtering by date range or searching by event name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Filter events on or after this date. ISO 8601 date format. Example: '2025-04-22'",
                },
                "end_date": {
                    "type": "string",
                    "description": "Filter events on or before this date. ISO 8601 date format. Example: '2025-04-28'",
                },
                "search_name": {
                    "type": "string",
                    "description": "Search for a specific event by name.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_notion_calendar_event",
        "description": (
            "Add a new event to Louis's Notion Calendar database. "
            "Use this when Louis asks to add or schedule something in his Notion calendar. "
            "Always confirm the name and date before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The event name. Example: 'Estimate — Smith Residence'",
                },
                "date": {
                    "type": "string",
                    "description": "The event date in ISO 8601 format. Use 'YYYY-MM-DD' for all-day or 'YYYY-MM-DDTHH:MM:SS' for a specific time. Example: '2025-04-23' or '2025-04-23T10:00:00'",
                },
                "location": {
                    "type": "string",
                    "description": "Optional location for the event.",
                },
            },
            "required": ["name", "date"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important fact or preference to long-term memory so you remember it in future sessions. "
            "Use this when Louis tells you something worth remembering — a preference, a standing rule, "
            "a note about a client, or anything else that should persist. "
            "Keep facts short and specific. Do not save things that are already in memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact to remember. Keep it concise. Example: 'Louis prefers to schedule estimates before noon'",
                },
            },
            "required": ["fact"],
        },
    },

    # ---------- Email tools (Outlook 365 via Microsoft Graph) ----------

    {
        "name": "get_unread_emails",
        "description": (
            "Fetch unread emails from Ashley's mailbox (ashley@southeasthomeworks.com), oldest first. "
            "Returns MESSAGE_ID, CONVERSATION_ID, sender, received time, subject, and full body for each. "
            "Call this at the start of each run to see what needs handling. "
            "Use the MESSAGE_ID with reply_to_email / create_draft_reply / mark_as_read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max messages to fetch. Default 10."},
            },
            "required": [],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send a NEW email immediately from the Ashley mailbox. "
            "ONLY USE FOR EMAILS TO LOUIS (status updates, scheduling questions, summaries). "
            "Never use this to email a lead — for lead emails use create_draft_email so Louis "
            "can review the draft in his Drafts folder before sending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Louis's email address."},
                "subject": {"type": "string", "description": "Subject line."},
                "body":    {"type": "string", "description": "Email body, plain text."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "reply_to_email",
        "description": (
            "Reply in-thread to an existing email, sent immediately. "
            "ONLY USE WHEN REPLYING TO LOUIS. "
            "For replies to leads, use create_draft_reply so Louis can review before sending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "MESSAGE_ID from get_unread_emails."},
                "body":       {"type": "string", "description": "Reply body, plain text."},
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "create_draft_email",
        "description": (
            "Create a DRAFT new email in Ashley's Drafts folder (not sent). "
            "USE THIS FOR ALL OUTBOUND EMAILS TO LEADS. Louis will open the draft in the "
            "Ashley mailbox, review/edit, and send it himself. Standard lead-intro workflow: "
            "parse the forwarded lead → create_crm_lead → create_draft_email to introduce yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Lead's email address."},
                "subject": {"type": "string", "description": "Subject line."},
                "body":    {"type": "string", "description": "Email body, plain text."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "create_draft_reply",
        "description": (
            "Create a DRAFT reply in Ashley's Drafts folder, threaded to the original (not sent). "
            "USE WHEN REPLYING TO LEADS. Louis reviews and sends. "
            "For replies to Louis use reply_to_email instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "MESSAGE_ID of the lead's message."},
                "body":       {"type": "string", "description": "Reply body, plain text."},
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "mark_as_read",
        "description": (
            "Mark an email as read so the next poll cycle skips it. "
            "ALWAYS call this on each unread email after you've handled it (replied, drafted, "
            "logged to CRM, etc.) — otherwise you'll re-process the same message every poll."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "MESSAGE_ID from get_unread_emails."},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "get_conversation",
        "description": (
            "Fetch all messages in an email thread by conversation ID. "
            "Useful when a lead replies and you need context on what was discussed earlier "
            "in the thread before drafting your response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "CONVERSATION_ID from get_unread_emails."},
            },
            "required": ["conversation_id"],
        },
    },

    # ---------- CRM lead creation ----------

    {
        "name": "create_crm_lead",
        "description": (
            "Create a new lead record in the Southeast Homeworks Notion CRM. "
            "Use this when Louis forwards a new lead email — parse the forward for the lead's "
            "name, contact info, address, and notes, then drop them in. "
            "Defaults: Status='New', Lead Date=today. Returns the new page URL — "
            "include this URL in your reply to Louis so he can click through to verify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":        {"type": "string", "description": "Lead's full name. Required."},
                "lead_source": {"type": "string", "description": "Where the lead came from. Options: Meta, Angi, LSA, Other, SUB, Repeat."},
                "address":     {"type": "string", "description": "Full street address — stored in Address Line 2."},
                "phone":       {"type": "string", "description": "Phone number."},
                "email":       {"type": "string", "description": "Email address."},
                "zip_code":    {"type": "integer", "description": "ZIP code as integer."},
                "notes":       {"type": "string", "description": "Lead notes (project scope, preferences, anything from the forwarded body). Stored in the page body under 'Lead Notes:'."},
            },
            "required": ["name"],
        },
    },
]
