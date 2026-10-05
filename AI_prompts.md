# AI Prompts Log

This file is a running log of the prompts used while completing Homework 5: Campus Customs Multi-Agent Operations. Add one section per problem, using the template below.

---

## Template for future problems

````markdown
## Problem N: Title

### Initial Prompt

```text
(paste the first prompt here)
```

### Follow-up Prompt

None.

### What was missing after the first prompt?

None. (If a follow-up was needed, write one sentence explaining what the first prompt missed.)

---
````

---

## Problem 1: Vibe coder prompts

### Initial Prompt

````text
I am starting Homework 5: Campus Customs Multi-Agent Operations.

For this homework, I will eventually build a system with three connected components: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard.

The agents will eventually include:
- Boss
- Inventory
- Accounting
- Facilities
- Customer Service

For now, I only want to complete Problem 1 and set up the project correctly. Do not build the later homework problems yet.

Please do the following:

1. Create a file called `AI_prompts.md` in the root of my project.

2. Set it up so I can use it as a running log of the prompts I give you throughout this homework.

3. Create a section for Problem 1 titled:
   `Problem 1: Vibe coder prompts`

4. Under that section, record this prompt as my initial prompt.

5. Structure `AI_prompts.md` so that future problems can each have:
   - the problem number and title
   - my initial prompt
   - a follow-up prompt, if one was needed
   - one sentence explaining what was missing after the first prompt, if a follow-up was needed

