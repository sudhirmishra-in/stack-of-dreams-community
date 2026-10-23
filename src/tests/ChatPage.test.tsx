import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

const sendMessage = vi.fn();
vi.mock('../services/chatService', () => ({
  chatService: { isMock: true, sendMessage: (...a: unknown[]) => sendMessage(...a) },
}));

import ChatPage from '../pages/ChatPage';
import { Route, Routes } from 'react-router';

const renderChat = () =>
  render(
    <MemoryRouter initialEntries={['/chat/assistant']}>
      <Routes>
        <Route path="/chat/:agentId?" element={<ChatPage />} />
        <Route path="/agents" element={<p>agents page</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe('ChatPage', () => {
  it('submits with Enter, shows the reply with markdown, and Shift+Enter does not submit', async () => {
    sendMessage.mockImplementation(async (r) => ({
      response: '**bold reply**\n\n```ts\nconst x = 1;\n```\n\n<script>alert(1)</script>',
      sessionId: r.sessionId,
      agentId: r.agentId,
    }));
    const user = userEvent.setup();
    renderChat();
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();

    const input = screen.getByLabelText('Message');
    await user.type(input, 'line one{Shift>}{Enter}{/Shift}line two');
    expect(sendMessage).not.toHaveBeenCalled();
    await user.keyboard('{Enter}');

    expect(await screen.findByText('bold reply')).toBeInTheDocument();
    expect(sendMessage.mock.calls[0][0]).toMatchObject({
      message: 'line one\nline two',
      agentId: 'assistant',
    });
    expect(document.querySelector('script')).toBeNull();
    expect(document.querySelector('pre code')).not.toBeNull();
  });

  it('shows an error and retries on failure', async () => {
    sendMessage.mockRejectedValueOnce(new Error('Server down'));
    sendMessage.mockImplementationOnce(async (r) => ({
      response: 'back online',
      sessionId: r.sessionId,
      agentId: r.agentId,
    }));
    const user = userEvent.setup();
    renderChat();
    await user.type(screen.getByLabelText('Message'), 'hi{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('Server down');
    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('back online')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('starts a new conversation from the header button', async () => {
    sendMessage.mockImplementation(async (r) => ({
      response: 'ok',
      sessionId: r.sessionId,
      agentId: r.agentId,
    }));
    const user = userEvent.setup();
    renderChat();
    await user.click(screen.getAllByRole('button', { name: /What is agentic AI/ })[0]);
    await waitFor(() => expect(screen.getByText('ok')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'New chat' }));
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();
  });
});
