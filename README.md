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

### How SARs Works
The SARs layer acts as an intelligent intermediary that:
- **Translates Model Names**: Maps Anthropic-style model identifiers to provider-specific tags via a configurable `model_map`.
- **Abstracts Provider Logic**: Routes requests to different backend clients (e.g., Ollama, OpenAI, Groq) based on the target model.
- **Unified Key Management**: Applies consistent rotation and retry logic regardless of the underlying AI provider.

### Extending the Gateway
Because of this extensible design, adding new AI providers is straightforward:
1. **Implement a new Client**: Create a provider-specific HTTP client.
2. **Update Model Map**: Add new mappings in `config.json` to link model names to the new provider's endpoints.
3. **Configure Endpoints**: Set the base URL for the new provider in the configuration.

This enables seamless integration of various LLM backends while maintaining a single, stable interface for Claude Code.

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
