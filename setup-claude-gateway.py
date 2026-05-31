#!/usr/bin/env python3
r"""
Claude Desktop Custom Gateway Setup — Standalone Edition
===========================================================

Sets up Claude Desktop to use any Anthropic-compatible API gateway
WITHOUT requiring Ollama. This reverse-engineers and replicates what
`ollama launch claude-desktop` does, then patches the gateway URL/key.

For non-Anthropic gateways (Kimi, OpenRouter, etc.), the script uses the
`inferenceModels` config field to bypass model discovery and present the
gateway's model as an Anthropic-compatible one.

Prerequisites:
    - Python 3.7+
    - Claude Desktop installed

OS Support:
    - Windows (legacy %LOCALAPPDATA%\Claude-3p and MSIX sandbox)
    - macOS (~/Library/Application Support/Claude-3p)
    - Linux (~/.config/Claude-3p)

Usage (interactive):
    python setup-claude-gateway.py

Usage (non-interactive):
    python setup-claude-gateway.py \
        --base-url https://api.kimi.com/coding/ \
        --api-key sk-xxxxxxxx \
        --model-id claude-sonnet-4-5

Usage (restore stock Anthropic mode):
    python setup-claude-gateway.py --restore
"""

import argparse
import json
import os
import platform
import shutil
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
    print(f"  Standalone — no Ollama required")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    print()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIG_ID = "00000000-0000-4000-8000-000000000114"

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

        # 1. Legacy direct path
        legacy = local_appdata / "Claude-3p"
        if legacy.exists():
            return legacy

        # 2. MSIX sandbox path (Store installs)
        packages_dir = local_appdata / "Packages"
        if packages_dir.exists():
            for pkg in packages_dir.glob("Claude_*"):
                candidate = pkg / "LocalCache" / "Roaming" / "Claude-3p"
                if candidate.exists():
                    return candidate

        # 3. Default to legacy path (create if needed)
        return legacy

    elif os_name == "macos":
        return home / "Library" / "Application Support" / "Claude-3p"

    elif os_name == "linux":
        return home / ".config" / "Claude-3p"

    else:
        raise RuntimeError(f"Unsupported operating system: {platform.system()}")


def get_backup_dir() -> Path:
    """Return the directory where we store backups of original configs."""
    os_name = detect_os()
    home = Path.home()
    if os_name == "windows":
        local_appdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return local_appdata / "ClaudeGatewayPatchBackup"
    elif os_name == "macos":
        return home / "Library" / "Application Support" / "ClaudeGatewayPatchBackup"
    else:
        return home / ".config" / "ClaudeGatewayPatchBackup"


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------

