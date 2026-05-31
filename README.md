# Claude Desktop Custom Gateway Setup

A cross-platform Python script that routes Claude Desktop to any custom Anthropic-compatible API endpoint (e.g., Kimi, OpenRouter, local LLM) — **no Ollama required**.

## How It Works

Claude Desktop has an undocumented "enterprise gateway" (3P) mode. When activated, it routes all inference through a custom API endpoint instead of `api.anthropic.com`. This script creates the minimal config files that activate this mode and point it at your gateway.

For non-Anthropic gateways, the script uses the `inferenceModels` config field to bypass model discovery and present your gateway's model as an Anthropic-compatible one.

## Prerequisites

- Python 3.7+
- Claude Desktop installed
- A gateway that supports:
  - `GET /v1/models` — for model discovery
  - `POST /v1/messages` — Anthropic Messages API format (streaming)

## Quick Start

### Interactive Mode

```bash
python setup-claude-gateway.py
```

The script will:
1. Auto-detect your OS and locate the Claude-3p config directory
2. Back up your existing config
3. Ask for your gateway Base URL, API Key, and Anthropic Model ID
4. Write the config files
5. Tell you to restart Claude Desktop

### Non-Interactive Mode (AI Assistants / CI)

```bash
python setup-claude-gateway.py \
  --base-url https://api.kimi.com/coding/ \
  --api-key sk-xxxxxxxxx \
  --model-id claude-sonnet-4-5
```

After restart, your gateway's model should appear in the Claude Desktop model picker with the Anthropic model ID you specified.

## Choosing a Model ID

Claude Desktop v1.96+ validates model IDs from custom gateways. Use `inferenceModels` to bypass discovery and present any model as an Anthropic one:

| What you want | `--model-id` value |
|---------------|-------------------|
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` |
| Claude 4 Sonnet | `claude-sonnet-4-20250514` |
| Claude 3 Opus | `claude-3-opus-20240229` |

The model ID you choose determines how Claude Desktop labels and treats the model (context limit, capabilities, etc.). The actual API calls are forwarded to your gateway unchanged.

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

### Step 1: Locate the config directory

Find your OS-specific `Claude-3p/` path from the table above. Create it if it doesn't exist.

### Step 2: Create the deployment mode flag

Create or edit:

```
Claude-3p/claude_desktop_config.json
```

If the file already exists, **preserve all existing fields** and only add/ensure:

```json
{
  "deploymentMode": "3p"
}
```

If the file does not exist, create it with just:

```json
{ "deploymentMode": "3p" }
```

### Step 3: Create the gateway config

Create the `configLibrary` directory inside `Claude-3p/`, then create:

```
configLibrary/00000000-0000-4000-8000-000000000114.json
```

Write:

```json
{
  "inferenceProvider": "gateway",
  "inferenceCredentialKind": "static",
  "inferenceGatewayApiKey": "YOUR_API_KEY",
  "inferenceGatewayAuthScheme": "bearer",
  "inferenceGatewayBaseUrl": "https://your-gateway.com/",
  "inferenceModels": [
    {
      "name": "claude-sonnet-4-5",
      "labelOverride": "claude-sonnet-4-5"
    }
  ]
}
```

### Step 4: Create the config registry

Create:

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
      "name": "claude-sonnet-4-5"
    }
  ]
}
```

### Step 5: Restart Claude Desktop

Fully quit (tray icon → Quit), then relaunch.

## Reverting to Original Claude (Anthropic)

### Via Script

```bash
python setup-claude-gateway.py --restore
```

### Manually

Remove or edit these files to revert:

1. In `Claude-3p/claude_desktop_config.json`, remove the `"deploymentMode": "3p"` line
2. Delete the `Claude-3p/configLibrary/` directory entirely

Then fully restart Claude Desktop.

## Limitations

- Claude Desktop's embedded Claude Code may cap context at 200k tokens for unknown models, even if your gateway reports a larger `context_length`. This is a client-side hardcoded limit.
- Web search, billing, and other Anthropic-cloud-only features are unavailable in third-party mode.

## License

MIT
