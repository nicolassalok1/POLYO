You are Codex with full filesystem access inside the POLYO workspace.

TASK:
Generate a secure module named **secure_api_key.py** at the POLYO root, and update or regenerate `app_gmgn_polyo.py` so it uses secure storage rather than plain-text keys.

GOAL:
Implement a minimal “local secret manager” for Windows/PowerShell + Python with:
- Encryption of API key using AES-128 (via cryptography.fernet)
- Hash of the API key using SHA-256 (for validation)
- Secure file storage under a hidden file `.gmgn_secret` at the POLYO root
- No plaintext key stored anywhere
- Integration with Streamlit so the user can:
    1. Enter API key once
    2. Press “Save Securely”
    3. Have the encrypted key stored locally
    4. App automatically loads/decrypts it in future sessions
    5. Display only the key’s hash (never the key itself)

===========================================================
FILE 1 — secure_api_key.py
===========================================================

Create functions:

1) generate_keyfile_if_missing():
    - Creates a Fernet encryption key stored in `.gmgn_secret_key` if not already present.

2) encrypt_and_store_api_key(api_key: str):
    - Uses the Fernet key to encrypt the API key.
    - Stores ciphertext in `.gmgn_secret`.
    - Stores SHA-256 hash into `.gmgn_secret_hash`.
    - Never store plaintext.

3) load_api_key() -> str | None:
    - Reads Fernet key
    - Decrypts ciphertext from `.gmgn_secret`
    - Returns plaintext API key if available
    - Returns None if missing

4) load_api_key_hash() -> str | None:
    - Loads the SHA-256 hex digest from `.gmgn_secret_hash`

5) clear_api_key():
    - Deletes `.gmgn_secret` and `.gmgn_secret_hash`

===========================================================
FILE 2 — UPDATE app_gmgn_polyo.py
===========================================================

Modify (or regenerate) the entire Streamlit app as follows:

A — At the top:
    import secure_api_key

B — In the sidebar:
    - Input box for GMGN API Key (password=True)
    - Buttons:
         “Save API Key Securely”
         “Clear API Key”
    - Display:
         - If API key is stored: 
               st.sidebar.markdown("Encrypted key loaded.")
               Show only:
                    SHA-256 hash prefix: e.g. hash[:12] + "…"
         - If not stored:
               st.sidebar.warning("No API key stored.")

C — Secure workflow:
    - If user enters a key and presses “Save Securely”:
          secure_api_key.encrypt_and_store_api_key(api_key_input)
          Do not print or log the plaintext.
    - If user presses “Clear API Key”:
          secure_api_key.clear_api_key()

D — API usage:
    - GMGN requests must use:
          stored_key = secure_api_key.load_api_key()
          or fallback to dummy mode
    - If the user typed a key in the session but didn't save it,
          prefer the typed key for that session only.

E — UI mode indicator:
    If stored_key or session_key valid:
         check GMGN endpoint
         if OK → MODE LIVE
         else → MODE TEST + warning
    Else:
         MODE TEST + info

===========================================================
SECURITY RULES
===========================================================

- The API key must NEVER appear in logs, print(), or Streamlit UI.
- Only hashed prefix (first 10–12 chars of SHA-256) may be shown.
- No plaintext key written to disk.
- No plaintext key returned through session_state except when typed manually.

===========================================================
OUTPUT
===========================================================

Codex must output ONLY the full code for:

1) secure_api_key.py
2) app_gmgn_polyo.py   (the updated version using secure storage)

No comments or explanations outside the code.
