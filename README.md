# EverFlow

EverFlow is a cross-platform desktop application (macOS/Windows) that acts as a local proxy server, routing requests to the Ollama cloud API with automatic key rotation. It enables uninterrupted usage of Claude Code by managing 100+ API keys and rotating them when rate limits are hit.

## Features
- **Automatic Key Rotation**: Rotates API keys when rate limits (HTTP 429) or invalid keys (HTTP 401/403) are encountered.
- **Sticky Index Rotation**: Maintains a deterministic rotation order to maximize key utility.
- **Web Dashboard**: Monitor proxy status, manage API keys, and view request logs in real-time.
- **System Tray Integration**: Convenient access to the dashboard and app control.
- **Cross-Platform**: Fully compatible with macOS and Windows.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+

### Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/srisuryakumar/EverFlow.git
   cd EverFlow
   ```

2. **Setup Virtual Environment**:
   - **macOS/Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```
   Once running, use the system tray icon to open the **Dashboard** at `http://127.0.0.1:8000/dashboard/`.

---

## ⚙️ Configuration & Data

EverFlow stores its configuration and API keys in platform-specific application data folders.

### App Data Locations
| OS | Path |
| :--- | :--- |
| **macOS** | `~/Library/Application Support/EverFlow/` |
| **Windows** | `%APPDATA%\EverFlow\` |

### Key Files

#### `config.json`
Stores application settings, including the proxy port and rotation strategy. 
**To change the proxy port**, locate this file in the paths above and modify the `proxy.port` value. Restart EverFlow after saving.

#### `keys.json`
Stores your API keys and status. You can add keys via the Dashboard or manually edit this file.

---

## 🛠 Configuring Claude Code

To route Claude Code through EverFlow, set the following environment variables in your shell. **CRITICAL: The port in the URL below must match the port configured in `config.json`.**

#### macOS (zsh/bash)
```bash
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:8000
```

#### Windows (PowerShell)
```powershell
$env:ANTHROPIC_AUTH_TOKEN = "ollama"
$env:ANTHROPIC_API_KEY = ""
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
```

Then launch Claude Code:
```bash
ollama launch claude -- --model claude-sonnet-4-6
```

---

## ✅ Verification

### 1. Health Check
Once the app is running, visit: `http://localhost:8000/health` (replace 8000 with your port). You should see a JSON response indicating the proxy is running.

### 2. Dashboard
Open the dashboard via the system tray icon or at: `http://localhost:8000/dashboard/`.

---

## 🏗 Architecture & Extensibility

EverFlow utilizes a **Smart API Routing (SARs)** layer that decouples the client request from the backend provider. This architecture allows EverFlow to function as a unified gateway between Claude Code and multiple AI model providers.

### How SARS Works
The SARs layer acts as an intelligent intermediary that transforms a generic request into a provider-specific call:
1. **Request Interception**: EverFlow receives a request from Claude Code (e.g., specifying model `claude-3-5-sonnet`).
2. **Map Lookup**: It checks the `model_map` in `config.json` to find the corresponding provider tag (e.g., `claude-3-5-sonnet` $\rightarrow$ `gemma4:31b-cloud`).
3. **Provider Routing**: Based on the target tag, the router selects the appropriate provider client (e.g., Ollama, OpenAI, Gemini, or Grok) and forwards the request to the provider's specific base URL.

### Provider-Agnostic Routing
A key design principle of EverFlow is that **routing is determined by the model identifier, not by environment variables.** 

While `ANTHROPIC_BASE_URL` is used to connect Claude Code to EverFlow, the decision of which provider (OpenAI, Groq, etc.) actually processes the request is handled entirely within EverFlow's internal mapping. This enables:
- **Dynamic Switching**: Change the backend provider for any model instantly via the dashboard without restarting your terminal or changing system variables.
- **Granular Control**: Route different model requests to different providers simultaneously (e.g., fast tasks to Groq, complex tasks to OpenAI).

### Extending the Gateway
EverFlow is designed to be provider-agnostic. Adding new AI providers (like OpenAI, Gemini, or Grok) follows a simple pattern:
1. **Implement a Provider Client**: Create a new HTTP client tailored to the provider's API structure.
2. **Expand Configuration**: Add the provider's base URL to the `providers` section of `config.json`.
3. **Update Model Map**: Map your desired Anthropic-style model names to the new provider's specific model tags.

This architecture transforms EverFlow from a simple proxy into a powerful AI orchestration layer, maintaining a single, stable interface for the user while leveraging the best models from across the AI ecosystem.

---

## Testing
Run the test suite using pytest:
```bash
pytest tests/ -v
```

For a comprehensive end-to-end integration test:
```bash
python test_complete.py
```

## Build Process
To create a distributable application:
- **macOS**: `./build.sh`
- **Windows**: `build.bat`
