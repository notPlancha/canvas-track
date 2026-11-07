"""Custom URI Protocol Handler and Token Parser for Canvas Track.

Enables hands-free Single Sign-On (SSO) login for Moodle by registering the
canvastrack:// URI scheme in user-level Windows registry (HKCU) and extracting
web service tokens from SSO redirects and base64 strings.
"""

from __future__ import annotations

import base64
import logging
import re
import sys

logger = logging.getLogger(__name__)

PROTOCOL_NAME = "canvastrack"


def extract_moodle_token(raw_input: str) -> str:
    """Extract a valid 32-character Moodle Web Service token from raw input.

    Accepts:
      - canvastrack://token=<base64>
      - moodlemobile://token=<base64>
      - Raw base64 strings
      - Delimited tokens: <passport>:::<token> or <url>:::<token>:::<privatetoken>
      - Plain 32-character hexadecimal token string
    """
    token_str = raw_input.strip()

    # 1. Strip protocol wrapper (canvastrack:// or moodlemobile://)
    if "://" in token_str:
        # Match token= parameter in query/fragment or path
        token_match = re.search(r"token=([^&#\s]+)", token_str, re.IGNORECASE)
        if token_match:
            token_str = token_match.group(1).strip()
        else:
            token_str = token_str.split("://", 1)[1].strip()

    # 2. Try base64 decoding
    try:
        # Add padding if missing
        missing_padding = len(token_str) % 4
        padded = token_str + ("=" * (4 - missing_padding)) if missing_padding else token_str
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore").strip()
        if ":::" in decoded:
            token_str = decoded
        elif re.fullmatch(r"[a-fA-F0-9]{32}", decoded):
            return decoded.lower()
    except Exception:
        pass

    # 3. Handle delimited string (<part1>:::<part2>...)
    if ":::" in token_str:
        parts = [p.strip() for p in token_str.split(":::") if p.strip()]
        # In Moodle tool_mobile launch:
        # Format is either <passport>:::<wstoken> (2 parts)
        # or <siteurl>:::<wstoken>:::<privatetoken> (3 parts)
        # In both cases, the wstoken is part index 1 or the 32-char hex string
        for part in reversed(parts):
            if re.fullmatch(r"[a-fA-F0-9]{32}", part):
                return part.lower()

    # 4. Direct 32-char hex token match
    clean_hex = re.findall(r"\b[a-fA-F0-9]{32}\b", token_str)
    if clean_hex:
        # Return the last valid hex match (usually wstoken)
        return clean_hex[-1].lower()

    # Fallback to trimmed input
    return token_str


def build_moodle_sso_url(
    domain_or_url: str,
    passport: str = "1",
    scheme: str = PROTOCOL_NAME,
) -> str:
    """Generate the Moodle mobile SSO launch URL for the given institution domain."""
    clean_domain = domain_or_url.strip().rstrip("/")
    if clean_domain.startswith("http://") or clean_domain.startswith("https://"):
        base = clean_domain
    else:
        base = f"https://{clean_domain}"

    return (
        f"{base}/admin/tool/mobile/launch.php?"
        f"service=moodle_mobile_app&passport={passport}&urlscheme={scheme}"
    )


def register_protocol_handler() -> bool:
    """Register the canvastrack:// URL protocol handler for the current user.

    Uses HKCU\\Software\\Classes\\canvastrack on Windows without requiring elevation.
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg

        protocol_key_path = rf"Software\Classes\{PROTOCOL_NAME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, protocol_key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:Canvas Track Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        # Target command line: invokes canvas-track auth-callback "%1"
        python_exe = sys.executable
        cmd_str = f'"{python_exe}" -m canvas_track.cli auth-callback "%1"'

        cmd_key_path = rf"{protocol_key_path}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as cmd_key:
            winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd_str)

        logger.info("Successfully registered '%s://' protocol handler in HKCU.", PROTOCOL_NAME)
        return True
    except Exception as e:
        logger.warning("Failed to register protocol handler in HKCU: %s", e)
        return False
