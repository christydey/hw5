# Campus Customs Operations Desk: Dashboard Design

The dashboard (`frontend/`, React + Vite + TypeScript) is the front counter for the five-agent team. You use it to pick a ticket, start the team, watch them work, and approve any money that has to move. Every number and sentence on screen comes from the Problem 7 API at `http://localhost:8000`. The frontend holds no shop data and makes no shop decisions.

## Layout

The page is a three-column operations desk under a sticky top bar. The columns read left to right, in the order you work.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▣ Campus Customs   [Shop date Mon, Aug 31 2026] [● Backend live] [2 awaiting] │
│   Operations Desk                                  ┌ CHECKING ─────┐ [Reset] │
│                                                    │ $3,400.00     │         │
│                                                    └───────────────┘         │
├───────────────┬──────────────────────────────────────┬───────────────────────┤
│ TICKETS       │ CUSTOMER ORDER · TAUHID ZAMAN  [OPEN]│ APPROVALS   [1 waiting]│
│ ┃#101 Bulldog │ #101 Bulldog tee   [▶ Start agent team]│ ┌ Pay invoice #501 ─┐ │
│ ┃#102 Rent due│ ─ status banner ─────────────────────│ │ $840.00  [Approve] │ │
│ ┃#103 Hoodies │ [Boss][Inventory][Accounting][Fac][CS]│ └───────────────────┘ │
│               │ NOW ◉ Accounting  Called check_payment│ WHO DID WHAT           │
│               │ LIVE ACTIVITY                        │ ┌ Boss ─────────────┐ │
│               │  ◉ Boss picked up a task             │ │ final report …    │ │
│               │  ◉→◉ Boss hands off to Inventory     │ └───────────────────┘ │
│               │     ↳ get_backorder_and_vendor_…     │ ┌ Inventory ────────┐ │
│               │  ◉ Inventory  final report …         │ └───────────────────┘ │
└───────────────┴──────────────────────────────────────┴───────────────────────┘
```

- **Top bar:** brand, the shop's date (`desk.date_today`, not the computer clock), backend connection status, a count of payments awaiting approval, the checking balance card, and **Reset shop**.
- **Left (Tickets):** the three tickets as cards. You can see at a glance which are open, running or resolved.
- **Center (Ticket detail):** the selected ticket's header and run button, a one-line status banner, the five-agent roster, a "Now" strip naming the agent currently working, and the live activity feed.
- **Right rail:** **Approvals** on top, because it's the one thing that needs your hand. **Who did what** sits below it, with one summary card per participating agent.

Below 1280 px the right rail moves under the main area as two columns. Below 860 px everything stacks into one column.

## Visual design choices

- **Black and pink.** A near-black background (`#09090b`) with layered charcoal panels, and hot pink (`#ff4fa3`) as the brand and action color: the primary button, open tickets, the selected ticket, and approval prompts. Two faint pink radial glows in the background corners keep the black from feeling flat.
- **One accent per meaning.** Pink means "act here / brand". Green means done or paid. Amber means a safety check or guardrail. Red means an error. Each agent's own color is used only for that agent.
- **Hierarchy through weight, not boxes.** Small uppercase labels (TICKETS, LIVE ACTIVITY, APPROVALS) sit above large, heavy values: the ticket title, the $ amounts, the balance. Monospace marks database identifiers (SKUs, tool calls, `invoice #501`) so they read as data rather than prose.
- **Motion only where something is happening.** Running tickets get a moving light along their edge, the working agent's avatar pulses, the feed shows a "typing" indicator, and the cash card flashes when the balance changes. Everything else is still, and all animation is turned off under `prefers-reduced-motion`.

## How the five agents are distinguished

Each agent has a fixed color, icon and title, defined once in `src/agents.ts` and used the same way everywhere: roster, feed, summaries, approval "prepared by" tags.

| Agent | Color | Icon | Why |
|---|---|---|---|
| Boss | Pink `#ff4fa3` | Crown | The Boss is the shop's voice, so it wears the brand color. |
| Inventory | Teal `#2dd4bf` | Package | A cool "stockroom" color. |
| Accounting | Amber `#fbbf24` | Calculator | The color of money and of caution. |
| Facilities | Violet `#a78bfa` | Building | Distinct from the others; "the building". |
| Customer Service | Sky `#38bdf8` | Speech bubbles | A friendly, conversational blue. |

The colors were picked to stay distinguishable from each other on black. Every use also pairs the color with an icon and a name, so color is never the only cue.

In the **roster**, each agent is a tile:
- **Working:** filled with its tint, glowing border, pulsing avatar.
- **Waiting on a teammate:** dashed border, labelled e.g. "Waiting on Accounting".
- **Done:** solid border.
- **Not called:** greyed out, so the agents the Boss chose to leave out are as obvious as the ones it used.

## Open, running and resolved tickets

| State | Ticket card | Detail header |
|---|---|---|
| **Open** | Pink left bar, pink outlined **OPEN** pill with a blinking dot | Pink **Start agent team** button |
| **Running** | Animated light sweeping along the left bar, solid pink **RUNNING** pill with a spinner | Button becomes a disabled "Agents working…"; pink "working" banner |
| **Resolved** | Green left bar, dimmed text, green **RESOLVED** pill, and a tilted green **RESOLVED** rubber stamp in the corner | Green "Resolved" banner; hint to reset the shop to run it again |
| **Failed run** | Stays **OPEN** | Red banner; button becomes **Run team again** |

The panel heading keeps a running count ("2 open · 1 resolved"). A ticket with payments waiting shows a pink "awaiting your approval" line on its card, so you can find it without opening it.