Also keep these project-wide requirements in mind for later problems:
- The working database will be `data/campus_customs_new.db`.
- The original `data/campus_customs.db` must remain untouched so it can be used to reset the assignment.
- The database contains the tables `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, and `invoices`.
- Use `desk.date_today` as the shop's current date.
- Vendor lead times come from the `vendors` table.
- A vendor cannot ship new product while it has an open unpaid invoice.
- Any payment must require human approval.
- Payments must update the relevant database table.
- Never allow a payment that would create a negative cash balance.
- Cash only goes out; there is no modeled revenue.
- Do not actually email customers or contact vendors. Any communications should remain drafts.
- All agents must use only `gpt-6-luna` through Portkey with `PORTKEY_API_KEY`.
- Do not use any other AI model.

For this step, only create/setup `AI_prompts.md` and confirm what you changed. Do not implement the MCP server, FastAPI backend, React dashboard, or agents yet.
````

### Follow-up Prompt

None.

### What was missing after the first prompt?

None.

---

## Problem 2: Study the Campus Customs database

### Initial Prompt

````text
I am now working on Problem 2: Study the Campus Customs database.

Please inspect `data/campus_customs.db` carefully so we understand the database before building any agents or tools.

For this problem, please:

1. Open and inspect `data/campus_customs.db`.

2. Examine every table and all of its fields. The expected tables are:
   - `desk`
   - `tickets`
   - `inventory`
   - `pricing`
   - `vendors`
   - `leases`
   - `cash_accounts`
   - `payments`
   - `invoices`

3. Study the three open tickets in the `tickets` table. Trace how the information in each ticket connects to the other relevant tables. I want to understand which tables and fields the agents will eventually need to resolve each ticket.

4. Preserve `data/campus_customs.db` exactly as it is. Do not modify the original database.

5. Make a copy of the original database called:
   `data/campus_customs_new.db`

   This will be the working database that later problems are allowed to modify.

6. Create `output/harness.md`.

7. In `output/harness.md`, document every database table. For each table:
   - list its fields
   - add one short explanation of what the table contains and why it matters to the agents

8. Also add a short section describing the three open tickets and which database tables appear relevant to each one. Base this only on what you actually find in the database rather than guessing.

9. Update `AI_prompts.md` with a new section titled:
   `Problem 2: Study the Campus Customs database`
   and record this prompt there.

For now, only complete Problem 2. Do not start implementing the MCP server, agents, FastAPI backend, or React dashboard.

When finished, summarize:
- the files you created or changed
- the database tables you found
- the three open tickets
- how you verified that `campus_customs.db` remained untouched and `campus_customs_new.db` is the working copy.
````

### Follow-up Prompt

None.

### What was missing after the first prompt?

None.

---

## Problem 3: Build the MCP server

### Initial Prompt

````text
I am now working on Problem 3: Build the MCP server.

Using what you learned from inspecting the Campus Customs database in Problem 2, build the MCP server for this project.

Please do the following:

1. Create an MCP server inside the `mcp_server/` directory using FastMCP.

2. The MCP server must use the working database:
   `data/campus_customs_new.db`

   Do not modify or point the server at the original `data/campus_customs.db`.

3. Create exactly three MCP tools for now. Choose the three tools based on the actual three open tickets (101, 102, and 103) and the database relationships you documented in `output/harness.md`.

Each tool should:
- have a clear, descriptive name
- solve a concrete information need associated with one or more of the three tickets
- read the appropriate database table(s)
- return only information actually stored in the database
- never invent missing data

Design the tools specifically around what is necessary to understand or unlock tickets 101, 102, and 103. Do not create vague generic tools if a more ticket-specific tool would be clearer.

4. Keep this problem limited to the MCP server and these three tools. I do not need to connect or run the MCP server yet.

5. Update `output/harness.md`.

Create a section for the MCP tools and document all three tools. For each tool, include:
- the tool name
- which database table or tables it reads
- which ticket it helps unlock: 101, 102, or 103
- one specific sentence explaining why this tool is the right tool for that ticket

Please make these explanations specific to the actual ticket and database data rather than saying something vague like "reads inventory."

6. Create `mcp_server/README.md`.

The README should briefly explain:
- what the MCP server is for
- that it uses `data/campus_customs_new.db`
- the three MCP tools it provides
- what each tool does

7. Update `AI_prompts.md` with a section titled:
   `Problem 3: Build the MCP server`
and record this prompt as my initial Problem 3 prompt.

Important constraints:
- Use FastMCP.
- Use only the working database `data/campus_customs_new.db`.
- Preserve `data/campus_customs.db` untouched.
- Never invent database values.
- Base the tools on the actual database schema and tickets you inspected in Problem 2.
- Do not implement later homework requirements yet.
- Do not build the FastAPI backend, multi-agent team, or React dashboard in this problem.
- Do not add unnecessary tools beyond the three required here.

Before finishing, review your implementation against both Problem 3 requirements and the database findings from Problem 2.

Then give me a concise summary showing:
1. the three MCP tool names,
2. the database table(s) each reads,
3. the ticket each helps unlock,
4. why each is appropriate for that specific ticket,
5. the files you created or modified.

Do not proceed to Problem 4.
````

### Follow-up Prompt

None.

### What was missing after the first prompt?

None.

---

## Problem 4: Add the MCP server to vibe coder and test each tool

### Initial Prompt

````text
I am now working on Problem 4: Add the MCP server to my vibe coder and test each tool.

Please use the MCP server we built in Problem 3 and connect it to this current Homework 5 project so that you, my vibe coder, can call its tools.

Please complete the following:

1. Configure this project to use the local MCP server in `mcp_server/`.

2. Save the MCP server connection configuration in `.mcp.json` at the project root, or use the appropriate project-level local MCP configuration format if required by this vibe coder.

3. Make sure the configuration points to the MCP server created in Problem 3 and that the server uses:
   `data/campus_customs_new.db`

4. Verify that the MCP server connects successfully and that you can see exactly the three MCP tools created in Problem 3.

5. Once connected, actually call each of the three MCP tools through the MCP connection.

For each tool, choose an appropriate request based on the ticket that the tool was designed to help with. Use tickets 101, 102, and 103 as appropriate based on the mappings already documented in `output/harness.md`.

6. Verify every returned value against `data/campus_customs_new.db`. Do not invent, estimate, or alter any values. The saved tool outputs must match the database.

7. Create:
   `output/mcp_smoke.json`

This file should contain evidence for all three MCP tool tests.

For EACH of the three tools, include:
- `prompt`: the prompt/request I asked the vibe coder to perform
- `tool_name`: the exact MCP tool that was called
- `tool_output`: the actual output returned by that MCP tool

Make sure this is valid JSON.

The evidence should demonstrate that the tools were actually called through the configured MCP server, not merely that the underlying Python functions work when called directly.

8. Do not modify the original:
   `data/campus_customs.db`

The MCP server should continue using only:
   `data/campus_customs_new.db`

9. Update `AI_prompts.md` with a section titled:
   `Problem 4: Add the MCP server to vibe coder and test each tool`

Record this prompt as my initial Problem 4 prompt.

10. Do not begin Problem 5 or implement any later homework requirements.

When finished, give me a concise summary showing:
- where the MCP connection configuration was saved
- whether the MCP server connected successfully
- the exact three MCP tools that were available
- which ticket/request you used to test each tool
- whether each output matched the database
- where `output/mcp_smoke.json` was saved
- the files you created or modified

If the vibe coder requires a restart or another manual action before it can recognize the new MCP configuration, stop and tell me exactly what I need to do rather than pretending the MCP tools were successfully connected or called.
````

### Follow-up Prompt

````text
Continue Problem 4.

The `campus-customs` MCP server should now be connected through `.mcp.json`.

Please verify that the MCP connection is active and that exactly three tools are available.

Then actually call each of the three tools THROUGH THE MCP CONNECTION using these ticket IDs:

- Ticket 101 → `get_backorder_and_vendor_block_status`
- Ticket 102 → `get_rent_due_and_cash_position`
- Ticket 103 → `get_bulk_order_stock_and_pricing`

For each test:

1. Call the actual MCP tool rather than directly invoking its underlying Python function.
2. Record the prompt/request used.
3. Record the exact MCP tool name.
4. Record the actual output returned by the MCP tool.
5. Check the returned values against `data/campus_customs_new.db`.

Then create `output/mcp_smoke.json` containing the evidence for all three tests. It must be valid JSON and, for each tool, include:
- `prompt`
- `tool_name`
- `tool_output`

The tool outputs must match values in `data/campus_customs_new.db`.

Do not modify `data/campus_customs.db`.

Also update the Problem 4 section of `AI_prompts.md` to include this as my follow-up prompt and add one sentence explaining that the follow-up was necessary because the MCP server configuration could not be loaded dynamically into the original Claude Code session and required a new session.

Do not start Problem 5.

When finished, tell me:
- whether `campus-customs` connected successfully
- whether exactly three MCP tools were available
- whether each tool was actually called through MCP
- whether each result matched the database
- whether `output/mcp_smoke.json` was successfully created.
````

### What was missing after the first prompt?

A follow-up was needed because the MCP server configuration in `.mcp.json` could not be loaded dynamically into the original Claude Code session, so a new session started from `hwv5/` was required before the tools could be called through MCP.

---

## Other session prompts (not tied to a problem)

### 2026-10-04: Session start

````text
hello, today i will be working on homework 5. please log everything in hwv5 folder today.
````

### 2026-10-04: Logging check

````text
write a joke to prove it
````

Response: "Why did the homework folder hire a stenographer? Because hwv5 wanted everything on the record, even the jokes."

---

### 2026-10-04: Uploaded homework files

````text
okay i uploaded the homewoerk in the hwv5 folder
````

---

### 2026-10-04: Checking the upload

````text
did you find it?
````

---

### 2026-10-04: Clarifying the upload

````text
okay great, i meant did you find the db file?
````

---

### 2026-10-04: Problem 4 follow-up — MCP smoke tests

````text
Continue Problem 4. The `campus-customs` MCP server is now connected successfully and I can see all three tools.

Please actually call each of the three tools THROUGH THE MCP CONNECTION:

1. For ticket 101, call:
   `get_backorder_and_vendor_block_status`

2. For ticket 102, call:
   `get_rent_due_and_cash_position`

3. For ticket 103, call:
   `get_bulk_order_stock_and_pricing`

For each test:
- use the appropriate ticket ID
- record the prompt/request
- record the exact MCP tool name
- record the actual output returned by the MCP tool
- verify the returned values against `data/campus_customs_new.db`

Then create `output/mcp_smoke.json`.

For each of the three tools, the JSON must include:
- `prompt`
- `tool_name`
- `tool_output`

Make sure `output/mcp_smoke.json` is valid JSON and that all tool outputs match the values in `data/campus_customs_new.db`.

These tests must be actual MCP tool calls through the connected `campus-customs` server. Do not substitute direct Python function calls for the MCP calls.

Do not modify `data/campus_customs.db`.

Also make sure `AI_prompts.md` contains this Problem 4 follow-up prompt and a one-sentence explanation that a follow-up was needed because the new `.mcp.json` configuration required a fresh Claude Code session before the MCP server became available.

Do not start Problem 5.

When finished, confirm:
1. all three tools were actually called through MCP,
2. each output matched the database,
3. `output/mcp_smoke.json` was created and contains all three tests.
````

Why a follow-up was needed: the new `.mcp.json` configuration only takes effect in a fresh Claude Code session, so the `campus-customs` MCP server wasn't available to call until the session was restarted.

---

## Problem 5: Build the agent team and grow the MCP tools

### 2026-10-04: Initial Problem 5 prompt

````text
I am now working on Problem 5: Build the agent team and grow the MCP tools.

Please build the Campus Customs multi-agent team using PydanticAI and expand the existing MCP server with any additional tools the agents need to work on the three open tickets.

Use the database, MCP server, harness, and work from Problems 1–4 as the source of truth. Do not start later homework problems.

## 1. Build the five-agent team

Create these five clearly separate PydanticAI agents:

- Boss
- Inventory
- Accounting
- Facilities
- Customer Service

Put the agent implementation under `backend/`.

Each agent must have:
- a clearly defined role and scope
- its own detailed system prompt
- access to the appropriate MCP tools
- an agent loop
- the ability to delegate work to any of the other agents

The team must have full connectivity. Any agent should be able to delegate to any other agent when that agent's expertise is needed.

Avoid infinite delegation loops. Add sensible limits so agents cannot endlessly hand work back and forth.

## 2. Agent prompts

Create:

`backend/prompts/`

Put one prompt file per agent in this directory.

The five prompt files should correspond to:
- Boss
- Inventory
- Accounting
- Facilities
- Customer Service

Write detailed prompts in our own words rather than short generic role descriptions.

Each prompt should contain the shop rules and responsibilities relevant to that particular agent.

The agents should understand these responsibilities:

Boss:
- reads and coordinates tickets
- determines which specialists are needed
- delegates work
- combines information from specialists
- makes final operational recommendations
- respects human-approval requirements

Inventory:
- evaluates stock by SKU and size
- identifies shortages
- evaluates restocking possibilities
- uses vendor information and lead times
- recognizes when an unpaid vendor invoice prevents shipment

Accounting:
- evaluates cash balances
- examines invoices
- checks margins/costs
- evaluates proposed payments and purchase orders
- never allows a payment that would create a negative cash balance
- treats payments as requiring human approval

Facilities:
- handles leases, rent, due dates, and other shop-space obligations
- uses `desk.date_today`, not the computer's date, when evaluating whether something is due or overdue

Customer Service:
- prepares customer-facing draft messages when appropriate
- never actually emails or contacts a customer
- communications remain drafts for human review

## 3. Model configuration

Use `PORTKEY_API_KEY` for AI calls.

EVERY agent must use ONLY:

`gpt-6-luna`

through Portkey.

Do not use any other model anywhere in the agent implementation, fallback configuration, examples, tests, or defaults.

Do not hard-code my API key.

Use the environment variable.

## 4. Data types

Put the shared Pydantic/data types needed by the agent system in:

`backend/models.py`

Create appropriate structured types for things such as agent requests/responses, delegation, ticket work, approvals, recommendations, or audit records as needed by your implementation.

Keep the design understandable rather than unnecessarily complicated.

## 5. Full agent connectivity

Implement delegation so all five agents can collaborate.

Any agent may delegate to any other agent when needed.

The Boss should be able to coordinate the overall workflow, but do not artificially restrict specialist-to-specialist delegation if another specialist is needed.

Make delegation auditable and bounded.

## 6. MCP is the shop-data layer

All shop facts must come through the MCP server using:

`data/campus_customs_new.db`

Review the three MCP tools already created in Problems 3–4.

Add any additional MCP tools that the five agents genuinely need to work on tickets 101, 102, and 103.

IMPORTANT:
- Do not create a second shop-tools/data-access layer inside `backend/` that bypasses MCP.
- Agents should obtain shop facts through MCP.
- Do not duplicate database-query logic inside the agents.
- Do not invent data.
- Keep `data/campus_customs.db` untouched.

Choose additional tools based on actual needs you identify from the database and open tickets rather than adding arbitrary tools.

## 7. Preserve the shop rules

The implementation must respect all existing shop rules, including:

- `desk.date_today` is the shop's definition of today.
- Vendor lead times come from `vendors`.
- A vendor will not ship new product while it has an open unpaid invoice.
- Human approval is required for any payment.
- A payment must update the relevant table when it is eventually approved/executed.
- A payment must be refused if there is insufficient cash; never allow a negative cash balance.
- Cash only goes out in this homework; no revenue is modeled.
- Do not email real customers or contact real vendors.
- Customer/vendor communications remain drafts.
- Shop facts come from `data/campus_customs_new.db` through MCP.

Do not resolve or mutate things merely because an agent recommends an action unless the current assignment explicitly authorizes that action.

## 8. Audit trail

Create/use:

`output/audit_trail.json`

Wire the agent system so that every agent-loop step appends enough information to this file to reconstruct and audit what happened later.

Do NOT erase or overwrite previous audit history every time the system runs. Append new records.

Use valid JSON in a structure that can safely grow across runs.

For each meaningful agent-loop step, record useful information such as:
- timestamp or sequence identifier
- ticket ID
- acting agent
- task/request
- MCP tool calls, if any
- delegation from/to another agent, if any
- result or recommendation
- whether human approval is required
- errors or guardrail decisions when relevant

Do not record secrets such as `PORTKEY_API_KEY`.

## 9. Safety and token controls

Add practical safeguards appropriate for agents that may eventually interact with customers and real money.

At minimum consider:
- human approval before payments
- refusal of payments that exceed available cash
- no negative balances
- no autonomous external customer/vendor communications
- drafts requiring human review
- database-backed facts only
- validation of tool inputs
- bounded delegation/agent-loop depth
- bounded retries
- reasonable token/output limits
- avoiding unnecessary repeated agent calls
- no secrets in logs
- clear handling of tool/model failures

Implement the relevant safeguards in the system where appropriate, not only in documentation.

## 10. Update `output/harness.md`

Expand `output/harness.md` to document Problem 5.

Add a section listing all five agents.

For each agent, briefly document:
- its role
- its responsibilities
- relevant MCP tools
- how/when it delegates

Also list EVERY MCP tool now available, including:
- the original three tools
- every new tool added in Problem 5
- the database table or tables each tool uses
- what operational need/ticket the tool supports

Add a short `Safety` section explaining:
- guardrails a real business would want when agents interact with real customers or real money
- human approval requirements
- financial safeguards
- communication safeguards
- data-integrity safeguards
- limits that keep token usage under control

## 11. Update the MCP README

Update:

`mcp_server/README.md`

so its tool list exactly matches the MCP server after Problem 5.

For every current tool, briefly explain what it does.

## 12. Preserve existing work

Do not break the three MCP tools or the MCP configuration that successfully passed Problem 4.

Keep `.mcp.json` working.

Do not delete or overwrite:
- `output/mcp_smoke.json`
- existing sections of `output/harness.md`
- previous entries in `AI_prompts.md`

Do not modify the original:
`data/campus_customs.db`

## 13. Update the prompt log

Add a section to `AI_prompts.md` titled:

`Problem 5: Build the agent team and grow the MCP tools`

Record this entire prompt as my initial Problem 5 prompt.

If you encounter a problem that requires me to take a manual action, stop and tell me what I need to do rather than pretending it succeeded.

## 14. Validate Problem 5

Before finishing, review the implementation against every Problem 5 requirement.

Check specifically that:
- all five agents exist
- each agent has its own prompt file
- `backend/models.py` exists
- all agents use PydanticAI
- all agents use only `gpt-6-luna` through Portkey
- no other model appears in the implementation
- `PORTKEY_API_KEY` is read securely from the environment
- all five agents have full delegation connectivity
- delegation/agent loops are bounded
- shop facts are obtained through MCP rather than a duplicate backend database layer
- any necessary new MCP tools were added
- `output/audit_trail.json` is append-oriented
- `output/harness.md` documents all five agents and all current MCP tools
- the harness contains the requested safety/token-use section
- `mcp_server/README.md` contains the current complete tool list
- `data/campus_customs.db` remains untouched
- existing Problem 4 MCP functionality remains intact

Do not run a full ticket-resolution workflow unless it is necessary for Problem 5. Do not start Problem 6.

When finished, give me a concise summary of:
1. the five agents and the files implementing them,
2. the five prompt files,
3. how full agent-to-agent delegation works,
4. the model/Portkey configuration,
5. every MCP tool currently available and which tools were newly added,
6. how agents access MCP instead of querying the shop database directly,
7. how `output/audit_trail.json` works,
8. the safety and token guardrails implemented,
9. all files created or modified,
10. whether you found any requirement you could not fully complete.
````

---

## Problem 6: Plan the three tickets

### 2026-10-04: Initial Problem 6 prompt

````text
I am now working on Problem 6: Plan the three tickets.

Using the Campus Customs database, MCP tools, agent team, harness, and other work already completed in Problems 1–5, please complete Problem 6.

Do NOT run the agents to resolve the tickets yet. This problem is only about documenting what we EXPECT the agent team to do.

Create `output/desk_tickets.html` as a self-contained HTML page that I can open locally by double-clicking it.

The page must have five tabs:
1. Ticket 101
2. Ticket 102
3. Ticket 103
4. Cash
5. Reflection

For now, leave the Cash and Reflection tabs blank or include only a short “Coming later” message.

For each of tickets 101, 102, and 103, create an “Expected” section. Also create a clearly labeled “Actual” section, but leave the Actual section empty because later problems will fill it after the agents run.

For each Expected section, determine and document:

- Which specialist agent the Boss should call FIRST and why.
- Every agent-to-agent delegation that should reasonably occur to resolve that specific ticket.
- Do NOT simply send every specialist agent to every ticket. Only include agents whose expertise is actually necessary.
- List the specific MCP tools that you expect the agents to use for that ticket.
- Explain briefly what each agent and MCP tool contributes to resolving the ticket.
- Base the plan on the actual ticket and shop data already discovered in `data/campus_customs_new.db`, the MCP tools, and `output/harness.md`. Do not invent shop facts.

The available agent roles are:
- Boss
- Inventory
- Accounting
- Facilities
- Customer Service

Use the actual MCP tool names implemented in the project, including the tools added in Problem 5.

Make the expected workflow specific enough that after we run the agents in a later problem, we can compare the planned delegation/tool-use path against what actually happened.

Important:
- Do not modify or resolve the tickets.
- Do not execute the full agent team.
- Do not change database values.
- Do not fill in the Actual sections yet.
- Preserve all work from Problems 1–5.
- Do not start Problem 7.

After completing the file, verify that:
1. `output/desk_tickets.html` exists and opens as standalone HTML.
2. All five tabs work.
3. Tickets 101, 102, and 103 each contain an Expected section and an empty Actual section.
4. Each Expected section identifies the Boss’s first delegation, all expected subsequent delegations, and the expected MCP tools.
5. Cash and Reflection are placeholders only.
6. No database data or ticket state was changed.

Then summarize exactly what you created and tell me whether Problem 6 is fully complete.
````

---

## Problem 7: Backend routes

### 2026-10-04: Initial Problem 7 prompt

````text
I am now working on Problem 7: Backend routes.

Using the Campus Customs work already completed in Problems 1–6, please build and test the FastAPI backend required for Problem 7.

Work with the existing implementation. Preserve the agent team, MCP server, database structure, audit trail, prompts, and previous homework outputs. Do not rebuild working components unnecessarily.

In `backend/main.py`, create a FastAPI application that provides the backend routes needed by the React dashboard in the next problem.

The backend must provide routes that do all of the following:

1. TICKETS
Return the three Campus Customs tickets and indicate whether each ticket is currently open or resolved. Use the actual ticket data/status from `data/campus_customs_new.db`.

2. RUN AGENT TEAM
Accept a ticket ID and run the existing multi-agent team from Problem 5 on that specific ticket.

This route should use the existing Boss + specialist agent architecture and existing MCP tools rather than implementing a separate ticket-resolution system.

3. AGENT EVENTS
Return recent agent events so the future dashboard can display:
- which agent acted
- what the agent said/did
- which MCP tools were used
- relevant ticket/run information

Use the existing audit trail where appropriate rather than inventing a second unrelated logging system.

4. HUMAN APPROVAL
Create a route that allows a human to approve a prepared payment or purchase.

Important safety rule:
Agents may PREPARE or RECOMMEND a payment/purchase, but they must not actually change cash merely because an agent requested it.

The approval route is the point where a human-approved payment or purchase may actually be executed and cash/database state may change.

Use the existing MCP/database architecture for the transaction. Do not create a second shop-data layer that bypasses MCP.

Validate requests carefully and prevent invalid, duplicate, or unauthorized transactions.

5. CASH BALANCE
Return the current checking balance from the `cash_accounts` table in `data/campus_customs_new.db`.

Do not hard-code the balance.

6. RESET
Create a route that resets the working database to the original Campus Customs values so I can perform a fresh run.

The working database is:
`data/campus_customs_new.db`

The original/reset source is:
`data/campus_customs.db`

The original database must remain unchanged/read-only. Reset the WORKING database from the original rather than modifying the original.

BACKEND REQUIREMENTS

- Use FastAPI in `backend/main.py`.
- Make the API usable by the React frontend that will be built in the next problem.
- Add appropriate request/response models where useful.
- Add clear error handling for invalid ticket IDs, invalid approvals, missing records, etc.
- Preserve the human-in-the-loop safeguards from Problem 5.
- Continue using `output/audit_trail.json` appropriately.
- Shop facts and mutations should continue through the MCP architecture rather than creating a separate SQLite/shop-tools implementation inside the agents.
- Do not invent any shop data.

TESTING

Test every backend route before finishing.

You may start the backend from the `backend/` directory using:

uvicorn main:app --reload --port 8000

Verify that the API is available at localhost:8000 and that each route returns the expected result.

Be careful during testing:
- Do not accidentally leave the working database in a modified state merely because you tested an approval.
- If a mutation must be tested, reset the working database afterward and verify that it matches the original starting state.
- Do not alter `data/campus_customs.db`.

DOCUMENTATION

Append a Problem 7 section to `output/harness.md`.

List EVERY backend route on one line each in this format:

METHOD /route — what the route does

Include all routes actually implemented, not just the six conceptual requirements.

Also record the exact Problem 7 prompt I gave you in `AI_prompts.md`, following the format used for the previous problems.

FINAL VERIFICATION

Before stopping, verify:

1. `backend/main.py` contains a working FastAPI app.
2. There is a route returning all three tickets and their open/resolved status.
3. There is a route that accepts a ticket ID and invokes the existing agent team.
4. There is a route returning recent agent/audit events.
5. There is a human-approval route for prepared payments/purchases.
6. Agents cannot independently execute those cash-changing approvals.
7. There is a route returning the current checking balance from `cash_accounts`.
8. There is a reset route that restores `data/campus_customs_new.db` from the original database.
9. The original `data/campus_customs.db` remains unchanged.
10. `output/harness.md` lists every route and what it does.
11. All routes have been tested successfully.
12. The working database is returned to its correct original starting state after testing.

Do not build the React frontend yet and do not start Problem 8.

When finished, give me:
- the routes you created
- the test result for each route
- any files created or modified
- confirmation that the original database remained untouched
- confirmation that the working database is in the correct starting state
- whether Problem 7 is fully complete
````

---

## Problem 8: Agent dashboard

### 2026-10-04: Initial Problem 8 prompt

````text
I am now working on Problem 8: Agent dashboard.

Using the Campus Customs work already completed in Problems 1–7, please build the frontend dashboard in frontend/ using React + Vite + TypeScript.

Connect the frontend to the FastAPI backend from Problem 7 at http://localhost:8000. Configure the backend CORS settings so the Vite frontend, usually http://localhost:5173, can call the API.

The dashboard must:

1. Display all three Campus Customs tickets and clearly show whether each ticket is open or resolved.
2. Let me select one ticket and start the agent team on that ticket.
3. While a ticket is running, show the agents involved and what each agent is saying or doing.
4. When the run finishes, clearly mark the ticket as resolved.
5. Show a concise summary of what each participating agent did on that ticket.
6. Show any payment or purchase that requires human approval. Provide an Approve control that calls the approval route from Problem 7. Agents must not directly approve or execute these transactions themselves.
7. Display the current checking balance from the backend and refresh it after an approved payment or purchase so I can see the balance change.
8. Use the actual Problem 7 API routes and the existing agent/backend implementation. Do not create fake frontend data or duplicate backend business logic in the frontend.
9. Include appropriate loading, error, empty, running, approval-required, and resolved states.

Make the dashboard polished and visually thoughtful. It should feel like a real Campus Customs operations desk, with a clear visual hierarchy for tickets, agents, activity, approvals, and cash. Make the five agent roles visually distinguishable and make open versus resolved tickets immediately recognizable.

Create output/design.md explaining:
- the dashboard layout
- the visual design choices
- how the five agents are visually distinguished
- how open/resolved tickets appear
- how agent activity is displayed
- how approvals are presented
- how the checking balance is displayed
- the creative choices that make the dashboard pleasant and useful

Then test the implementation. Confirm that the frontend builds successfully and that it is correctly wired to the Problem 7 backend routes.

Do not start Problem 9. Do not unnecessarily change or overwrite work from Problems 1–7.

At the end, tell me:
- which files you created or modified
- whether the frontend build passed
- how to start the backend
- how to start the frontend
- the local URL I should open
- whether there is anything I need to do manually before testing the dashboard

Also append this exact Problem 8 prompt to AI_prompts.md.
````

---

## Problem 9: Resolve the tickets

### 2026-10-04: Initial Problem 9 prompt

````text
I am now working on Problem 9: Resolve the tickets.

Using the Campus Customs system already completed in Problems 1–8, please perform the full Problem 9 run. Do not redesign or rebuild the existing system unless a small fix is necessary for the required workflow.

Please do the following:

1. RESET FIRST
- Reset the working database at data/campus_customs_new.db to its original clean state before running any tickets.
- Verify the reset succeeded.
- Record the starting checking balance from cash_accounts.
- Confirm tickets 101, 102, and 103 are all open before beginning.
- Do not use the $2,560 balance from my Problem 8 test as the starting balance.

2. RUN ALL THREE TICKETS
Run tickets 101, 102, and 103 through the actual multi-agent workflow until all three are resolved.

For each ticket:
- use the real Boss + specialist-agent workflow from Problem 5
- use the actual MCP tools
- preserve the real delegation sequence
- record which agents participated
- record what each agent did
- record which MCP tools were called
- record the final outcome
- record any payment or purchase proposed
- do not fabricate agent actions or tool calls

If a payment or purchase requires human approval, STOP before approving it yourself. Tell me:
- which ticket needs approval
- what is being paid/purchased
- the exact amount
- the current checking balance
- what I need to click/do in the dashboard

I will perform the human approval myself. Do not simulate, bypass, or automatically grant human approval.

After I approve it, verify the actual cash change from the working database before continuing.

3. CASH ACCOUNTING
Track the cash effects separately for tickets 101, 102, and 103.

Record:
- starting checking balance after reset
- cash change caused by ticket 101 and why
- cash change caused by ticket 102 and why
- cash change caused by ticket 103 and why
- ending checking balance

The ending balance MUST be verified directly against cash_accounts in data/campus_customs_new.db. Do not infer or guess the ending balance.

4. UPDATE output/desk_tickets.html
Keep the existing Expected sections from Problem 6 unchanged.

For tickets 101, 102, and 103, fill in the previously empty Actual section using evidence from the real Problem 9 runs.

For each Actual section include:
- first agent Boss called
- why
- all actual delegations
- agents that participated
- MCP tools actually used
- final outcome
- any human approval

Do not overwrite the Expected sections.

5. COMPLETE THE CASH TAB
In the Cash tab of output/desk_tickets.html, itemize:
- starting checking balance
- Ticket 101 cash change + reason
- Ticket 102 cash change + reason
- Ticket 103 cash change + reason
- ending checking balance

Make sure the arithmetic reconciles exactly to cash_accounts.

6. CREATE output/resolved_tickets.json
For each ticket include:
- id
- final status
- short outcome
- contribution of each participating agent
- MCP tools used
- any human approvals
- cash effect

Use the actual run data, not hypothetical results.

7. CREATE output/resolved_board.html
Create a standalone page that can be double-clicked and viewed locally.

It must contain a screenshot of the React dashboard for EACH resolved ticket:
- Ticket 101
- Ticket 102
- Ticket 103

Clearly label each screenshot with its ticket number.

If screenshots must be captured during the runs, capture/save them at the appropriate time rather than inventing a representation later.

8. AUDIT TRAIL
Append the REAL Problem 9 runs to output/audit_trail.json.
Do not erase or replace earlier valid audit records.

9. FINISH output/harness.md
Complete the harness so it documents:
- database tables
- MCP tools
- five agents
- API routes
- React dashboard
- safety rules / human approval guardrails
- Problem 9 end-to-end run

Preserve valid work already documented from earlier problems.

10. FINAL VALIDATION
Before saying Problem 9 is complete, verify:
- tickets 101, 102, and 103 are all resolved
- Expected sections remain intact
- Actual sections contain real run data
- Cash tab reconciles exactly
- ending checking balance equals cash_accounts
- resolved_tickets.json is valid JSON
- resolved_board.html opens locally and contains evidence for all 3 resolved tickets
- audit_trail.json contains the real runs
- harness.md covers all required components
- no payment/purchase occurred without my human approval
- the original/reference database was not accidentally modified

IMPORTANT: Because Problem 9 explicitly tests human approval, do not approve payments on my behalf. Pause whenever my approval is required and wait for me.
````

### 2026-10-04: Problem 9 follow-up (after approving Ticket 101)

````text
I approved and paid the $840 invoice #501 for Ticket 101 through the dashboard.

Please continue Problem 9 from the CURRENT state. Do NOT reset the database.

First:
1. Verify directly in data/campus_customs_new.db that the payment was recorded.
2. Verify that checking changed from $3,400.00 to $2,560.00.
3. Verify Ticket 101's final status.
4. Preserve the real Ticket 101 agent/delegation/tool evidence for its Actual section and the required Problem 9 output files.
5. Preserve this as the Ticket 101 cash effect: -$840 for payment of Bulldog Print Co invoice #501.
6. Capture/save the required resolved-board evidence for Ticket 101 before moving on if it has not already been captured.

Then proceed with Ticket 102 through the real multi-agent workflow.

Do not approve any payment or purchase yourself.

If Ticket 102 requires a human approval, STOP and tell me:
- what needs approval
- exact amount
- current checking balance
- why the payment/purchase is needed
- exactly what I need to click in the dashboard

Do not start Ticket 103 until Ticket 102 has been fully handled and any required human approval has been completed.
````

### 2026-10-04: Problem 9 follow-up (after approving Ticket 102)

````text
I have now approved and paid the $2,400 rent payment for Ticket 102 through the dashboard.

Continue Problem 9 from the CURRENT state. Do NOT reset the database.

First verify directly in data/campus_customs_new.db:

1. The $2,400 rent payment for lease #1 was actually recorded.
2. Checking changed from $2,560.00 to $160.00.
3. Ticket 102's final status is resolved.
4. Preserve the actual Ticket 102 agents, delegations, MCP tool calls, outcome, and human approval for the Actual section and final Problem 9 artifacts.
5. Record Ticket 102's cash effect as -$2,400 for payment of lease #1.
6. Capture/save the required resolved-board evidence for Ticket 102 if it has not already been captured.

Then proceed with Ticket 103 using the real multi-agent workflow.

The current checking balance should now be $160.00. Do not infer affordability — use the MCP tools and database state required by the existing workflow.

Do NOT approve any payment or purchase yourself.

If Ticket 103 requires a human approval, STOP before making the transaction and tell me:
- exactly what is being proposed
- exact amount
- current checking balance
- why it is needed
- whether the available cash is sufficient
- exactly what I need to do in the dashboard

If Ticket 103 can be resolved without a payment or purchase, complete the agent run normally.

After Ticket 103 is fully resolved, do NOT reset anything. Then complete all remaining Problem 9 deliverables:
- fill the Actual sections of output/desk_tickets.html while preserving the Expected sections
- complete the Cash tab with the exact cash reconciliation
- create output/resolved_tickets.json
- create output/resolved_board.html with evidence/screenshots for tickets 101, 102, and 103
- append the real runs to output/audit_trail.json without deleting earlier records
- finish output/harness.md
- verify all three tickets are resolved
- verify the final checking balance directly against cash_accounts

Before declaring Problem 9 complete, give me a concise validation report showing:
Starting cash
Ticket 101 cash effect
Ticket 102 cash effect
Ticket 103 cash effect
Ending cash
Final status of 101, 102, and 103
Any human approvals
All required output files created/updated
````

---
