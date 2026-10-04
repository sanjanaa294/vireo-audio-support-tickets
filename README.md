# Vireo Audio — Support Performance Coach

## What this tool does

This is an evidence-first AI-assisted support coaching dashboard for Vireo Audio. It:

- analyzes Tier 1 support agents using CSAT, median handle time, and first-response SLA breaches;
- peer-normalizes the three signals within each team;
- produces a transparent bottom-ten coaching list;
- generates an evidence-based coaching brief for a selected agent;
- calculates the financial impact of SLA breaches using Vireo's stated ₹350 breach credit;
- lets reviewers download the bottom-ten result as CSV.

Tier 2 is excluded because Vireo's policy says Tier 2 work is multi-touch and should not be compared with Tier 1 on volume metrics.

## Run from a clean machine

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The app opens in a browser. The supplied CSVs are loaded automatically. You can also upload replacement `tickets.csv` and `agents.csv` from the sidebar.

## Important methodology

- Analysis defaults to Jan–Jun 2026, matching the business-review window.
- CSAT blanks are excluded from averages.
- Only agents with at least 30 tickets and 30 CSAT responses enter the bottom-ten ranking.
- Ranking is peer-normalized within team.
- Risk score: 50% CSAT risk, 30% median handle-time risk, 20% SLA-breach risk.
- Legacy resolution timestamps receive a +5:30 IST correction before handle-time calculation, consistent with the supplied policy/README treatment of migrated timestamps.
- SLA targets: chat 15 min, voice 2 h, social 4 h, email 8 h.
- Each first-response SLA breach carries a ₹350 store credit.

## Business goal

At approximately 650 tickets/week, reduce Tier 1 first-response SLA breaches by 20% relative. The observed Jan–Jun 2026 Tier 1 baseline is about 9.1%; the target is about 7.3%. At ₹350 per breach, that is approximately ₹54,000 in avoided SLA credits per quarter.

## AI assistance

The core analysis is deterministic and reproducible so the result works without an API key. The coaching brief uses evidence from the selected agent's tickets and lightweight text-theme extraction. This avoids making an external model a dependency of the core business calculation.

## Limitations

The dashboard is a coaching triage tool, not an automated disciplinary or bonus decision. Flagged agents should be reviewed against actual tickets and operating context, especially Returns, Logistics, and other queues where work complexity differs.

## Development and AI-tool disclosure

ChatGPT was used during development as a coding, debugging, and validation assistant.
The final application runs locally using Python, Pandas, and Streamlit and does not make external LLM/API calls.

External model/API cost for one run: ₹0.

Discarded/changed work included an initial Tier 1 filter that incorrectly included operational teams. After checking the supplied support policy, the filter was changed to include only Chat Frontline, Email Frontline, and Voice Frontline. An additional text-theme extraction bug was identified and fixed during testing.
