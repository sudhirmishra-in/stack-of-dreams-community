/** Facts about the running system, kept as data so the page and its tests stay in step. Update when the system changes. */

export type Status = 'live' | 'legacy' | 'planned' | 'disabled';

export interface MapNode {
  name: string;
  detail: string;
  status: Status;
  region?: string;
}

export interface Layer {
  id: string;
  title: string;
  caption: string;
  nodes: MapNode[];
  /** What travels to the next layer down. */
  next?: string;
}

export const LAYERS: Layer[] = [
  {
    id: 'users',
    title: 'People',
    caption: 'Invite-only pilot users on the public site',
    next: 'HTTPS. The browser keeps the access token in memory only and never holds AWS credentials.',
    nodes: [
      {
        name: 'React app on AWS Amplify',
        detail:
          'agents.sudhirmishra.in. Every push to main builds, lints and tests before it goes live. Route 53 holds the DNS.',
        status: 'live',
        region: 'us-east-2',
      },
      {
        name: 'Amazon Cognito',
        detail:
          'Password sign-in for invited users, plus Google sign-in. A pre sign-up Lambda lets only allow-listed Google emails create an account, and they stay pending until approved.',
        status: 'live',
        region: 'us-east-2',
      },
    ],
  },
  {
    id: 'api',
    title: 'Pilot API',
    caption: 'One Lambda Function URL, token verified in code',
    next: 'Navigator questions go to the runtime. General questions go to the research harness.',
    nodes: [
      {
        name: 'API Lambda',
        detail:
          'Checks the Cognito access token, the pending-approval flag and the kill switch. Reserves quota atomically before any model is called, then settles real token use. Also serves search, details, routes and the map proxy.',
        status: 'live',
        region: 'us-east-2',
      },
      {
        name: 'Usage ledger (DynamoDB)',
        detail:
          'Per-user daily and monthly counters, a pilot-wide daily cap, one request at a time per user, approvals and the allow-list. Each assistant keeps its own per-user counters.',
        status: 'live',
        region: 'us-east-2',
      },
    ],
  },
  {
    id: 'agents',
    title: 'Assistants',
    caption: 'Two agents with different jobs',
    next: 'Model calls go to Amazon Bedrock. Directory tools read DynamoDB and Amazon Location.',
    nodes: [
      {
        name: 'AI for Good: community_navigator runtime',
        detail:
          'Amazon Bedrock AgentCore Runtime running a Strands orchestrator with four specialist agents (discovery, inventory, capacity, location). It prefers deterministic tools, delegates at most 3 times, and an output guard removes any phone, link or number the tools did not return.',
        status: 'live',
        region: 'us-east-2',
      },
      {
        name: 'General AI Assistant: research harness',
        detail:
          'An AgentCore harness on Amazon Nova Lite with no tools. Answers general and technical questions, declines to invent citations, and points food questions to the AI for Good assistant.',
        status: 'live',
        region: 'us-east-1',
      },
      {
        name: 'Legacy chat Lambda and testagent',
        detail:
          'The original React to Lambda to AgentCore path. Kept as the rollback route, capped at 2 concurrent runs, and no longer used by the website.',
        status: 'legacy',
        region: 'us-east-1',
      },
    ],
  },
  {
    id: 'services',
    title: 'Models and tools',
    caption: 'What the agents call',
    nodes: [
      {
        name: 'Amazon Bedrock models',
        detail:
          'Nova Lite for the agents. Nova Micro only for the small classifier that checks ambiguous questions.',
        status: 'live',
        region: 'us-east-2 and us-east-1',
      },
      {
        name: 'Directory data (DynamoDB)',
        detail:
          'Real OpenStreetMap provider records (unverified, no inventory), citywide service-activity figures, and clearly labelled demo records.',
        status: 'live',
        region: 'us-east-2',
      },
      {
        name: 'Amazon Location Service',
        detail:
          'ZIP geocoding, travel time and distance, and the map tiles, all through the API so no map key reaches the browser.',
        status: 'live',
        region: 'us-east-2',
      },
    ],
  },
];

export interface FlowStep {
  title: string;
  detail: string;
}