def read_json(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            warn(f"Could not parse {path}: {e}")
    return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def backup_file(src: Path, backup_dir: Path) -> Path | None:
    if not src.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / src.name
    shutil.copy2(src, dst)
    return dst


def backup_directory(src: Path, backup_dir: Path) -> Path | None:
    if not src.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / src.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Core patching logic
# ---------------------------------------------------------------------------

def patch_claude_desktop_config(claude_3p_dir: Path) -> None:
    """
    Ensure claude_desktop_config.json has deploymentMode: "3p" while
    preserving any existing user preferences.
    """
    config_path = claude_3p_dir / "claude_desktop_config.json"
    existing = read_json(config_path)
    existing["deploymentMode"] = "3p"
    write_json(config_path, existing)


def write_gateway_config(
    config_library: Path,
    base_url: str,
    api_key: str,
    model_id: str,
    auth_scheme: str = "bearer",
) -> None:
    """Write the gateway config and meta registry."""
    config_library.mkdir(parents=True, exist_ok=True)

    # Preserve any extra fields from existing config
    existing = read_json(config_library / f"{CONFIG_ID}.json")
    gateway_config = {
        **existing,
        "inferenceProvider": "gateway",
        "inferenceCredentialKind": "static",
        "inferenceGatewayApiKey": api_key,
        "inferenceGatewayAuthScheme": auth_scheme,
        "inferenceGatewayBaseUrl": base_url.rstrip("/") + "/" if base_url else base_url,
        "inferenceModels": [
            {
                "name": model_id,
                "labelOverride": model_id,
            }
        ],
    }
    write_json(config_library / f"{CONFIG_ID}.json", gateway_config)

    meta = {
        "appliedId": CONFIG_ID,
        "entries": [
            {"id": CONFIG_ID, "name": model_id}
        ],
    }
    write_json(config_library / "_meta.json", meta)


def apply_patch(claude_3p_dir: Path, base_url: str, api_key: str, model_id: str, auth_scheme: str) -> None:
    """Apply the full gateway patch to a single Claude-3p directory."""
    claude_3p_dir.mkdir(parents=True, exist_ok=True)
    patch_claude_desktop_config(claude_3p_dir)
    config_library = claude_3p_dir / "configLibrary"
    write_gateway_config(config_library, base_url, api_key, model_id, auth_scheme)


# ---------------------------------------------------------------------------
# Restore logic
# ---------------------------------------------------------------------------

def restore_stock_config(claude_3p_dir: Path) -> bool:
    """Restore stock Anthropic config by removing deploymentMode and configLibrary."""
    restored = False

    # 1. Remove deploymentMode from claude_desktop_config.json
    desktop_target = claude_3p_dir / "claude_desktop_config.json"
    if desktop_target.exists():
        data = read_json(desktop_target)
        if "deploymentMode" in data:
            data.pop("deploymentMode", None)
            write_json(desktop_target, data)
            restored = True

    # 2. Delete configLibrary entirely
    lib_target = claude_3p_dir / "configLibrary"
    if lib_target.exists():
        shutil.rmtree(lib_target)
        restored = True

    return restored


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def validate_api_key(key: str) -> bool:
    return len(key) >= 10


# ---------------------------------------------------------------------------
# Prompt helpers (for interactive mode)
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
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Route Claude Desktop to any Anthropic-compatible API gateway. No Ollama required.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Interactive mode
  %(prog)s --base-url https://api.kimi.com/coding/ --api-key sk-xxx --model-id claude-sonnet-4-5
  %(prog)s --restore                          # Revert to stock Anthropic mode
        """.strip(),
    )
    parser.add_argument("--base-url", help="Gateway base URL (e.g. https://api.example.com/coding/)")
    parser.add_argument("--api-key", help="API key for the gateway")
    parser.add_argument("--model-id", default="claude-sonnet-4-5", help="Anthropic model ID to present (default: claude-sonnet-4-5)")
    parser.add_argument("--auth-scheme", default="bearer", help="Auth scheme: bearer, basic, ... (default: bearer)")
    parser.add_argument("--restore", action="store_true", help="Restore original stock Anthropic config")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    banner()

    os_name = detect_os()
    info(f"Detected OS: {platform.system()}")

    try:
        claude_3p_dir = get_claude_3p_dir()
    except RuntimeError as e:
        error(str(e))
        return 1

    info(f"Claude-3p directory: {claude_3p_dir}")
    backup_dir = get_backup_dir()

    # ------------------------------------------------------------------
    # RESTORE MODE
    # ------------------------------------------------------------------
    if args.restore:
        info("Restoring stock Anthropic configuration...")

        paths_to_restore = [claude_3p_dir]
        if os_name == "windows":
            local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            packages_dir = local_appdata / "Packages"
            if packages_dir.exists():
                for pkg in packages_dir.glob("Claude_*"):
                    msix_claude_3p = pkg / "LocalCache" / "Roaming" / "Claude-3p"
                    if msix_claude_3p.exists():
                        paths_to_restore.append(msix_claude_3p)

        any_restored = False
        for p in paths_to_restore:
            if restore_stock_config(p):
                success(f"Restored: {p}")
                any_restored = True

        if any_restored:
            print()
            print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
            print(f"{Colors.BOLD}  RESTORE COMPLETE{Colors.RESET}")
            print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
            print("1. Fully quit Claude Desktop (tray icon → Quit)")
            print("2. Kill any remaining Claude.exe / Claude processes")
            print("3. Relaunch Claude Desktop from Start Menu / Applications")
            print()
            print("Claude Desktop will now connect to Anthropic's cloud.")
        else:
            info("Already in stock Anthropic mode. Nothing to restore.")
        return 0

    # ------------------------------------------------------------------
    # PATCH MODE
    # ------------------------------------------------------------------
    base_url = args.base_url or ""
    api_key = args.api_key or ""

    if not base_url or not api_key:
        print(f"{Colors.BOLD}--- Gateway Configuration ---{Colors.RESET}")

    while not validate_url(base_url):
        base_url = ask_input("Base URL (e.g. https://api.example.com/coding/)")
        if not validate_url(base_url):
            error("URL must start with http:// or https://")

    while not validate_api_key(api_key):
        api_key = ask_input("API Key", password=True)
        if not validate_api_key(api_key):
            error("API Key looks too short. Please provide a valid key.")

    model_id = args.model_id
    if not args.base_url:
        model_input = ask_input("Anthropic Model ID", default="claude-sonnet-4-5")
        if model_input:
            model_id = model_input

    auth_scheme = args.auth_scheme
    if not args.base_url:
        scheme_input = ask_input("Auth Scheme", default="bearer")
        if scheme_input:
            auth_scheme = scheme_input

    # Confirm
    print()
    print("Review:")
    print(f"  Base URL: {base_url}")
    print(f"  API Key:  {'*' * min(len(api_key), 8)}...")
    print(f"  Model ID: {model_id}")
    print(f"  Auth:     {auth_scheme}")
    print()

    if not args.base_url:
        if not ask_confirm("Write configuration?", default=True):
            info("Aborted by user.")
            return 0

    # Backup existing state
    claude_3p_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    desktop_backup = backup_file(claude_3p_dir / "claude_desktop_config.json", backup_dir)
    if desktop_backup:
        info(f"Backup created: {desktop_backup}")

    lib_backup = backup_directory(claude_3p_dir / "configLibrary", backup_dir)
    if lib_backup:
        info(f"Backup created: {lib_backup}")

    # Apply patch
    apply_patch(claude_3p_dir, base_url, api_key, model_id, auth_scheme)
    success(f"Configuration written to {claude_3p_dir}")

    # Also patch MSIX path on Windows if it exists
    if os_name == "windows":
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        packages_dir = local_appdata / "Packages"
        if packages_dir.exists():
            for pkg in packages_dir.glob("Claude_*"):
                msix_claude_3p = pkg / "LocalCache" / "Roaming" / "Claude-3p"
                if msix_claude_3p.exists():
                    info(f"Also patching MSIX path: {msix_claude_3p}")
                    apply_patch(msix_claude_3p, base_url, api_key, model_id, auth_scheme)
                    success(f"MSIX path patched: {msix_claude_3p}")

    # Final instructions
    print()
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  SETUP COMPLETE{Colors.RESET}")
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    print("1. Fully quit Claude Desktop (tray icon → Quit)")
    print("2. Kill any remaining Claude.exe / Claude processes")
    print("3. Relaunch Claude Desktop from Start Menu / Applications")
    print()
    print("Your custom gateway should appear in the model picker.")
    print()
    print(f"Run with {Colors.BOLD}--restore{Colors.RESET} to revert to Anthropic's cloud.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
