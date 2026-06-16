from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import json
import base64
import tempfile

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _decode_env_json(env_var: str):
    """Decode a base64-encoded JSON environment variable into a temp file path."""
    value = os.environ.get(env_var)
    if not value:
        return None
    decoded = base64.b64decode(value).decode("utf-8")
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write(decoded)
    tmp.flush()
    return tmp.name

def get_credentials():
    creds = None

    # --- Load token ---
    # On Railway: read from GOOGLE_TOKEN_JSON env var
    # Locally: read from token.json file
    token_env = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_env:
        token_data = json.loads(base64.b64decode(token_env).decode("utf-8"))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # --- Refresh or re-authorize if needed ---
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

            # Save refreshed token back — to file locally, printed as warning on Railway
            if not token_env:
                with open("token.json", "w") as f:
                    f.write(creds.to_json())
            else:
                print("WARNING: Token refreshed but running on Railway — update GOOGLE_TOKEN_JSON env var if issues occur.")

        else:
            # First-time login — only works locally (opens a browser)
            creds_path = _decode_env_json("GOOGLE_CREDENTIALS_JSON") or "credentials.json"
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

            with open("token.json", "w") as f:
                f.write(creds.to_json())

    return creds
