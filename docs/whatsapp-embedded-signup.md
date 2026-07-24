# WhatsApp Embedded Signup v4

Kondai uses Meta Embedded Signup so founders connect WhatsApp with one guided
Facebook window. They do not enter access tokens, application secrets, WABA IDs,
Phone Number IDs or webhook URLs.

## Founder experience

```text
Connections
→ Connect WhatsApp
→ Continue with Facebook
→ Choose or create a business portfolio
→ Choose or create a WhatsApp Business Account
→ Select and verify the business phone number
→ Finish
```

The browser receives a short-lived authorization code and session information.
The code is sent to FastAPI, which exchanges it server-side, verifies the phone
number, subscribes the WABA to the Kondai Meta app, registers the number when
required and encrypts the resulting token.

## One-time Kondai platform setup

The Kondai platform owner must configure Meta once.

1. Create or open the Kondai Meta Business app.
2. Add WhatsApp.
3. Add Facebook Login for Business.
4. Create an Embedded Signup v4 configuration.
5. Configure allowed JavaScript SDK domains and OAuth redirect settings for the
   deployed Kondai frontend.
6. Configure the WhatsApp webhook callback shown below.
7. Subscribe the Meta app to the `messages` webhook field.
8. Complete the relevant Meta business verification, app review and Tech
   Provider requirements before onboarding external customer businesses at
   scale.

## Backend environment

```env
META_APP_ID=
META_APP_SECRET=
META_EMBEDDED_SIGNUP_CONFIG_ID=

# Usually blank for the JavaScript SDK code flow. Set it only when the Meta
# login configuration requires the same explicit redirect URI during exchange.
META_EMBEDDED_SIGNUP_REDIRECT_URI=

# Optional. Use only when the Meta configuration requires a specialised flow,
# such as an eligible WhatsApp Business App coexistence setup.
META_EMBEDDED_SIGNUP_FEATURE_TYPE=

META_WEBHOOK_VERIFY_TOKEN=
PUBLIC_API_BASE_URL=https://api.kondai.example
META_AUTO_REGISTER_PHONE_NUMBER=true
WHATSAPP_GRAPH_VERSION=v25.0
```

The platform callback URL is:

```text
https://api.kondai.example/api/v1/integrations/whatsapp/webhook
```

The callback and verification token are configured once in the Kondai Meta app,
not once per customer.

## Frontend implementation

The frontend loads the Meta JavaScript SDK only when the WhatsApp connection
panel opens. It calls `FB.login` with:

```text
config_id
response_type=code
override_default_response_type=true
sessionInfoVersion=3
```

It listens for the `WA_EMBEDDED_SIGNUP` browser message and waits for both:

- the authorization code; and
- the finished session containing `waba_id` and `phone_number_id`.

Only then does it call the backend completion endpoint.

## Backend completion

`POST /api/v1/integrations/whatsapp/embedded/complete` performs:

1. Authorization-code exchange.
2. Phone-number verification through Graph API.
3. `POST /<WABA_ID>/subscribed_apps`.
4. Phone registration when enabled.
5. Encrypted token storage.
6. Creation of global webhook routing records for the WABA and phone number.

## Multi-tenant webhook routing

Meta uses one callback URL for the Kondai app. Incoming events contain a WABA ID
and phone-number metadata. Kondai maps those identifiers to the correct
workspace using records stored under the internal `__kondai_system__` workspace.

The webhook:

- verifies `X-Hub-Signature-256` with the platform Meta App Secret;
- rejects events for unknown WABAs or phone numbers;
- deduplicates messages by Meta message ID;
- creates or updates the correct customer conversation and customer issue.

## Legacy developer endpoint

The old credential-entry connector remains as a hidden backend endpoint for
migration and emergency development use. It is not shown to founders and is not
part of the normal product experience.
