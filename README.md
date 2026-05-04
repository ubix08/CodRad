# Local Agent Server

A production-ready local AI coding assistant built on OpenHands SDK. Works without Docker - directly on your system.

## Features

- **Project Management** - Create and manage coding projects
- **Session History** - Multiple conversation sessions per project  
- **GitHub Import** - Clone repositories directly into projects
- **50+ Skills** - Built-in skills from OpenHands
- **WebSocket** - Real-time streaming responses
- **Flexible LLM** - OpenRouter, Anthropic, OpenAI, Groq support
- **Security** - Action confirmation, sandboxing, OAuth ready
- **Production Ready** - Metrics, monitoring, hooks

## Requirements

- Python 3.10+
- Linux/macOS/Windows (WSL)
- API key (OpenRouter, Anthropic, OpenAI, or Groq)

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/ubix08/CodRad.git
cd CodRad
pip install -r requirements.txt
```

### 2. Configure

```bash
cp local_agent_server/.env.example local_agent_server/.env
```

Edit `.env` and add your API key:

```bash
# Option 1: OpenRouter (recommended - many models)
OPENROUTER_API_KEY=sk-or-your-key-here

# Option 2: Anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Option 3: OpenAI  
# OPENAI_API_KEY=sk-your-key-here

# Option 4: Groq
# GROQ_API_KEY=your-key-here
```

### 3. Run

```bash
# Default port 8000
./start.sh

# Or custom port
./start.sh 9000
```

Server runs at: **http://localhost:8000**
API docs: **http://localhost:8000/docs**

## Installation (System-wide)

```bash
# Install
pip install -e .

# Run
local-agent-server
# or
python -m local_agent_server.server:main
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GROQ_API_KEY` | Groq API key | - |
| `LLM_PROVIDER` | Provider name | openrouter |
| `LLM_MODEL` | Model name | openrouter/google/gemini-2.0-flash-001 |
| `AUTH_ENABLED` | Enable auth | false |
| `AUTH_SECRET` | Auth secret | auto-generated |
| `PROJECTS_ROOT` | Projects folder | ~/agent-projects |
| `WORKSPACE_ROOT` | Workspace folder | ~/agent-workspaces |
| `CONFIRMATION_POLICY` | confirm_risky/always_confirm/never_confirm | never_confirm |

## Project Structure

Projects are stored in `~/agent-projects/`:

```
~/agent-projects/
├── my-project/
│   ├── src/
│   ├── tests/
│   ├── AGENTS.md           # Project description
│   ├── .agents/          # Custom skills
│   │   └── skills/
│   └── .project/
│       ├── config.yaml
│       └── sessions/
│           ├── sess_abc123/
│           │   ├── meta.json
│           │   └── messages.json
```

## API Endpoints

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| GET | `/api/projects/{id}` | Get project |
| DELETE | `/api/projects/{id}` | Delete project |
| POST | `/api/projects/import/github` | Import GitHub repo |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/sessions` | List sessions |
| POST | `/api/projects/{id}/sessions` | Create session |
| GET | `/api/projects/{id}/sessions/{sid}` | Get session |
| DELETE | `/api/projects/{id}/sessions/{sid}` | Delete session |
| POST | `/api/projects/{id}/sessions/{sid}/run` | Run agent |
| POST | `/api/projects/{id}/sessions/{sid}/messages` | Send message |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Server metrics |
| WS | `/ws/{session_id}` | WebSocket |

## Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

Access UI at: http://localhost:5173

## Docker (Optional)

```bash
docker build -t local-agent .
docker run -p 8000:8000 -v ~/agent-projects:/home/openhands/agent-projects local-agent
```

## Development

```bash
# Virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run with auto-reload
python -m uvicorn local_agent_server.server:app --reload

# Run tests
pytest

# Code style
ruff check . --fix
ruff format .
```

## Production Checklist

- [ ] Set `AUTH_ENABLED=true` and configure `AUTH_SECRET`
- [ ] Use reverse proxy (nginx/Caddy)
- [ ] Set up SSL/TLS
- [ ] Configure monitoring
- [ ] Set up logging
- [ ] Configure backups for projects folder

## License

MIT