# Agentic Activation and Founder Operating Cycle

Kondai begins its first operating review when both required sources are available:

1. A GitHub repository has been selected and read.
2. The Product Database connection has completed a live Firestore snapshot.

The internal specialist services remain hidden from the user. The founder sees one
coordinated Kondai experience.

## Initial review lifecycle

```text
GitHub + Product Database connected
        ↓
Confirm connected sources
        ↓
Review codebase and recent product changes
        ↓
Review customers, accounts and business records
        ↓
Create source-linked evidence bundles
        ↓
Rank findings and one recommended next action
        ↓
Ask the founder: “May I continue?”
```

Every finding records the exact evidence keys used to support it. Missing Stripe,
PostHog or customer-conversation connections are stated as limitations rather than
being silently filled with assumptions.

## Founder decision

The founder can:

- Continue with the recommended direction.
- Change the title, action, audience, channel or success measure.
- Inspect the supporting evidence.
- Review lower-ranked alternatives.
- Put the recommendation on hold.

Continuing approves only the strategic direction. It does not authorise an external
action.

## Work preparation

After the founder continues, Kondai creates an action plan and prepares the first
reviewable deliverable.

For a growth workflow this means:

- Creating the campaign plan.
- Selecting the approved audience definition.
- Producing a grounded campaign asset.
- Creating a final approval record.

For customer care it means preparing grounded replies or escalating uncertain
cases. For product or engineering work it creates an evidence-linked internal task.

## Execution controls

Prepared content or customer replies remain in final approval until explicitly
approved. Execution uses the configured provider. When no outbound provider is
configured, the execution record remains honest about using the local mock adapter.

## Outcome monitoring

After execution, Kondai creates an outcome check linked to the original
recommendation, plan, approvals and baseline metrics. Refreshing the outcome records
what has executed and prepares the workflow for comparison with later connected
billing, analytics and customer data.

## API surface

```text
GET  /api/v1/operations/command-center
GET  /api/v1/operations/readiness
POST /api/v1/operations/initial-review
GET  /api/v1/operations/runs/{run_id}
GET  /api/v1/operations/latest-review
POST /api/v1/operations/recommendations/{id}/continue
POST /api/v1/operations/recommendations/{id}/hold
PATCH /api/v1/operations/recommendations/{id}
POST /api/v1/operations/plans/{id}/outcome/refresh
```

## Operational collections

```text
operation_runs
operation_steps
business_reviews
evidence_bundles
review_findings
recommendations
action_plans
action_steps
internal_tasks
approvals
outcome_checks
```
