# Stack of Dreams Labs

> Intelligent Agents. Real-World Impact.

Frontend for **agents.sudhirmishra.in**: a web interface for AI agents that will run on Amazon Bedrock AgentCore Runtime using the Strands Agents framework.

> **Access: invite-only.** Using the AI agents (the assistant and the AI for Good pilot) requires a sign-in, and accounts are
> created by an administrator. There is no self sign-up. To request access, contact the project owner. See
> `platform/docs/pilot-admin.md` for how invitations, quotas and access removal work.

**Status:** the React app runs on its own with mock data and a mock chat service (no AWS credentials needed, replies labelled
as mock). The optional pilot backend in `platform/` (real directory data, quotas, the `community_navigator` agent runtime) is
deployed separately in AWS us-east-2; the app uses it only when `VITE_PILOT_API_BASE_URL` is set.

Stack: React 19, TypeScript, Vite, Tailwind CSS 4, React Router, lucide-react, react-markdown, Vitest + Testing Library, ESLint, Prettier.

## Run locally

```bash
npm install
cp .env.example .env.local   # optional; mock mode is the default
npm run dev                  # http://localhost:5173
```

| Command           | Purpose                                 |
| ----------------- | --------------------------------------- |
| `npm run dev`     | Dev server                              |
| `npm run build`   | Typecheck + production build to `dist/` |
| `npm run preview` | Serve the production build              |
| `npm run lint`    | ESLint                                  |
| `npm run test`    | Vitest (single run)                     |
| `npm run format`  | Prettier                                |

## Environment variables

| Variable            | Default  | Description                                                              |
| ------------------- | -------- | ------------------------------------------------------------------------ |
| `VITE_USE_MOCK_API` | `true`   | `true` uses the in-browser mock. Set `false` to call the HTTP backend.   |
| `VITE_API_BASE_URL` | _(none)_ | Base URL of the API, no trailing slash. Used only when mock mode is off. |

Anything prefixed `VITE_` is embedded in public JavaScript. **Never put secrets or AWS credentials in these variables.** The app contains no AWS SDK and no credentials.

Tip: send `/fail` in mock mode to see the error and retry UI.

## Switching from mock to the AWS backend

1. Build the Lambda and API Gateway separately (not part of this repo).
2. Set, in `.env.local` or in the Amplify console's environment variables:
   ```
   VITE_USE_MOCK_API=false
   VITE_API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/<stage>
   ```
3. Enable CORS on the API for the site's origin.
4. The app will `POST ${VITE_API_BASE_URL}/chat`:
   ```json
   { "message": "Hello", "sessionId": "uuid", "agentId": "assistant" }
   ```
   and expects:
   ```json
   { "response": "Hello! How can I help?", "sessionId": "uuid", "agentId": "assistant" }
   ```
   This contract is provisional. Adjust `src/services/httpChatService.ts` and `src/types/chat.ts` if it changes. Authentication is not implemented yet.

## Project structure

```
src/
  app/          App.tsx, router.tsx
  components/   layout/, chat/, agents/, ui/
  pages/        Home, Chat, Agents, Architecture, About
  services/     chatService (selector), mockChatService, httpChatService, errors
  hooks/        useChat, useTheme
  data/         agent registry (add new agents here)
  types/        chat.ts, agent.ts
  utils/        session.ts (UUIDs + local storage)
  tests/        Vitest suites
  styles/       Tailwind entry + theme tokens
```

To add an agent, add an entry to `src/data/agents.ts`. Only agents with `interactive: true` open in chat.

## AI for Good / hackathon projects

Routes: `/ai-for-good`, `/ai-for-good/projects/:projectId`, and the reserved placeholder `/ai-for-good/projects/:projectId/app`.

**Add a project:** append an entry to `PROJECTS` in `src/data/projects.ts` (type `HackathonProject` in `src/types/project.ts`). Only `id`, `name`, `description`, `category` and `status` are required. Add `agentId`, `demoUrl`, `repoUrl` and `details` (overview, problem statement, solution, tech stack, architecture, team) once they really exist; missing values render as placeholders. Links must be http(s).

**Brand a project's app route:** set `branding` on the project (a `Partial<AppBranding>`, see `src/types/branding.ts`): `name`, `tagline`, `logo` (Lucide icon or `imageUrl`), `theme` (`accent`, `accent2`, `gradientFrom`, `gradientTo`), `nav`, `agents`, `defaultAgentId`, `footer`. Overrides are merged over `DEFAULT_BRANDING` in `src/config/branding.tsx` and applied by `BrandingProvider`. Shell and chat components read branding from context rather than hardcoding it.

The app route is a placeholder until a challenge is defined; replace `ProjectAppPage` content then.

## Authentication

Controlled by `VITE_AUTH_MODE`:

| Mode             | Behavior                                                                                           |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| `none` (default) | Public app, no sign-in, no token sent.                                                             |
| `mock`           | Fake sign-in button for local development. Provides **no real security** and issues no real token. |
| `oidc`           | Real sign-in with Amazon Cognito (or any OIDC provider) using Authorization Code + PKCE.           |