## How agent activity is displayed

The live feed reads `/api/events` (built on `output/audit_trail.json`). It polls every 1.5 s while a run is active and every 5 s otherwise. Each event type gets its own treatment:

- **What an agent says** appears as a chat bubble in the agent's color, labelled *picked up a task*, *thinking* or *final report*. Final reports are tinted with the agent's color so they stand out from intermediate steps.
- **Hand-offs** appear as a row with both avatars and an arrow ("Boss hands off to Inventory"), with the delegated question quoted underneath. Refused or failed hand-offs turn amber and show the reason.
- **MCP tool calls** appear as compact monospace lines (`↳ get_vendor_ship_status(vendor_id=1) — ok / cached`), indented under the agent that made them. Tools an agent decided to call also show as small pink chips on its bubble.
- **Guardrails** appear as amber shield rows. Examples: "Only Accounting prepares payment proposals", or a payment amount corrected from the database.
- **System milestones** appear as full-width lines: run started, approvals prepared (pink), ticket resolved (green), human approvals (neutral), errors (red).

Delegation depth indents each item slightly, so a Boss → Facilities → Accounting chain reads as a nested conversation. The feed follows new items automatically unless you've scrolled up to read.

The **Now** strip above the feed always names the one agent doing the work right now, with its latest line.

The **Who did what** rail turns the same events into one card per participating agent, in the order they joined:
- the agent's latest final report, clamped to five lines with *Show more*, plus an "Asked 2×" note if it was consulted more than once
- how many MCP calls it made and which tools
- which teammates it handed off to
- how many guardrail checks touched its work

The feed shows only the ticket's most recent run since the last reset, so a fresh run always starts on a clean desk.

## How approvals are presented

Approvals are the only place money can move, so the panel is designed to be impossible to miss and hard to click by accident:

- **Visibility.** When anything is pending, the whole Approvals panel gets a pink glow and a "N waiting" badge. A status banner on the ticket says "payment needs your approval. Nothing has been paid yet." The top bar shows the count across all tickets.
- **The card.** Each card shows:
  - a plain-language title ("Pay invoice #501", "Pay rent · lease #1 (due 2026-09-02)", "Buy 12 × CC-HOOD-NAVY from vendor #1")
  - the amount, large
  - which agent prepared it (colored tag) and which account it comes from
  - the agent's reason
- **Approving.** **Approve $840.00** opens a confirmation dialog. It restates the payment and the current balance, explains that the backend re-checks everything before paying, and asks for your name, which is remembered for next time. Only then does it call `POST /api/approvals/{id}/approve`. If the backend refuses (for example, not enough cash), the dialog shows the exact reason and nothing changes. **Reject** works the same way.
- **After approval.** The card turns green ("Approved & paid"), shows who approved it and the balance before → after, and the feed records the human decision.
- **Blocked proposals.** A proposal that failed the database checks when it was prepared shows with a dashed border, an amber "Blocked by safety check" label, a struck-through amount and the exact reasons. There's no Approve button, so a payment the system has already ruled out can't even be attempted.
- **What's shown.** Pending approvals are always shown. Decided ones belong to the ticket's latest run, so history from before a reset doesn't look like the current state.

Agents never touch this panel. They can only propose; the Approve button is the only path to the approval route.

## How the checking balance is displayed

The balance card sits top-right on every screen. It shows the label (CHECKING), the balance in large tabular figures, and the as-of date, read live from `cash_accounts` via `GET /api/cash`.

It refreshes on every poll and immediately after any approval or reset. When the value changes, the card flashes pink, the amount turns pink, and the footer briefly shows the change with a direction arrow, for example "↓ −$840.00 · was $3,400.00". You literally see the money leave.

## Creative choices that make it pleasant and useful

- **It feels like a real desk.** The header names the shop's own date and location ("Operations Desk · Chapel Street"). Resolved tickets get a rubber stamp, like a paper ticket spiked at a real counter.
- **You can watch the team think.** The roster, the "Now" strip, hand-off rows and per-agent colors turn an opaque multi-agent run into something you can follow live, including the moments when a guardrail stops an agent.
- **"Not called" is information.** Dimming the agents the Boss left out shows the routing decision itself, which is exactly what Problem 6's plan predicted and what you'll compare in the next problem.
- **Safety is visible.** Guardrail rows, struck-through blocked payments, the "nothing has been paid yet" banner and the re-check notice in the approval dialog all make the human-in-the-loop design legible instead of hidden.
- **Honest states.**
  - Skeleton cards while loading.
  - A red banner with the exact start command when the backend is down; it keeps retrying.
  - Friendly empty states ("No agent activity yet…", "Nothing needs approval for this ticket").
  - Failed runs that say so and stay open.
  - Backend errors shown verbatim in place.
- **One-click fresh start.** **Reset shop** (with confirmation) restores the database through the real reset route, clears the feed, and puts the balance back, ready for another run.

## Files

| File | Purpose |
|---|---|
| `frontend/src/api.ts` | Typed client: one function per Problem 7 route |
| `frontend/src/types.ts` | TypeScript mirrors of `backend/models.py` |
| `frontend/src/useDesk.ts` | Polling, state, and the actions (run, approve, reject, reset) |
| `frontend/src/activity.ts` | Groups a ticket's events by agent for the roster and summaries |
| `frontend/src/agents.ts` | The five agents' colors, icons and labels |
| `frontend/src/components/*` | Header/cash card, ticket list, ticket detail and roster, activity feed, approvals, summaries, dialogs |
| `frontend/src/styles.css` | The black-and-pink design system and all motion |
