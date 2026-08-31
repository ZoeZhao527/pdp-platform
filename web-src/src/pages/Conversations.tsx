import { Send, UserRound, Bot } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import type { Conversation, Message } from "../types";

export default function Conversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [simulate, setSimulate] = useState("");
  const [error, setError] = useState("");

  const loadConversations = useCallback(() => {
    api
      .conversations()
      .then((rows) => {
        setConversations(rows);
        if (!selectedId && rows.length > 0) {
          setSelectedId(rows[0].id);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedId]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedId) return;
    api
      .messages(selectedId)
      .then(setMessages)
      .catch((err: Error) => setError(err.message));
  }, [selectedId]);

  const send = async () => {
    if (!selectedId || !draft.trim()) return;
    await api.sendMessage(selectedId, draft.trim());
    setDraft("");
    const rows = await api.messages(selectedId);
    setMessages(rows);
  };

  const simulateMessage = async () => {
    if (!simulate.trim()) return;
    const result = await api.webhook(simulate.trim());
    setSimulate("");
    setSelectedId(result.conversation_id);
    loadConversations();
    const rows = await api.messages(result.conversation_id);
    setMessages(rows);
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>会话工作台</h1>
          <p>查看消息流转，并通过 Mock 渠道模拟客户消息</p>
        </div>
      </header>

      <div className="simulate-bar">
        <input
          value={simulate}
          onChange={(event) => setSimulate(event.target.value)}
          placeholder="输入模拟客户消息，例如：我想了解敏感肌护理方案"
        />
        <button type="button" className="btn primary" onClick={simulateMessage}>
          发送
        </button>
      </div>
      {error && <span className="error-text">{error}</span>}

      <div className="workspace">
        <aside className="conversation-list">
          {conversations.map((item) => (
            <button
              type="button"
              key={item.id}
              className={`conversation-item ${selectedId === item.id ? "active" : ""}`}
              onClick={() => setSelectedId(item.id)}
            >
              <div className="conversation-title">{item.title || item.external_id}</div>
              <div className="conversation-meta">
                <span className={`pill ${item.conversation_type}`}>
                  {item.conversation_type === "cs" ? "外部客服" : "运营 Agent"}
                </span>
                <span>{item.status}</span>
              </div>
            </button>
          ))}
          {conversations.length === 0 && <div className="empty">暂无会话</div>}
        </aside>

        <section className="thread">
          <div className="thread-body">
            {messages.map((item) => (
              <div key={item.id} className={`bubble ${item.direction === "in" ? "in" : "out"}`}>
                <div className="bubble-icon">
                  {item.direction === "in" ? <UserRound size={15} /> : <Bot size={15} />}
                </div>
                <div className="bubble-content">
                  <div className="bubble-meta">
                    {item.direction === "in" ? "客户" : "Agent"} · {item.source}
                  </div>
                  <div className="bubble-text">{item.content}</div>
                </div>
              </div>
            ))}
            {messages.length === 0 && <div className="empty">选择左侧会话查看消息</div>}
          </div>
          <div className="thread-input">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && send()}
              placeholder="以 Agent 身份回复客户"
            />
            <button type="button" className="btn primary icon-btn" onClick={send} aria-label="发送">
              <Send size={16} />
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