export const REQUEST_FLOW: FlowStep[] = [
  {
    title: 'Sign in',
    detail:
      'Cognito issues an access token. A Google account can only be created if its email is on the allow-list, and it stays pending until the owner approves it.',
  },
  {
    title: 'Ask a question',
    detail:
      'The browser calls the pilot API with the token, the question and which assistant (navigator or research).',
  },
  {
    title: 'Verify and gate',
    detail:
      'The API verifies the token signature, issuer, client and type. Pending, disabled or switched-off requests are refused here, before anything costs money.',
  },
  {
    title: 'Reserve quota',
    detail:
      'One atomic DynamoDB transaction checks the user daily and monthly limits, the pilot-wide cap and concurrency. Over the limit returns 429 with no model call.',
  },
  {
    title: 'Route',
    detail:
      'Navigator questions pass a deterministic topic filter (and a small classifier only when unclear) before reaching the runtime. General questions go straight to the research harness.',
  },
  {
    title: 'Answer',
    detail:
      'The agent reasons with Amazon Nova Lite. The navigator calls directory tools and returns citations and caveats. Real inventory is never invented: it says unknown.',
  },
  {
    title: 'Settle and measure',
    detail:
      'The API records the real tokens used against the quota, emits metrics, and returns the answer with the remaining allowance.',
  },
];

export interface Pipeline {
  title: string;
  steps: { name: string; detail: string }[];
}

export const DATA_PIPELINE: Pipeline = {
  title: 'Keeping the directory fresh',
  steps: [
    {
      name: 'Public sources',
      detail:
        'OpenStreetMap (Overpass) and NYC Open Data. 211 and partner feeds exist as adapters but stay disabled until authorized.',
    },
    {
      name: 'EventBridge Scheduler',
      detail: 'OSM daily and weekly full runs, NYC Open Data monthly.',
    },
    {
      name: 'Ingest Lambda',
      detail:
        'Validates, normalizes, de-duplicates and upserts with retries, and never deletes on a partial run.',
    },
    {
      name: 'DynamoDB directory',
      detail: 'Every record keeps its source, timestamps and verification status.',
    },
    {
      name: 'Freshness Lambda',
      detail: 'Hourly, read-only: reports how many hours since each source last synced.',
    },
  ],
};

export const OBSERVABILITY: Pipeline = {
  title: 'Watching it run',
  steps: [
    {
      name: 'Metrics',
      detail:
        'The API and ingest Lambda print CloudWatch metrics (requests, latency, tokens, estimated cost, quota and sign-in refusals, sync health).',
    },
    {
      name: 'Traces',
      detail:
        'The runtime sends spans to CloudWatch with prompts and tool payloads removed before export. Agents are named so traces show who did what.',
    },
    {
      name: 'Alarms and budget',
      detail: 'CloudWatch alarms and a monthly budget notify through an SNS topic.',
    },
  ],
};

export interface Guardrail {
  title: string;
  detail: string;
}

export const GUARDRAILS: Guardrail[] = [
  {
    title: 'Invite-only',
    detail: 'Admin-created users, or allow-listed Google emails that the owner approves.',
  },
  {
    title: 'Server-side limits',
    detail:
      'Per-user daily and monthly quotas, a pilot-wide cap, one request at a time, and a kill switch.',
  },
  {
    title: 'Grounded answers',
    detail:
      'Tool results only; unsupported contacts and numbers are removed; sources and caveats are shown.',
  },
  {
    title: 'Private telemetry',
    detail: 'Logs and traces carry no prompts, tokens or emails; users appear only as hashes.',
  },
];

export interface StatusRow {
  item: string;
  status: Status;
  note: string;
}

export const STATUS: StatusRow[] = [
  {
    item: 'Website, sign-in, both assistants, quotas, approvals',
    status: 'live',
    note: 'In use by invited users.',
  },
  {
    item: 'Directory sync and freshness reporting',
    status: 'live',
    note: 'Scheduled; data is community-sourced and unverified.',
  },
  {
    item: 'Metrics and traces',
    status: 'live',
    note: 'Flowing; used for checks, not yet on a dashboard.',
  },
  {
    item: 'CloudWatch observability dashboard and new alarms',
    status: 'planned',
    note: 'Next phase.',
  },
  {
    item: 'Admin monitoring page in the app',
    status: 'planned',
    note: 'Optional, after the dashboard.',
  },
  {
    item: '211 and partner data feeds',
    status: 'disabled',
    note: 'Adapters built; off until access is authorized.',
  },
  {
    item: 'Per-user limits on the legacy chat path',
    status: 'legacy',
    note: 'None; the path is capped at 2 concurrent runs and kept only for rollback.',
  },
];
