# Kondai architecture

```text
Sources of truth
GitHub · Database · Billing · Analytics · Support · Market
                         ↓
              Product Knowledge Graph
                         ↓
             Founder Intelligence Agent
             observes · predicts · recommends
                         ↓
                 Founder approval
                         ↓
                    Growth Agent
                 prepares · executes
                         ↓
                      Customers
                         ↓
                    Support Agent
              answers · verifies · listens
                         ↓
              feedback returns to graph
```

Local mode uses React, FastAPI, JSON persistence and deterministic AI fallback. Production mode targets Cloud Run, Vertex AI, Firestore, Cloud Tasks and Cloud Scheduler.
