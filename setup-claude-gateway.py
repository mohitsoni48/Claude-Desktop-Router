#!/usr/bin/env python3
"""
Claude Desktop Custom Gateway Setup
====================================

Cross-platform setup script for routing Claude Desktop to any custom
Anthropic-compatible API gateway.

Prerequisites:
    - Python 3.7+
    - Ollama installed and in PATH
    - `ollama launch claude-desktop` already run at least once

OS Support:
    - Windows (MSIX and legacy installs)
    - macOS
    - Linux

Usage:
    python setup-claude-gateway.py
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on Windows to avoid UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Simple ANSI colors (works on Windows 10+, macOS, Linux)
# ---------------------------------------------------------------------------
class Colors:
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def info(msg: str):
    print(f"{Colors.CYAN}>{Colors.RESET} {msg}")


def success(msg: str):
    print(f"{Colors.GREEN}OK{Colors.RESET} {msg}")


def error(msg: str):
    print(f"{Colors.RED}ERR{Colors.RESET} {msg}")


def warn(msg: str):
    print(f"{Colors.YELLOW}WARN{Colors.RESET} {msg}")


def banner():
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  Claude Desktop Custom Gateway Setup{Colors.RESET}")
    print(f"  Route Claude Desktop to any Anthropic-compatible API")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    print()


# ---------------------------------------------------------------------------
# OS detection & path resolution
# ---------------------------------------------------------------------------

def detect_os() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    return "unknown"


def get_claude_3p_dir() -> Path:
    r"""
    Resolve the Claude-3p application data directory.

    Priority:
        Windows legacy -> %LOCALAPPDATA%\Claude-3p
        Windows MSIX   -> %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude-3p
        macOS          -> ~/Library/Application Support/Claude-3p
        Linux          -> ~/.config/Claude-3p
    """
    os_name = detect_os()
    home = Path.home()

    if os_name == "windows":
        local_appdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))

        # 1. Legacy direct path (Ollama launcher writes here)
        legacy = local_appdata / "Claude-3p"
        if legacy.exists():
            return legacy

        # 2. MSIX sandbox path (fallback for Store-only installs)
        packages_dir = local_appdata / "Packages"
        if packages_dir.exists():
            for pkg in packages_dir.glob("Claude_*"):
                candidate = pkg / "LocalCache" / "Roaming" / "Claude-3p"
                if candidate.exists():
                    return candidate

        # 3. Create legacy path as fallback
        return legacy

    elif os_name == "macos":
        return home / "Library" / "Application Support" / "Claude-3p"

    elif os_name == "linux":
        return home / ".config" / "Claude-3p"

    else:
        raise RuntimeError(f"Unsupported operating system: {platform.system()}")


# ---------------------------------------------------------------------------
# Ollama checks & launch
# ---------------------------------------------------------------------------

def check_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def run_ollama_launch() -> bool:
    info("Running: ollama launch claude-desktop")
    try:
        result = subprocess.run(
            ["ollama", "launch", "claude-desktop"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            warn(f"ollama launch exited with code {result.returncode}")
            if result.stderr:
                warn(result.stderr.strip())
            return False
        success("ollama launch completed")
        return True
    except FileNotFoundError:
        error("ollama command not found in PATH")
        return False
    except Exception as e:
        error(f"Failed to run ollama launch: {e}")
        return False


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------

CONFIG_ID = "00000000-0000-4000-8000-000000000114"


def read_existing_config(config_library: Path) -> dict:
    config_file = config_library / f"{CONFIG_ID}.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            error(f"Existing config is invalid JSON: {e}")
    return {}


def backup_existing(config_library: Path) -> Path | None:
    config_file = config_library / f"{CONFIG_ID}.json"
    if config_file.exists():
        backup = config_library / f"{CONFIG_ID}.json.backup"
        shutil.copy2(config_file, backup)
        return backup
    return None


def write_gateway_config(
    config_library: Path,
    base_url: str,
    api_key: str,
    name: str,
    auth_scheme: str = "bearer",
) -> None:
    config_library.mkdir(parents=True, exist_ok=True)

    # Preserve any extra fields from existing config
    existing = read_existing_config(config_library)
    gateway_config = {
        **existing,
        "inferenceGatewayApiKey": api_key,
        "inferenceGatewayAuthScheme": auth_scheme,
        "inferenceGatewayBaseUrl": base_url.rstrip("/") + "/" if base_url else base_url,
        "inferenceProvider": "gateway",
    }

    config_file = config_library / f"{CONFIG_ID}.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(gateway_config, f, indent=2)
        f.write("\n")

    meta_file = config_library / "_meta.json"
    meta = {
        "appliedId": CONFIG_ID,
        "entries": [
            {"id": CONFIG_ID, "name": name}
        ],
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def validate_api_key(key: str) -> bool:
    return len(key) >= 10


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def ask_input(prompt: str, default: str = "", password: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    if password:
        import getpass
        value = getpass.getpass(f"{prompt}{suffix}: ").strip()
        return value or default
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_confirm(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{default_str}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> int:
    banner()

    os_name = detect_os()
    info(f"Detected OS: {platform.system()}")

    # 1. Check Ollama
    if not check_ollama_installed():
        error("Ollama is not installed or not in PATH.")
        info("Please install Ollama first: https://ollama.com/download")
        return 1
    success("Ollama is installed")

    # 2. Run ollama launch
    if not ask_confirm("Run 'ollama launch claude-desktop' now?", default=True):
        info("Skipping ollama launch. Assuming it was already run.")
    else:
        if not run_ollama_launch():
            if not ask_confirm("Ollama launch may have failed. Continue anyway?", default=False):
                return 1

    # 3. Locate Claude-3p directory
    try:
        claude_3p_dir = get_claude_3p_dir()
    except RuntimeError as e:
        error(str(e))
        return 1

    info(f"Claude-3p directory: {claude_3p_dir}")

    if not claude_3p_dir.exists():
        warn("Claude-3p directory does not exist yet.")
        info("Creating directory...")
        claude_3p_dir.mkdir(parents=True, exist_ok=True)

    # 4. Prompt for gateway details
    print()
    print(f"{Colors.BOLD}--- Gateway Configuration ---{Colors.RESET}")

    base_url = ""
    while not validate_url(base_url):
        base_url = ask_input("Base URL (e.g. https://api.example.com/coding/)")
        if not validate_url(base_url):
            error("URL must start with http:// or https://")

    api_key = ""
    while not validate_api_key(api_key):
        api_key = ask_input("API Key", password=True)
        if not validate_api_key(api_key):
            error("API Key looks too short. Please provide a valid key.")

    name = ask_input("Gateway Display Name", default="Custom")

    # 5. Confirm & write
    print()
    print("Review:")
    print(f"  Base URL: {base_url}")
    print(f"  API Key:  {'*' * min(len(api_key), 8)}...")
    print(f"  Name:     {name}")
    print()

    if not ask_confirm("Write configuration?", default=True):
        info("Aborted by user.")
        return 0

    config_library = claude_3p_dir / "configLibrary"
    backup_path = backup_existing(config_library)
    if backup_path:
        info(f"Backup created: {backup_path}")

    write_gateway_config(config_library, base_url, api_key, name)
    success(f"Configuration written to {config_library}")

    # 6. Final instructions
    print()
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  SETUP COMPLETE{Colors.RESET}")
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    print("1. Fully quit Claude Desktop (tray icon -> Quit)")
    print("2. Kill any remaining Claude.exe in Task Manager")
    print("3. Relaunch Claude Desktop from Start Menu")
    print()
    print("Your custom gateway should appear in the model picker.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
