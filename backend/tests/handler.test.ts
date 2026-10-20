import { describe, expect, it, vi } from 'vitest';
import type { APIGatewayProxyEventV2 } from 'aws-lambda';
import { createHandler, runtimeSessionIdFor } from '../src/handler.js';
import { parseAgentMap } from '../src/agents.js';
import { stripThinking } from '../src/invokeAgent.js';

const ARN = 'arn:aws:bedrock-agentcore:us-east-1:111111111111:harness/h-1';
const SID = '9c14781f-fa3e-4ea0-bdb3-9df8c9017ca8';

function event(body: unknown, token: string | null = 'good-token'): APIGatewayProxyEventV2 {
  return {
    body: typeof body === 'string' ? body : JSON.stringify(body),
    isBase64Encoded: false,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  } as unknown as APIGatewayProxyEventV2;
}

const verifyToken = async (h: string | undefined) =>
  h === 'Bearer good-token' ? { sub: 'user-1' } : null;

const setup = (impl = async () => 'Hello!') => {
  const invoke = vi.fn(impl);
  return { invoke, handler: createHandler({ verifyToken, agents: { assistant: ARN }, invoker: { invoke } }) };
};
const valid = { message: 'Hi', sessionId: SID, agentId: 'assistant' };

describe('chat handler', () => {
  it('returns the agent reply in the frontend contract shape', async () => {
    const { handler, invoke } = setup();
    const res = await handler(event(valid));
    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body!)).toEqual({ response: 'Hello!', sessionId: SID, agentId: 'assistant' });
    expect(invoke).toHaveBeenCalledWith(
      expect.objectContaining({ harnessArn: ARN, runtimeUserId: 'user-1', message: 'Hi' }),
    );
  });

  it('scopes the runtime session to the user', async () => {
    const a = runtimeSessionIdFor('user-1', SID);
    expect(a).toHaveLength(64);
    expect(a).not.toBe(runtimeSessionIdFor('user-2', SID));
    expect(a).toBe(runtimeSessionIdFor('user-1', SID));
  });

  it('rejects missing or invalid tokens before doing anything else', async () => {
    const { handler, invoke } = setup();
    expect((await handler(event(valid, null))).statusCode).toBe(401);
    expect((await handler(event(valid, 'forged'))).statusCode).toBe(401);
    expect((await handler(event('{nope', 'forged'))).statusCode).toBe(401);
    expect(invoke).not.toHaveBeenCalled();
  });

  it.each([
    ['bad json', '{nope'],
    ['empty message', { ...valid, message: '  ' }],
    ['long message', { ...valid, message: 'x'.repeat(4001) }],
    ['missing session', { message: 'Hi', agentId: 'assistant' }],
    ['short session', { ...valid, sessionId: 'abc' }],
    ['non-string message', { ...valid, message: 5 }],
  ])('returns 400 for %s', async (_n, body) => {
    const { handler, invoke } = setup();
    expect((await handler(event(body))).statusCode).toBe(400);
    expect(invoke).not.toHaveBeenCalled();
  });

  it('returns 404 for unknown agents, including prototype keys', async () => {
    const { handler } = setup();
    expect((await handler(event({ ...valid, agentId: 'research' }))).statusCode).toBe(404);
    expect((await handler(event({ ...valid, agentId: 'constructor' }))).statusCode).toBe(404);
  });

  it('returns 413 for oversized bodies', async () => {
    const { handler } = setup();
    expect((await handler(event('x'.repeat(20_000)))).statusCode).toBe(413);
  });

  it('returns a generic 502 without leaking internal errors', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { handler } = setup(async () => {
      throw new Error('AccessDenied: arn:aws:secret');
    });
    const res = await handler(event(valid));
    expect(res.statusCode).toBe(502);
    expect(res.body).not.toContain('AccessDenied');
  });
});

describe('helpers', () => {
  it('parses the agent map defensively', () => {
    expect(parseAgentMap('{"a":"arn1","b":3}')).toEqual({ a: 'arn1' });
    expect(parseAgentMap('nope')).toEqual({});
    expect(parseAgentMap(undefined)).toEqual({});
  });
  it('strips <thinking> blocks', () => {
    expect(stripThinking('<thinking>hmm\nmore</thinking>\n\nAnswer')).toBe('Answer');
  });
});

describe('cognito verifier wrapper', () => {
  it('rejects non-bearer headers without contacting Cognito', async () => {
    const { createCognitoVerifier } = await import('../src/auth.js');
    const v = createCognitoVerifier('us-east-2_abcdefghi', 'client');
    expect(await v(undefined)).toBeNull();
    expect(await v('Basic abc')).toBeNull();
    expect(await v('Bearer not.a.jwt')).toBeNull();
  });
});
