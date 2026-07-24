# Real GitHub onboarding

Kondai blocks the main workspace until a repository has been connected.

## Supported connection methods

### Public repository URL

No GitHub credentials are required. Paste:

```text
https://github.com/owner/repository
```

### GitHub OAuth

Create an OAuth App and configure:

```text
Homepage URL:
http://localhost:5173

Authorization callback URL:
http://localhost:8000/api/v1/integrations/github/oauth/callback
```

Then set:

```env
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
INTEGRATION_ENCRYPTION_KEY=
```

### Personal access token

The setup page accepts a token as a development fallback. Tokens are encrypted
before storage and never returned by the API.

## Information read from GitHub

- Repository metadata
- README
- Recursive file tree
- Language distribution
- Recent commits
- Open issues
- Key manifests and documentation

## Connected status rule

A source snapshot does not mark an integration as connected.

GitHub is considered connected only when:

1. Kondai can authenticate or access the public repository.
2. A repository has been selected.
3. The live repository sync has completed.
4. The initial product record has been created.
