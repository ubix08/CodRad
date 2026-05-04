# Local Agent Server

A production-ready local AI coding assistant built on OpenHands SDK.

## Features

- **Project Management** - Create and manage coding projects
- **Session History** - Multiple conversation sessions per project  
- **GitHub Integration** - Import repositories directly
- **Skills** - 50+ built-in skills from OpenHands
- **WebSocket** - Real-time streaming
- **Flexible LLM** - OpenRouter, Anthropic, OpenAI support

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-repo/CodRad.git
cd CodRad
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp local_agent_server/.env.example local_agent_server/.env
# Edit .env with your API keys
```

### 3. Start Server

```bash
# Backend only
python -m uvicorn local_agent_server.server:app --host 0.0.0.0 --port 8000

# Or use the start script
chmod +x start.sh
./start.sh
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `LLM_PROVIDER` | LLM provider (openrouter/anthropic/openai) | openrouter |
| `LLM_MODEL` | Model name | openrouter/google/gemini-2.0-flash-001 |
| `AUTH_ENABLED` | Enable authentication | false |
| `PROJECTS_ROOT` | Projects directory | ~/agent-projects |
| `WORKSPACE_ROOT` | Workspace directory | ~/agent-workspaces |

## Project Structure

Projects are stored in `~/agent-projects/`:

```
~/agent-projects/
├── my-project/
│   ├── src/
│   ├── .agents/
│   │   └── skills/
│   ├── AGENTS.md
│   └── .project/
│       ├── config.yaml
│       └── sessions/
│           ├── sess_abc123/
│           │   ├── meta.json
│           │   └── messages.json
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Server metrics |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| GET | `/api/projects/{id}` | Get project |
| DELETE | `/api/projects/{id}` | Delete project |
| GET | `/api/projects/{id}/sessions` | List sessions |
| POST | `/api/projects/{id}/sessions` | Create session |
| POST | `/api/projects/{id}/sessions/{session_id}/run` | Run session |
| POST | `/api/projects/{id}/sessions/{session_id}/messages` | Send message |
| POST | `/api/projects/import/github` | Import GitHub repo |

## Frontend

The frontend is in `/frontend`:

```bash
cd frontend
npm install
npm run dev
```

Access at: `http://localhost:5173`

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run server with auto-reload
python -m uvicorn local_agent_server.server:app --reload

# Run tests
pytest

# Check code
ruff check .
```

## Docker

```bash
docker build -t local-agent .
docker run -p 8000:8000 -v ~/agent-projects:/home/openhands/agent-projects local-agent
```

## License

MIT