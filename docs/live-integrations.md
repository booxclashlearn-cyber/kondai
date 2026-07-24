# Live business integrations

Kondai now supports four real business-data connectors after GitHub onboarding.

## 1. Product Database — Cloud Firestore

The founder uploads a Firebase/Google Cloud service-account JSON file and maps
collections for customers, accounts, subscriptions, events and generated
outputs. The backend encrypts the credential before storage and reads only a
bounded number of documents per mapped collection.

Recommended IAM role for the service account: a read-only Firestore/Datastore
viewer role. Do not use an owner credential.

## 2. Billing — Stripe

Use a Stripe restricted key with read permissions for account, customer,
subscription, invoice and price data. Kondai calculates:

- MRR and ARR
- Active subscriptions and customers
- Cancellations in the previous 30 days
- Estimated churn and retention
- Revenue collected in the previous 30 days
- Revenue at risk from past-due or cancel-at-period-end subscriptions

## 3. Product Analytics — PostHog

Enter the PostHog host, project ID and a personal API key with query access.
Kondai uses the Query API and HogQL to retrieve:

- Active users in the previous 30 days
- Event volume
- Top product events
- Unique users by event
- Activation rate for an optional activation event

## 4. Support Inbox — Gmail

Enable the Gmail API and create a Google OAuth Web application. Configure:

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GMAIL_REDIRECT_URI=http://localhost:8000/api/v1/integrations/gmail/oauth/callback
```

Authorized redirect URI:

```text
http://localhost:8000/api/v1/integrations/gmail/oauth/callback
```

Kondai requests read-only Gmail access, imports matching inbound messages as
support tickets, groups basic customer themes and sends the resulting support
snapshot into the business intelligence layer.

The Gmail readonly scope is restricted for a public application and may require
Google verification and a security assessment. During development, keep the
OAuth consent screen in testing mode and add specific test users.

## Credential storage

All service-account JSON, Stripe keys, PostHog keys and Google OAuth tokens are
stored only by the backend and encrypted with `INTEGRATION_ENCRYPTION_KEY`.
They are never returned from integration status endpoints.
