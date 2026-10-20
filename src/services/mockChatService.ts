import type { ChatRequest, ChatResponse } from '../types/chat';
import type { ChatService } from './errors';

export const MOCK_BANNER =
  '> **Mock response** — generated locally in your browser. No AWS agent was invoked.';

const DELAY_MS = 900;

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

/** Messages containing this token make the mock fail, so error handling can be demoed/tested. */
export const MOCK_ERROR_TRIGGER = '/fail';

export function buildMockReply(message: string): string {
  const m = message.toLowerCase();
  let body: string;

  if (/\b(hi|hello|hey)\b/.test(m)) {
    body = `Hello! I'm the demo **AI Assistant** for Stack of Dreams Labs. Try asking about agentic AI, the target architecture, or for a code example.`;
  } else if (/agentcore|bedrock/.test(m)) {
    body = `**Amazon Bedrock AgentCore** provides managed infrastructure for running agents securely at scale.

In the target architecture:

- The agent code runs in **AgentCore Runtime**
- The agent calls a foundation model through **Amazon Bedrock**
- A thin API layer sits between the browser and the runtime

This page currently uses a mock service, so none of that is running yet.`;
  } else if (/strands/.test(m)) {
    body = `**Strands Agents** is an open-source SDK for building agents with a model-driven loop and tools. A minimal agent looks like this:

\`\`\`python
from strands import Agent

agent = Agent(system_prompt="You are a concise technical assistant.")
result = agent("Explain agentic AI in two sentences.")
print(result)
\`\`\`

_Illustrative snippet only — it is not executed by this demo._`;
  } else if (/code|example|snippet|typescript|python|function/.test(m)) {
    body = `Here's an example of the provisional chat request this UI would send:

\`\`\`typescript
const res = await fetch(\`\${API_BASE_URL}/chat\`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, sessionId, agentId: 'assistant' }),
});
const { response } = await res.json();
\`\`\``;
  } else if (/agentic|agent\b|agents\b/.test(m)) {
    body = `**Agentic AI** describes systems where a model doesn't just answer — it plans, calls tools, observes results, and iterates toward a goal.

| Aspect | Chatbot | Agent |
| --- | --- | --- |
| Interaction | Single reply | Multi-step loop |
| Tools | None | APIs, search, code |
| Memory | Prompt only | Session + long-term |`;
  } else if (/architecture|diagram|flow/.test(m)) {
    body = `The **target architecture** is: React frontend → API Gateway → Lambda → AgentCore Runtime → Strands agent → Bedrock foundation model.

See the *Architecture* page for each component's responsibility. It is a target design and is not deployed yet.`;
  } else {
    body = `You asked: _"${message.slice(0, 160)}"_

This is a simulated answer. When the backend is connected, the request will go to a Strands agent running on Amazon Bedrock AgentCore Runtime, and the reply will come from a foundation model.`;
  }

  return `${MOCK_BANNER}\n\n${body}`;
}

export const mockChatService: ChatService = {
  isMock: true,

  async sendMessage(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    await wait(DELAY_MS, signal);
    if (request.message.includes(MOCK_ERROR_TRIGGER)) {
      throw new Error('Simulated mock failure (triggered by "/fail").');
    }
    return {
      response: buildMockReply(request.message),
      sessionId: request.sessionId,
      agentId: request.agentId,
    };
  },
};
