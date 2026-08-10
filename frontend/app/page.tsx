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
  | { role: "bot"; text: string; sources: Source[]; verified?: { ok: boolean; unknown: string[] } };

const EXAMPLES = [
  "폭행을 당했는데 증거를 어떻게 모아야 하나요?",
  "전세 보증금을 못 돌려받고 있어요",
  "가해자와 통화한 내용을 녹음해도 되나요?",
];

type ChecklistItem = { item: string; why?: string; deadline?: string };
type Checklist = { label: string; urgent: ChecklistItem[]; items: ChecklistItem[] };

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

  const [checkTypes, setCheckTypes] = useState<Record<string, string>>({});
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  async function loadCheckTypes() {
    if (Object.keys(checkTypes).length) { setCheckTypes({}); setChecklist(null); return; }
    const r = await fetch("/api/checklists");
    setCheckTypes(await r.json());
  }

  async function loadChecklist(type: string) {
    const r = await fetch(`/api/checklists/${type}`);
    setChecklist(await r.json());
    setChecked({});
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
            if (event === "verified") copy[copy.length - 1] = { ...last, verified: JSON.parse(data) };
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
          <div style={{ display: "flex", gap: 8 }}>
            <button className="settings-btn" onClick={loadCheckTypes}>📋 증거 체크리스트</button>
            <button className="settings-btn" onClick={() => setShowSettings(!showSettings)}>
              {apiKey ? "🔑 키 설정됨" : "⚙️ API 키 설정"}
            </button>
          </div>
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
        {Object.keys(checkTypes).length > 0 && (
          <div className="checklist-panel">
            <div className="check-tabs">
              {Object.entries(checkTypes).map(([k, label]) => (
                <button key={k} className={checklist?.label === label ? "active" : ""} onClick={() => loadChecklist(k)}>
                  {label}
                </button>
              ))}
            </div>
            {checklist && (
              <div className="check-body">
                {checklist.urgent.map((it, i) => (
                  <label key={`u${i}`} className="check-item urgent">
                    <input type="checkbox" checked={!!checked[`u${i}`]}
                      onChange={() => setChecked({ ...checked, [`u${i}`]: !checked[`u${i}`] })} />
                    <span>
                      <b>🚨 {it.item}</b> — {it.deadline}
                      {it.why && <em>{it.why}</em>}
                    </span>
                  </label>
                ))}
                {checklist.items.map((it, i) => (
                  <label key={i} className="check-item">
                    <input type="checkbox" checked={!!checked[`i${i}`]}
                      onChange={() => setChecked({ ...checked, [`i${i}`]: !checked[`i${i}`] })} />
                    <span>{it.item}</span>
                  </label>
                ))}
                <div className="template-links">
                  서식 내려받기:{" "}
                  <a href="/api/templates/cctv" target="_blank" rel="noreferrer">CCTV 보존요청서</a> ·{" "}
                  <a href="/api/templates/complaint" target="_blank" rel="noreferrer">고소장</a>
                </div>
              </div>
            )}
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
              <div className="msg bot">
                {m.text || "…"}
                {m.verified && (
                  <div className={m.verified.ok ? "verify ok" : "verify warn"}>
                    {m.verified.ok ? "✓ 인용 검증됨 — 모든 인용이 검색된 근거와 일치합니다" : "⚠️ 일부 인용을 근거에서 확인하지 못했습니다"}
                  </div>
                )}
              </div>
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
