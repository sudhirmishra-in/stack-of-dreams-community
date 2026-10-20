# Amplify Hosting and agents.sudhirmishra.in

## What was inspected (read-only)
* DNS provider: **GoDaddy** (`ns37/ns38.domaincontrol.com`), not Route 53 (no hosted zones in the account).
* `sudhirmishra.in` apex: 4 A records (185.199.108-111.153) = GitHub Pages. `www`: CNAME `sudhirmishra-in.github.io`. **Do not touch.**
* `agents.sudhirmishra.in`: no record. No wildcard record, no CAA records, so no conflicts and no CAA blocking certificate issuance.
* Amplify is allowed in **us-east-2** only (denied in us-east-1). No Amplify apps exist yet.
* The app (`stack-of-dreams-communitynavigator/`) is **not a git repository**: there is no GitHub repo to connect yet.

## Prerequisite: a GitHub repo
Create e.g. `sudhirmishra/stack-of-dreams-labs`, push this folder (the repo root = `stack-of-dreams-communitynavigator/`; keep `.env*` out:
`.gitignore` already excludes them). This is separate from the `sudhirmishra-in.github.io` Pages repo.

## Console steps (recommended; the console handles the GitHub app authorization)
1. Region **US East (Ohio) us-east-2** -> AWS Amplify -> *Create new app* -> GitHub -> select repo + `main`.
2. Build settings: it detects `amplify.yml` (npm ci, npm run build, `dist`). It also applies the security headers.
3. Environment variables (Hosting -> Environment variables), public identifiers only:
   `VITE_AUTH_MODE=oidc`, `VITE_AUTH_AUTHORITY=https://cognito-idp.us-east-2.amazonaws.com/us-east-2_tPaKrhmEX`,
   `VITE_AUTH_CLIENT_ID`, `VITE_AUTH_REDIRECT_URI=https://agents.sudhirmishra.in/auth/callback`,
   `VITE_AUTH_SCOPE=openid email`, `VITE_AUTH_LOGOUT_DOMAIN`, `VITE_USE_MOCK_API=false`, `VITE_API_BASE_URL` (existing
   chat), `VITE_PILOT_API_BASE_URL`, `VITE_USE_MOCK_RESOURCES=false` (no map key needed).
4. **SPA rewrite** (Hosting -> Rewrites and redirects), type 200:
   source `</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>` target `/index.html`.
   CLI equivalent: `aws amplify update-app --region us-east-2 --app-id <id> --custom-rules '[{"source":"</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>","target":"/index.html","status":"200"}]'`
5. Deploy once and open the `*.amplifyapp.com` URL to confirm it builds.

## Custom domain (needs your explicit go-ahead; changes public DNS)
1. Amplify -> Domain management -> *Add domain* -> `sudhirmishra.in` -> **subdomain `agents` only**, branch `main`.
   (Amplify may offer to manage the apex/www too: **remove those**, we only want `agents`.)
2. Amplify shows the **exact** DNS records: an ACM certificate-validation CNAME and the `agents` CNAME (to a
   `*.cloudfront.net` name). Copy them from the console; **do not guess targets**.
3. In GoDaddy -> DNS for sudhirmishra.in, **add** those two CNAME records (host = only the label, e.g. `agents` and
   `_abc123.agents`, without `.sudhirmishra.in`). Do not edit or delete the existing A records or `www`.
4. Wait for status *Available* (certificate validation + propagation, often minutes to an hour).
5. Cognito: add `https://agents.sudhirmishra.in/auth/callback` and `https://agents.sudhirmishra.in` to the app client.

## Verify
```bash
dig +short CNAME agents.sudhirmishra.in          # the Amplify/CloudFront name
dig +short A sudhirmishra.in                      # still the 4 GitHub Pages IPs
curl -sI https://agents.sudhirmishra.in | head -12   # 200, HSTS, headers
curl -s -o /dev/null -w '%{http_code}\n' https://agents.sudhirmishra.in/ai-for-good/find    # 200 (SPA rewrite)
```
Then in a browser: HTTPS lock; sign-in redirects to Cognito and back; `/ai-for-good/results?...` deep link works;
results load (Network tab: calls to the Function URL succeed, no CORS errors: the origin must be in `AllowedOrigins`);
the map renders. The Content-Security-Policy header ships as **Report-Only**: open the console, exercise sign-in,
search, the map and the assistant, and if there are no violations rename the header key in `amplify.yml` to
`Content-Security-Policy` to enforce it.
