# Claude Desktop Custom Gateway Setup

A cross-platform Python script that routes Claude Desktop to any custom Anthropic-compatible API endpoint (e.g., Kimi, OpenRouter, local LLM).

## How It Works

Claude Desktop supports an enterprise gateway mode. When Ollama runs `ollama launch claude-desktop`, it creates a small config library that points Claude to Ollama's API. This script swaps those credentials for your own gateway — keeping everything else untouched.

## Prerequisites

- Python 3.7+
- [Ollama](https://ollama.com/download) installed and in your PATH
- `ollama launch claude-desktop` already run at least once on this machine
- A gateway that supports:
  - `GET /v1/models` — for model discovery
  - `POST /v1/messages` — Anthropic Messages API format (streaming)

## Quick Start

```bash
python setup-claude-gateway.py
```

The script will:
1. Check that Ollama is installed
2. Run `ollama launch claude-desktop` (or skip if already done)
3. Ask for your gateway Base URL, API Key, and Display Name
4. Write the config and create a backup of the original
5. Tell you to restart Claude Desktop

After restart, your gateway's models should appear in the Claude Desktop model picker.

## Supported Platforms

| Platform | Config Path |
|----------|-------------|
| Windows (legacy) | `%LOCALAPPDATA%\Claude-3p\configLibrary\` |
| Windows (MSIX/Store) | `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude-3p\configLibrary\` |
| macOS | `~/Library/Application Support/Claude-3p/configLibrary/` |
| Linux | `~/.config/Claude-3p/configLibrary/` |

The script auto-detects your OS and uses the correct path.

## Manual Setup (No Script)

If you prefer to do it manually — or you're asking an AI assistant to do it for you — follow these steps:

### Step 1: Ensure Ollama setup is done

Run this in your terminal:

```bash
ollama launch claude-desktop
```

This creates the `Claude-3p` directory and config files.

### Step 2: Locate the config library

Find your OS-specific `Claude-3p/configLibrary/` path from the table above.

### Step 3: Edit the gateway config

Open or create:

```
configLibrary/00000000-0000-4000-8000-000000000114.json
```

Write:

```json
{
  "disableDeploymentModeChooser": true,
  "inferenceGatewayApiKey": "YOUR_API_KEY",
  "inferenceGatewayAuthScheme": "bearer",
  "inferenceGatewayBaseUrl": "https://your-gateway.com/",
  "inferenceProvider": "gateway"
}
```

### Step 4: Update the config registry

Open or create:

```
configLibrary/_meta.json
```

Write:

```json
{
  "appliedId": "00000000-0000-4000-8000-000000000114",
  "entries": [
    {
      "id": "00000000-0000-4000-8000-000000000114",
      "name": "YourGatewayName"
    }
  ]
}
```

### Step 5: Restart Claude Desktop

Fully quit (tray icon → Quit), then relaunch.

## Limitations

- Claude Desktop's embedded Claude Code may cap context at 200k tokens for unknown models, even if your gateway reports a larger `context_length`. This is a client-side hardcoded limit.
- Web search, billing, and other Anthropic-cloud-only features are unavailable in third-party mode.

## Reverting to Ollama

The script creates a `.backup` file before writing. To restore:

1. Find the backup in `configLibrary/00000000-0000-4000-8000-000000000114.json.backup`
2. Copy it over the current `00000000-0000-4000-8000-000000000114.json`
3. Restart Claude Desktop

Or simply re-run `ollama launch claude-desktop` to reset to Ollama's defaults.

## License

MIT
