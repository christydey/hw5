# Campus Customs: Multi-Agent Operations Desk (Homework 5)

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) works the open tickets of a small Yale apparel shop. Shop data comes only through an MCP server. A FastAPI backend runs the team and holds the human-approval queue, and a React dashboard lets you watch the agents and approve payments. Agents can research, check and *propose*. Only a human can approve a payment, and the app never lets cash go negative.

```
React dashboard (frontend/, :5173)
        │  HTTP
FastAPI backend (backend/main.py, :8000) ── PydanticAI agents (gpt-6-luna via Portkey)
        │  MCP over stdio
MCP server (mcp_server/server.py) ── data/campus_customs_new.db   (working copy)
                                       data/campus_customs.db       (original, read-only)
```

## Repository layout

| Path | What it is |
|---|---|
| `mcp_server/` | FastMCP server with 13 tools (10 read, 3 backend-only signed writes). See `mcp_server/README.md`. |
| `backend/` | Agents (`agents.py`, `team.py`), prompts (`prompts/*.md`), shared types (`models.py`), API (`main.py`), MCP client (`mcp_bridge.py`), audit trail (`audit.py`), offline checks (`check_setup.py`). |
| `frontend/` | React + Vite + TypeScript dashboard. |
| `data/` | `campus_customs.db` (the original, never modified) and `campus_customs_new.db` (the working copy the app reads and writes). |
| `output/` | Homework deliverables: `harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `github_url.txt`, plus Problem 9 screenshots and evidence. |
| `.mcp.json` | MCP server config for Claude Code (also read by the backend to launch the server). |
| `AI_prompts.md` | Log of the prompts used to build the project. |

> **Note on the committed working database.** `data/campus_customs_new.db` is committed in its **post-Problem 9 state**: all three tickets resolved, two payments recorded, checking at $160. Reset it (below) before doing your own run.

## 1. Install

You need Python 3.12 or newer (built with 3.14), Node.js 20 or newer (built with Node 24), and a Portkey API key.

```bash
git clone <this-repo-url> hw5 && cd hw5

# Python dependencies (MCP server + backend)
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

## 2. Configure your `.env`

```bash
cp .env.example .env
# then edit .env and set your own key:
# PORTKEY_API_KEY=pk-...your key...
```

`.env` is git-ignored. Never commit it. The backend reads `PORTKEY_API_KEY` from the repo's `.env`, or from the environment if it's exported there.

## 3. Copy or reset the database

The app only ever writes to `data/campus_customs_new.db`. To get a clean working copy from the original, either use the shell:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

or, once the backend is running, the dashboard's **Reset shop** button. You can also call the API directly:

```bash
curl -X POST localhost:8000/api/reset -H 'Content-Type: application/json' -d '{"confirm":"RESET"}'
```

The reset route copies the original byte-for-byte, checks the SHA-256 matches, and voids any pending approvals. `data/campus_customs.db` itself is only ever read.

## 4. Start the MCP server

You normally **don't start it by hand**. The backend launches `mcp_server/server.py` itself (over stdio), using the command in `.mcp.json`. If those paths don't exist on your machine, it falls back to the current Python and the repo's own server.

To run or test it on its own:

```bash
python mcp_server/server.py          # speaks MCP over stdio (it waits silently for a client)
```

To use it from **Claude Code**, edit `.mcp.json` so `command` points at your virtualenv's Python and `args` at your clone's `mcp_server/server.py`. The committed file contains the author's absolute paths. Then start a fresh Claude Code session in the repo. The read tools work from Claude Code. The write tools refuse unless the backend started the server, by design.

## 5. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

- Check it's up: `curl localhost:8000/api/health`. Interactive API docs are at http://localhost:8000/docs.
- Optional offline self-test (no model calls, no tokens): `python -m backend.check_setup`, run from the repo root. It expects a **freshly reset** database (step 3). On the committed post-run database, three of its checks report the changed cash state.

## 6. Start the React frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

## 7. Use the app

Open **http://localhost:5173**.

1. Select a ticket (101 Bulldog tee, 102 Rent due, 103 Bulk hoodie discount) and click **Start agent team**.
2. Watch the run. The roster shows which agent is working, and the live feed shows each delegation, MCP tool call and guardrail check. When the run finishes, the ticket is marked **Resolved**.
3. If the team prepared a payment, it appears under **Approvals**. Click **Approve**, enter your name, and confirm. The backend re-checks it against the database before paying, and the **Checking** balance updates. You can also **Reject** it.
4. **Who did what** summarizes each agent's contribution.

## 8. Full three-ticket run (as in Problem 9)

1. **Reset first**, with **Reset shop** in the dashboard, or step 3 above. Checking should show **$3,400.00** and all three tickets should be **open**.
2. Run **101**. Approve the $840 Bulldog Print Co invoice #501. Checking becomes $2,560.
3. Run **102**. Approve the $2,400 lease #1 rent. Checking becomes $160.
4. Run **103**. In our run no payment was proposed. Checking stays $160.

Agent runs are model-driven, so the exact delegations and wording vary between runs. The cash rules don't: every payment needs a human, and checking can never go negative. Our recorded run is in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json` and `output/resolved_board.html`.

## Safety at a glance

- **Agents can only propose payments.** Payment amounts always come from the database, never from the model.
- **Only the human Approve route can move cash.** It works through a signed MCP write tool that only the backend can call. Agents' tool lists contain no write tools.
- **Overdrafts, stale or duplicate approvals, and payments to blocked vendors are refused.**
- **Customer messages stay drafts.** Nothing is sent.
- **Every agent step is appended to `output/audit_trail.json`,** with secrets redacted.
- **Limits:** each run has bounded delegation depth and hand-offs, plus token, request and retry limits.

Details are in `output/harness.md` and `output/design.md`.
