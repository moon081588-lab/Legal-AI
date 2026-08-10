"use client";

import { useRef, useState } from "react";

type Source = {
  law_name: string;
  article_no: string;
  article_title?: string;
  text: string;
  source_url?: string;
};

type Message =
  | { role: "user"; text: string }
  | { role: "bot"; text: string; sources: Source[] };

const EXAMPLES = [
  "전세 보증금을 못 돌려받고 있어요",
  "갑자기 해고 통보를 받았어요",
  "연차휴가는 며칠까지 받을 수 있나요?",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [apiKey, setApiKey] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("legal_ai_api_key") ?? "" : ""
  );
  const [showSettings, setShowSettings] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  function saveApiKey(value: string) {
    setApiKey(value);
    if (value.trim()) localStorage.setItem("legal_ai_api_key", value.trim());
    else localStorage.removeItem("legal_ai_api_key");
  }

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setBusy(true);
    setInput("");
    setMessages((m) => [...m, { role: "user", text: question }, { role: "bot", text: "", sources: [] }]);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey.trim()) headers["X-Anthropic-Key"] = apiKey.trim();
      const res = await fetch("/api/chat", {
        method: "POST",
        headers,
        body: JSON.stringify({ question }),
      });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          let event = "", data = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("event: ")) event = line.slice(7);
            if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (!event) continue;
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (last.role !== "bot") return m;
            if (event === "sources") copy[copy.length - 1] = { ...last, sources: JSON.parse(data) };
            if (event === "delta") copy[copy.length - 1] = { ...last, text: last.text + JSON.parse(data).text };
            return copy;
          });
        }
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } catch {
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last.role === "bot" && !last.text)
          copy[copy.length - 1] = { ...last, text: "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요." };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div className="header-row">
          <h1>⚖️ Legal-AI — 생활법령 AI 도우미</h1>
          <button className="settings-btn" onClick={() => setShowSettings(!showSettings)}>
            {apiKey ? "🔑 키 설정됨" : "⚙️ API 키 설정"}
          </button>
        </div>
        {showSettings && (
          <div className="settings">
            <label>Anthropic API 키 (브라우저에만 저장되며 답변 생성에만 사용됩니다)</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => saveApiKey(e.target.value)}
              placeholder="sk-ant-..."
            />
            <p>
              키가 없으면 관련 조문 원문만 표시됩니다. 키는{" "}
              <a href="https://console.anthropic.com" target="_blank" rel="noreferrer">
                console.anthropic.com
              </a>
              에서 발급받을 수 있습니다.
            </p>
          </div>
        )}
        <div className="notice">
          AI가 생성하는 <b>일반 법령 정보</b>입니다. 법률 자문이 아니며, 구체적인 사안은 변호사 또는
          대한법률구조공단(국번없이 132) 상담을 이용하세요.
        </div>
      </div>

      {messages.length === 0 && (
        <div className="examples">
          {EXAMPLES.map((q) => (
            <button key={q} onClick={() => ask(q)}>{q}</button>
          ))}
        </div>
      )}

      <div className="messages">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="msg user">{m.text}</div>
          ) : (
            <div key={i} style={{ display: "contents" }}>
              <div className="msg bot">{m.text || "…"}</div>
              {m.sources.length > 0 && (
                <details className="sources">
                  <summary>근거 조문 {m.sources.length}건 보기</summary>
                  {m.sources.map((s, j) => (
                    <div key={j} className="source-item">
                      <div className="name">
                        {s.law_name} {s.article_no}
                        {s.article_title ? ` (${s.article_title})` : ""}
                      </div>
                      <div className="text">{s.text}</div>
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noreferrer">법령 원문 보기 →</a>
                      )}
                    </div>
                  ))}
                </details>
              )}
            </div>
          )
        )}
        <div ref={bottomRef} />
      </div>

      <div className="inputbar">
        <div className="inner">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(input)}
            placeholder="법률 관련 궁금한 점을 물어보세요"
            disabled={busy}
          />
          <button onClick={() => ask(input)} disabled={busy || !input.trim()}>
            {busy ? "…" : "질문"}
          </button>
        </div>
      </div>
    </div>
  );
}
