import { createHash } from 'node:crypto';
import type { APIGatewayProxyEventV2, APIGatewayProxyStructuredResultV2 } from 'aws-lambda';
import { createCognitoVerifier, type TokenVerifier } from './auth.js';
import { parseAgentMap, type AgentMap } from './agents.js';
import { createHarnessInvoker, type AgentInvoker } from './invokeAgent.js';

const MAX_BODY_BYTES = 16 * 1024;
const MAX_MESSAGE_CHARS = 4000;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{7,99}$/;

export interface Deps {
  verifyToken: TokenVerifier;
  agents: AgentMap;
  invoker: AgentInvoker;
}

const json = (statusCode: number, body: unknown): APIGatewayProxyStructuredResultV2 => ({
  statusCode,
  headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  body: JSON.stringify(body),
});

/**
 * AgentCore requires a 33+ character session id. Hashing it together with the caller's identity
 * means one user can never attach to another user's runtime session, even by guessing an id.
 */
export function runtimeSessionIdFor(userId: string, sessionId: string): string {
  return createHash('sha256').update(`${userId}:${sessionId}`).digest('hex');
}

export function createHandler(deps: Deps) {
  return async (event: APIGatewayProxyEventV2): Promise<APIGatewayProxyStructuredResultV2> => {
    // Function URLs have no authorizer, so the token is verified here before anything else.
    const user = await deps.verifyToken(event.headers?.authorization);
    if (!user) return json(401, { error: 'Unauthorized' });
    const userId = user.sub;

    const raw = event.isBase64Encoded
      ? Buffer.from(event.body ?? '', 'base64').toString('utf8')
      : (event.body ?? '');
    if (Buffer.byteLength(raw) > MAX_BODY_BYTES) return json(413, { error: 'Request too large' });

    let body: unknown;
    try {
      body = JSON.parse(raw);
    } catch {
      return json(400, { error: 'Body must be valid JSON' });
    }
    const { message, sessionId, agentId } = (body ?? {}) as Record<string, unknown>;

    if (typeof message !== 'string' || !message.trim() || message.length > MAX_MESSAGE_CHARS) {
      return json(400, { error: `message must be a non-empty string up to ${MAX_MESSAGE_CHARS} characters` });
    }
    if (typeof sessionId !== 'string' || !ID_PATTERN.test(sessionId)) {
      return json(400, { error: 'sessionId is missing or invalid' });
    }
    if (typeof agentId !== 'string' || !ID_PATTERN.test(agentId.padEnd(8, '_'))) {
      return json(400, { error: 'agentId is missing or invalid' });
    }
    const harnessArn = Object.hasOwn(deps.agents, agentId) ? deps.agents[agentId] : undefined;
    if (!harnessArn) return json(404, { error: `Unknown agent "${agentId}"` });

    try {
      const response = await deps.invoker.invoke({
        harnessArn,
        runtimeSessionId: runtimeSessionIdFor(userId, sessionId),
        runtimeUserId: userId,
        message: message.trim(),
      });
      return json(200, { response: response || 'The agent returned an empty response.', sessionId, agentId });
    } catch (err) {
      // Log details server-side only; never leak internals to the browser.
      console.error('Agent invocation failed', err);
      return json(502, { error: 'The agent could not be reached. Please try again.' });
    }
  };
}

export const handler = createHandler({
  verifyToken: createCognitoVerifier(
    process.env.COGNITO_USER_POOL_ID ?? '',
    process.env.COGNITO_CLIENT_ID ?? '',
  ),
  agents: parseAgentMap(process.env.AGENT_HARNESS_MAP),
  invoker: createHarnessInvoker(process.env.AGENT_REGION ?? process.env.AWS_REGION ?? 'us-east-1'),
});
