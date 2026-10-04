# Vireo Audio — Submission Form

## 1. What did you build, and what business outcome does it move?

I built an evidence-first Tier 1 support performance and coaching dashboard. It ranks agents using CSAT, median handle time, and first-response SLA breach rate, while comparing agents within the same team. A manager can then investigate a flagged agent using ticket themes and sample agent notes.

For Jan–Jun 2026, the strict Tier 1 baseline was a 9.2% first-response SLA breach rate, with 260 breaches across 2,840 tickets. The proposed goal is a 20% relative reduction, bringing the breach rate to about 7.3%. At approximately 650 tickets per week, this would avoid roughly ₹54,000 per quarter in ₹350 SLA credits.

## 2. What does one run cost, and what would a month cost at Vireo's volume (~650 tickets/week)?

The tool has ₹0 in external model/API cost per run because the current implementation performs the analysis locally using Python and Pandas and does not make an LLM API call.

At approximately 650 tickets per week, or roughly 2,817 tickets per month, the incremental external model/API cost remains ₹0 per month. Local machine compute is not separately priced.

## 3. How do you know it works? (sample size, checking method, error rate, failure cases)

The tool was tested on the Jan–Jun 2026 ticket window. It analyzed 2,840 strict Tier 1 tickets, with 1,230 CSAT responses and 23 agents meeting the minimum eligibility threshold of 30 tickets and 30 CSAT responses.

I checked the calculations against the supplied support policy. Tier 2 and operational teams are excluded from the Tier 1 ranking, blank CSAT responses are excluded rather than treated as zero, and legacy resolution timestamps are adjusted from UTC to IST before calculating handle time. The dashboard also checks for missing first responses and reports 0 for the selected analysis window.

The main known failure cases are auto-closed tickets affecting attendance, structurally different queues, and the possibility of interpreting an agent ranking without reviewing the underlying tickets. The tool therefore presents the Bottom 10 as a coaching shortlist rather than an automatic performance or bonus decision.
I did not estimate a statistical error rate because this is a deterministic rules-and-calculation pipeline rather than a predictive classifier; validation focused on calculation checks against the supplied policy and known edge cases.