When auth is enabled, `/chat` requires sign-in (other pages stay public), the header shows Sign in / Sign out, and `httpChatService` sends `Authorization: Bearer <access token>`. A 401/403 shows a "sign in again" error.

**Cognito setup (outside this repo):**

1. Create a user pool and an app client **without a client secret**, with the Authorization Code grant and scopes `openid email profile`.
2. Add a hosted UI domain. Set allowed callback URLs to `https://agents.sudhirmishra.in/auth/callback` and `http://localhost:5173/auth/callback`, and sign-out URLs to the site origins.
3. Set `VITE_AUTH_MODE=oidc`, `VITE_AUTH_AUTHORITY`, `VITE_AUTH_CLIENT_ID` and `VITE_AUTH_LOGOUT_DOMAIN` (see `.env.example`).
4. Add a Cognito JWT authorizer on the API Gateway `/chat` route (backend work, not done here).

Tokens are held in memory only, so a page reload re-runs sign-in (usually instant while the Cognito session cookie is valid). The post-login redirect only accepts in-app paths. Client-side auth only controls the UI; the API must verify the token.

## Community Resource Navigator (AI for Good)

Routes: `/ai-for-good` (landing), `/ai-for-good/find`, `/ai-for-good/results`, `/ai-for-good/resources/:resourceId`, `/ai-for-good/assistant`, `/ai-for-good/dashboard`, `/ai-for-good/volunteer`. The earlier program/hackathon-projects page moved to `/ai-for-good/program`.

Code lives in `src/features/aiForGood/`. Structured data comes from a typed service (`src/services/resourceService.ts`, `mockResourceService.ts`, `httpResourceService.ts`) that is **separate from the chat service**; assistant replies are never parsed into inventory records.

| Variable                     | Default  | Meaning                                                                                                      |
| ---------------------------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `VITE_USE_MOCK_RESOURCES`    | `true`   | `true` uses built-in synthetic data; `false` calls the HTTP API                                              |
| `VITE_RESOURCE_API_BASE_URL` | _(none)_ | Base URL for `POST /resources/search`, `GET /resources/{id}`, `GET /resources` (provisional, no backend yet) |

**Mock data:** five fictional food banks mirroring the synthetic dataset behind the assistant's lookup tool, so results and assistant answers agree. Every record is flagged `isDemoData: true`, `verified: false`, and shown with a DEMO DATA label. There are no addresses, phone numbers, hours or timestamps, so those show "Not available" / "Contact provider to confirm", and Call/Directions buttons never appear. Diaper stock is not tracked, so diaper searches return an empty state. "Closest ZIP" ranks by ZIP similarity only (no real distances). Enter ZIP `00000` to see the error state.

**Assistant handoff:** "Ask AI" navigates to `/ai-for-good/assistant` with a prompt in router state (not the URL). The existing chat page sends it once through the unchanged chat service. Prompts tell the assistant to use only the supplied facts. Free-text search notes stay out of URLs.

## Backend

The chat API lives in `backend/` (Lambda Function URL + AgentCore harness). See `backend/README.md` for deploy steps. Not deployed by default.

## Pilot platform (AI for Good)

The real-data backend (DynamoDB, ingestion, quotas, query gateway, AgentCore runtime `community_navigator`) lives
in `platform/` and is **not deployed yet**. Start at `platform/README.md`, `platform/docs/deployment.md` and
`platform/docs/amplify-dns.md`. The frontend uses it when `VITE_PILOT_API_BASE_URL` is set, otherwise it keeps
using mock resources and the existing chat service (and says so on screen).

## Security notes

- Markdown is rendered with `react-markdown` with raw HTML skipped; `dangerouslySetInnerHTML` is not used. Links open with `rel="noopener noreferrer nofollow"`.
- Chat history is saved in the browser's `localStorage` (per agent). That is **not appropriate for confidential or regulated information**; the UI says so. Use "Clear conversation" to wipe it.
- A visible notice marks the app as an experimental demo.

## Deploying on AWS Amplify (not done by this repo)

`amplify.yml` contains the build settings (`npm ci`, `npm run build`, output `dist`). For client-side routing, add a rewrite in the Amplify console (Hosting → Rewrites and redirects):

| Source address                                                                                           | Target address | Type          |
| -------------------------------------------------------------------------------------------------------- | -------------- | ------------- |
| `</^[^.]+$\|\.(?!(css\|gif\|ico\|jpg\|js\|png\|txt\|svg\|woff\|woff2\|ttf\|map\|json\|webp)$)([^.]+$)/>` | `/index.html`  | 200 (Rewrite) |

Custom domain and DNS are intentionally not configured here.

## Limitations / TODO

- Backend (Lambda, API Gateway, AgentCore, Strands agent) is not built; the target architecture page is a design, not a deployment.
- Responses are not streamed; the HTTP contract is single request/response.
- No authentication or rate limiting.
- Research Agent and Multi-Agent Orchestrator are placeholders.
