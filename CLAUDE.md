# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EverFlow is a cross-platform desktop application (macOS/Windows) that acts as a local proxy server, routing requests to the Ollama cloud API with automatic key rotation. It enables uninterrupted usage of Claude Code by managing 100+ API keys and rotating them when rate limits are hit.

## Quick Commands

```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Run in development
python main.py

# Run tests
pytest tests/ -v              # All tests
pytest tests/test_rotator.py -v  # Specific test file
pytest tests/ --cov=src       # With coverage
python test_complete.py       # Comprehensive integration test

# Build distributable
./build.sh          # macOS
build.bat           # Windows

# Dashboard (when running)
http://127.0.0.1:8000/dashboard/
```

## Architecture

### Application Flow (main.py → src/app.py)

```
main.py → EverFlowApp.run()
  ├─ ConfigManager (loads config.json)
  ├─ KeyStore (loads keys.json)
  ├─ KeyRotator (sticky index-based rotation)
  ├─ ProxyRouter (retry engine)
  ├─ ProxyServer (FastAPI on port 8000)
  └─ TrayIcon (system tray menu)
```

### Core Modules

**src/proxy/** — Request routing engine
- `server.py`: FastAPI app running in daemon thread. Endpoints: `/v1/messages`, `/v1/models`, `/health`
- `router.py`: Retry loop with key rotation. Translates Anthropic model names → Ollama models via `MODEL_MAP`
- `ollama_client.py`: Async httpx client for ollama.com/v1/messages
- `detector.py`: Classifies HTTP responses into ErrorType (SUCCESS, RATE_LIMITED, KEY_INVALID, etc.)

**src/keys/** — Key management
- `store.py`: Thread-safe persistent storage (keys.json). Atomic writes via temp file + os.replace
- `rotator.py`: Deterministic sticky index-based key selection

**src/dashboard/** — Web UI
- `api.py`: FastAPI routes (`/dashboard/summary`, `/dashboard/keys`, `/dashboard/logs`, `/dashboard/chart/rpm`)
- `index.html`: Single-file SPA with vanilla JS, auto-refresh every 3s

**src/config/** — Configuration
- `manager.py`: Dot-notation access (`config.get("rotation.max_retries")`). Deep-merge with defaults on load

**src/models/** — Data classes
- `api_key.py`: APIKey dataclass with `is_available()`, `masked_key()`, `to_dict()`, `from_dict()`
- `enums.py`: KeyStatus, ErrorType, RequestOutcome
- `request_log.py`: RequestLog for dashboard history

**src/tray/** — System tray
- `icon.py`: pystray icon with menu (Open Dashboard, Quit). Blocking `run()` call

### Request Flow

1. Claude Code → POST `/v1/messages` (Anthropic SDK format)
2. `ProxyRouter.route()` translates model name via `MODEL_MAP`
3. `KeyRotator.get_next_key()` selects key (excludes already-tried keys)
4. `OllamaClient.call()` makes async HTTP request
5. `ResponseDetector.classify()` categorizes response
6. On rate limit (429): mark key exhausted, wait, retry with next key
7. On invalid key (401/403): mark invalid, rotate immediately
8. On success: record stats, return response

### Error Handling

- `AllKeysExhaustedException`: All keys unavailable → return 529 to client
- `MaxRetriesExceededException`: Retry limit hit → return 500
- Bad request (400): Pass through to client without retry

## File Locations

```
EverFlow/
├── main.py              # Entry point
├── EverFlow.spec    # PyInstaller config
├── requirements.txt     # Dependencies
├── build.sh / build.bat # Build scripts
├── dashboard/
│   └── index.html       # Single-file SPA
├── src/
│   ├── app.py           # Main orchestrator
│   ├── platform_utils.py  # Cross-platform paths
│   ├── exceptions.py      # Custom exceptions
│   ├── config/
│   │   └── manager.py     # ConfigManager
│   ├── keys/
│   │   ├── store.py       # KeyStore (persistence)
│   │   └── rotator.py     # KeyRotator (strategies)
│   ├── proxy/
│   │   ├── server.py      # ProxyServer (FastAPI)
│   │   ├── router.py      # ProxyRouter (retry engine)
│   │   ├── detector.py    # ResponseDetector
│   │   └── ollama_client.py
│   ├── dashboard/
│   │   └── api.py         # Dashboard routes
│   ├── models/
│   │   ├── api_key.py     # APIKey dataclass
│   │   ├── request_log.py # RequestLog
│   │   └── enums.py       # Enums
│   └── tray/
│       └── icon.py        # TrayIcon
└── tests/
    └── test_rotator.py    # Rotator unit tests
```

### App Data (platform-specific)

- **macOS**: `~/Library/Application Support/EverFlow/`
- **Windows**: `%APPDATA%\EverFlow\`

Files: `config.json`, `keys.json` (never commit)

## Testing

```bash
# All tests
pytest tests/ -v

# Single test file
pytest tests/test_rotator.py -v

# Test with coverage
pytest tests/ --cov=src

# Run specific test function
pytest tests/test_rotator.py::test_sticky_sequential_order -v

# Run integration test
python test_complete.py
```

Test files use fresh in-memory stores per test via fixtures that clear `keys.json` and `config.json`.

**Complete Integration Testing**:
The `test_complete.py` script provides comprehensive end-to-end testing of all components:
- Platform utilities and path resolution
- API key management and storage
- Configuration loading
- Ollama client functionality
- Response detection and classification
- Key rotation strategies
- Proxy routing logic

**Development Workflow**:
1. Start with `python main.py` to launch the application
2. Use the system tray icon to access the dashboard
3. Add API keys through the dashboard interface
4. Configure Claude Code environment variables as shown below
5. Test routing by making requests through Claude Code

## Build Process

PyInstaller bundles:
- `dashboard/index.html` → served at `/dashboard/`
- `assets/logo.png` → tray icon
- Hidden imports: uvicorn submodules, pywebview, pystray backends

Output:
- macOS: `dist/EverFlow.app`
- Windows: `dist/EverFlow.exe`

## Claude Code Configuration

To route Claude Code through EverFlow:

```bash
# macOS (add to ~/.zshrc or ~/.bashrc)
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:8000

# Windows PowerShell
$env:ANTHROPIC_AUTH_TOKEN = "ollama"
$env:ANTHROPIC_API_KEY = ""
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
```

Then: `ollama launch claude -- --model claude-sonnet-4-6` (model translated to `glm-5:cloud`)

## Key Design Decisions

- **Daemon thread for server**: FastAPI runs in background so tray icon can block on main thread (macOS requirement)
- **Atomic file writes**: All persistence uses temp file + `os.replace()` to prevent corruption
- **Thread-safe operations**: `threading.RLock()` protects all shared state in KeyStore, ConfigManager, ProxyRouter
- **No external JS/CSS**: Dashboard is fully self-contained (only Google Fonts import)
- **Model translation layer**: Anthropic SDK model names → Ollama cloud models via `MODEL_MAP` in router.py
- **Cross-platform support**: Uses platform-specific paths and build configurations
- **Single-file dashboard**: Entire UI in one HTML file for easy bundling

## Development Tips

- **Hot reload**: The FastAPI server supports hot reload. Use `uvicorn src.proxy.server:app --reload` for development
- **Debug mode**: Set `DEBUG=true` in environment to enable detailed logging
- **API testing**: Use curl to test the proxy: `curl -X POST http://localhost:8000/v1/messages -H "Content-Type: application/json" -d '{"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "Hello"}]}'`
- **Dashboard API**: Access dashboard endpoints directly: `curl http://localhost:8000/dashboard/summary`

## Troubleshooting

- **Port conflicts**: Change port in config or use `--port` flag when running
- **Tray icon issues**: On macOS, ensure app has accessibility permissions
- **Build failures**: Clean build directory: `rm -rf build/ dist/` before rebuilding
- **Key validation**: Ollama API keys should start with `ollama_` and be 24+ characters