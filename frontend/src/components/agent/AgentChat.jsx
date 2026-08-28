import { useRef, useState, useEffect } from 'react';
import { Send, Bot, User, Sparkles } from 'lucide-react';
import { askAgent } from '../../api';
import { useToast } from '../../context/ToastContext';

const QUICK_QUESTIONS = [
  'Why did payments fail today?',
  'Which payment method is causing the most failures?',
  'How much revenue is at risk?',
  'What should we retry?',
  'What caused the checkout drop-off?',
];

function AgentMessage({ role, children, toolCalls }) {
  return (
    <div className={`chat-msg msg-${role}`}>
      <div className="chat-avatar">
        {role === 'user' ? <User size={13} /> : <Bot size={13} />}
      </div>
      <div className="chat-bubble">
        {typeof children === 'string' && (children.includes('\n') ? (
          children.split('\n').map((line, i) => <p key={i}>{line}</p>)
        ) : (
          <p>{children}</p>
        ))}
        {toolCalls && toolCalls.length > 0 ? (
          <div className="tool-calls">
            {toolCalls.map((tc, i) => (
              <span key={i} className="chip">
                <Sparkles size={11} /> {tc?.name || 'tool'} · {tc?.status || 'proposed'}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function AgentChat({ dateRange }) {
  const toast = useToast();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [asked, setAsked] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, thinking]);

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question) return;
    setInput('');
    setAsked(true);
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setThinking(true);
    const res = await askAgent({ question, from: dateRange.from, to: dateRange.to });
    setThinking(false);

    if (res.ok) {
      const d = res.data || {};
      const answer =
        d.answer ||
        (d.message && d.message.content) ||
        'The agent processed your question. Connect a richer LLM/tool-calling backend to /api/agent/ask for deeper answers.';
      setMessages((m) => [...m, { role: 'agent', text: answer, toolCalls: d.tool_calls || d.toolCalls }]);
      return;
    }

    if (res.status === 404) {
      setMessages((m) => [
        ...m,
        {
          role: 'agent',
          text:
            "The AI agent API isn't connected yet. Wire `POST /api/agent/ask` on the backend to your LLM/tool-calling layer and this chat will run live investigations, retrieve payment context, and recommend actions.",
        },
      ]);
      return;
    }
    toast('Agent request failed', 'error', { description: res.error });
    setMessages((m) => [
      ...m,
      { role: 'agent', text: `The agent backend could not be reached (${res.error || 'network error'}). Please start the backend and try again.` },
    ]);
  };

  return (
    <div className="panel pad agent-chat">
      <div className="panel-head">
        <div className="panel-title">
          <h2>Ask the operations agent</h2>
          <p>Natural-language commands wired to the LLM tool-calling backend via POST /api/agent/ask</p>
        </div>
      </div>

      <div className="quick-questions">
        {QUICK_QUESTIONS.map((q) => (
          <button key={q} className="chip-btn" onClick={() => send(q)} disabled={thinking}>
            {q}
          </button>
        ))}
      </div>

      <div className="chat-list" ref={listRef}>
        {!asked ? (
          <div className="chat-empty">
            <div className="chat-empty-orb">
              <Sparkles size={18} />
            </div>
            <strong>Ready to investigate</strong>
            <p>Ask about failures, revenue at risk, retries, checkout drop-off and more. The agent answers using your live payment events.</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <AgentMessage key={i} role={m.role} toolCalls={m.toolCalls}>
              {m.text}
            </AgentMessage>
          ))
        )}
        {thinking ? (
          <div className="chat-msg msg-agent">
            <div className="chat-avatar">
              <Bot size={13} />
            </div>
            <div className="chat-bubble thinking">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </div>
        ) : null}
      </div>

      <div className="chat-composer">
        <input
          placeholder="Ask the agent… e.g. Which payment method is failing most?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send();
          }}
          disabled={thinking}
        />
        <button className="btn btn-primary" onClick={() => send()} disabled={thinking || !input.trim()} aria-label="Send">
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}