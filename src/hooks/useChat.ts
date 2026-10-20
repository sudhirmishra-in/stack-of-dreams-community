import { useCallback, useEffect, useRef, useState } from 'react';
import { chatService as defaultService } from '../services/chatService';
import type { ChatService } from '../services/errors';
import type { ChatMessageModel, Conversation } from '../types/chat';
import {
  clearStoredConversation,
  createSessionId,
  loadConversation,
  newConversation,
  saveConversation,
} from '../utils/session';

const makeId = () => createSessionId();

function errorText(err: unknown): string {
  return err instanceof Error && err.message ? err.message : 'Something went wrong.';
}

/**
 * `conversationKey` separates stored history for a different backend that shares the same agent id
 * (e.g. the AI for Good assistant vs the general chat). It never changes what is sent to the service.
 */
export function useChat(
  agentId: string,
  service: ChatService = defaultService,
  conversationKey: string = agentId,
) {
  const [conversation, setConversation] = useState<Conversation>(() =>
    loadConversation(conversationKey),
  );
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [prevAgentId, setPrevAgentId] = useState(conversationKey);

  // Switching agents loads that agent's own conversation (adjust state during render).
  if (prevAgentId !== conversationKey) {
    setPrevAgentId(conversationKey);
    setConversation(loadConversation(conversationKey));
    setIsLoading(false);
  }

  useEffect(() => {
    saveConversation(conversation);
  }, [conversation]);

  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => {
    abortRef.current?.abort();
  }, [conversationKey]);

  const request = useCallback(
    async (sessionId: string, message: string, prior: ChatMessageModel[]) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setIsLoading(true);

      const append = (msg: ChatMessageModel) =>
        setConversation((c) =>
          c.sessionId === sessionId ? { ...c, messages: [...c.messages, msg] } : c,
        );

      try {
        const history = service.supportsHistory
          ? prior
              .filter((m) => m.status === 'sent' && m.content)
              .slice(-4)
              .map((m) => ({ role: m.role, content: m.content }))
          : undefined;
        const res = await service.sendMessage(
          { message, sessionId, agentId, ...(history ? { history } : {}) },
          controller.signal,
        );
        append({
          id: makeId(),
          role: 'assistant',
          content: res.response,
          createdAt: Date.now(),
          status: 'sent',
          mock: service.isMock,
          ...(res.citations ? { citations: res.citations } : {}),
          ...(res.uncertainty ? { uncertainty: res.uncertainty } : {}),
        });
      } catch (err) {
        if (controller.signal.aborted) return;
        append({
          id: makeId(),
          role: 'assistant',
          content: '',
          createdAt: Date.now(),
          status: 'error',
          error: errorText(err),
        });
      } finally {
        if (abortRef.current === controller) setIsLoading(false);
      }
    },
    [agentId, service],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || isLoading) return;
      const userMsg: ChatMessageModel = {
        id: makeId(),
        role: 'user',
        content: message,
        createdAt: Date.now(),
        status: 'sent',
      };
      setConversation((c) => ({ ...c, messages: [...c.messages, userMsg] }));
      await request(conversation.sessionId, message, conversation.messages);
    },
    [conversation.sessionId, conversation.messages, isLoading, request],
  );

  /** Removes the trailing error message and re-sends the last user message. */
  const retry = useCallback(async () => {
    if (isLoading) return;
    const msgs = conversation.messages;
    const last = msgs[msgs.length - 1];
    if (last?.status !== 'error') return;
    const lastUser = [...msgs].reverse().find((m) => m.role === 'user');
    if (!lastUser) return;
    setConversation((c) => ({ ...c, messages: c.messages.slice(0, -1) }));
    // Context for a retry is everything before the failed attempt (its user message and the error).
    await request(conversation.sessionId, lastUser.content, msgs.slice(0, -2));
  }, [conversation, isLoading, request]);

  /** Starts a fresh conversation with a new session ID. */
  const startNewConversation = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    setConversation(newConversation(conversationKey));
  }, [conversationKey]);

  /** Same as a new conversation, but also wipes the stored history from this browser. */
  const clearConversation = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    clearStoredConversation(conversationKey);
    setConversation(newConversation(conversationKey));
  }, [conversationKey]);

  return {
    messages: conversation.messages,
    sessionId: conversation.sessionId,
    isLoading,
    isMock: service.isMock,
    sendMessage,
    retry,
    startNewConversation,
    clearConversation,
  };
}
