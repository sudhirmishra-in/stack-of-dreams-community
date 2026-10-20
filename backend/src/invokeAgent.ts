import { BedrockAgentCoreClient, InvokeHarnessCommand } from '@aws-sdk/client-bedrock-agentcore';

export interface AgentInvoker {
  invoke(args: {
    harnessArn: string;
    runtimeSessionId: string;
    runtimeUserId: string;
    message: string;
  }): Promise<string>;
}

/** Removes model "<thinking>" scratch text that some models emit inline. */
export function stripThinking(text: string): string {
  return text.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
}

export function createHarnessInvoker(region: string): AgentInvoker {
  const client = new BedrockAgentCoreClient({ region });
  return {
    async invoke({ harnessArn, runtimeSessionId, runtimeUserId, message }) {
      const res = await client.send(
        new InvokeHarnessCommand({
          harnessArn,
          runtimeSessionId,
          runtimeUserId,
          messages: [{ role: 'user', content: [{ text: message }] }],
        }),
      );
      let text = '';
      for await (const event of res.stream ?? []) {
        if (event.contentBlockDelta?.delta && 'text' in event.contentBlockDelta.delta) {
          text += event.contentBlockDelta.delta.text ?? '';
        } else if (event.runtimeClientError || event.internalServerException) {
          throw new Error('The agent runtime reported an error.');
        } else if (event.validationException) {
          throw new Error('The agent rejected the request.');
        }
      }
      return stripThinking(text);
    },
  };
}
