"use client";

import { memo, useEffect, useRef, useState } from "react";
import { downloadIcs } from "./lib/ics";
import { SSEDecoder, type SSEEvent } from "./lib/sse";

type Source = {
  law_name: string;
  article_no: string;
  article_title?: string;
  text: string;
  source_url?: string;
};

type Message =
  | { role: "user"; text: string }
  | {
      role: "bot";
      text: string;
      sources: Source[];
      verified?: { ok: boolean; unknown: string[] };
      clarify?: string[];
      question?: string;
      rated?: boolean;
    };

type Program = { id: string; title: string; who: string; what: string; how: string; contact: string };
type Hotline = { name: string; phone: string; hours: string; for: string };
type RegionRow = { region: string; klac: string; victim_center: string; sunflower: string };

type ChecklistItem = { item: string; why?: string; deadline?: string };
type Checklist = { label: string; urgent: ChecklistItem[]; items: ChecklistItem[] };
type Stage = { id: string; title: string; desc: string; rights: string[]; tips: string };
type DeadlineRule = {
  id: string; label: string; from: string; hours?: number; days?: number;
  months?: number; years?: number; urgency: string; desc: string;
};

const EXAMPLES = [
  "폭행을 당했는데 증거를 어떻게 모아야 하나요?",
  "전세 보증금을 못 돌려받고 있어요",
  "가해자와 통화한 내용을 녹음해도 되나요?",
];

const LANGS = [
  ["ko", "한국어"], ["en", "English"], ["vi", "Tiếng Việt"], ["zh", "中文"],
] as const;

function quickExit() {
  window.location.replace("https://weather.naver.com");
}

/** Memoized so streaming updates to the last message don't re-render history. */
const MessageView = memo(function MessageView({
  m,
  onRate,
}: {
  m: Message;
  onRate?: (helpful: boolean) => void;
}) {
  if (m.role === "user") return <div className="msg user">{m.text}</div>;
  return (
    <div style={{ display: "contents" }}>
      {m.clarify && m.clarify.length > 0 && (
        <div className="clarify">
          더 정확히 안내드리기 위해, 아래 내용을 알려주시면 도움이 됩니다:
          <ul>{m.clarify.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </div>
      )}
      <div className="msg bot">
        {m.text || "…"}
        {m.verified && (
          <div className={m.verified.ok ? "verify ok" : "verify warn"}>
            {m.verified.ok
              ? "✓ 인용 검증됨 — 모든 인용이 검색된 근거와 일치합니다"
              : "⚠️ 일부 인용을 근거에서 확인하지 못했습니다"}
          </div>
        )}
        {onRate && m.text && (
          <div className="rate">
            {m.rated ? (
              <span className="thanks">의견 감사합니다. 서비스 개선에 활용하겠습니다.</span>
            ) : (
              <>
                이 답변이 도움이 되었나요?
                <button onClick={() => onRate(true)} aria-label="도움이 되었습니다">👍</button>
                <button onClick={() => onRate(false)} aria-label="도움이 되지 않았습니다">👎</button>
              </>
            )}
          </div>
        )}
      </div>
      {m.sources.length > 0 && (
        <details className="sources">
          <summary>근거 조문 {m.sources.length}건 보기</summary>
          {m.sources.map((s, j) => (
            <div key={j} className="source-item">
              <div className="name">
                {s.law_name} {s.article_no}{s.article_title ? ` (${s.article_title})` : ""}
              </div>
              <div className="text">{s.text}</div>
              {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer">법령 원문 보기 →</a>}
            </div>
          ))}
        </details>
      )}
    </div>
  );
});

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("ko");
  const [simple, setSimple] = useState(false);
  const [apiKey, setApiKey] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("legal_ai_api_key") ?? "" : ""
  );
  const [panel, setPanel] = useState<
    "" | "settings" | "check" | "procedure" | "deadline" | "support" | "centers"
  >("");
  const [offline, setOffline] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  function saveApiKey(value: string) {
    setApiKey(value);
    if (value.trim()) localStorage.setItem("legal_ai_api_key", value.trim());
    else localStorage.removeItem("legal_ai_api_key");
  }

  // ---- checklists ----
  const [checkTypes, setCheckTypes] = useState<Record<string, string>>({});
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  async function openChecklists() {
    if (panel === "check") { setPanel(""); return; }
    const r = await fetch("/api/checklists");
    setCheckTypes(await r.json());
    setPanel("check");
  }

  async function loadChecklist(type: string) {
    const r = await fetch(`/api/checklists/${type}`);
    setChecklist(await r.json());
    setChecked({});
  }

  // ---- procedure navigator ----
  const [stages, setStages] = useState<Stage[]>([]);
  const [openStage, setOpenStage] = useState("");

  async function openProcedure() {
    if (panel === "procedure") { setPanel(""); return; }
    const r = await fetch("/api/procedure");
    const data = await r.json();
    setStages(data.stages);
    setPanel("procedure");
  }

  // ---- deadline engine ----
  const [rules, setRules] = useState<DeadlineRule[]>([]);
  const [incidentDate, setIncidentDate] = useState("");

  async function openDeadlines() {
    if (panel === "deadline") { setPanel(""); return; }
    const r = await fetch("/api/deadlines");
    const data = await r.json();
    setRules(data.rules);
    setPanel("deadline");
  }

  function deadlineFor(rule: DeadlineRule): { text: string; passed: boolean } | null {
    if (!incidentDate) return null;
    const base = new Date(incidentDate + "T00:00:00");
    const d = new Date(base);
    if (rule.hours) d.setHours(d.getHours() + rule.hours);
    else if (rule.days) d.setDate(d.getDate() + rule.days);
    else if (rule.months) d.setMonth(d.getMonth() + rule.months);
    else if (rule.years) d.setFullYear(d.getFullYear() + rule.years);
    else return { text: "죄명에 따라 상이", passed: false };
    const passed = d.getTime() < Date.now();
    return { text: d.toLocaleDateString("ko-KR"), passed };
  }

  // ---- support / eligibility ----
  const [supportQs, setSupportQs] = useState<
    { id: string; label: string; options: { value: string; label: string }[] }[]
  >([]);
  const [supportAnswers, setSupportAnswers] = useState<Record<string, string>>({});
  const [supportResult, setSupportResult] = useState<
    { matched: Program[]; others: Program[]; notes: string[]; disclaimer: string } | null
  >(null);

  async function openSupport() {
    if (panel === "support") { setPanel(""); return; }
    const r = await fetch("/api/support/questions");
    setSupportQs((await r.json()).questions);
    setPanel("support");
  }

  async function matchSupport(next: Record<string, string>) {
    setSupportAnswers(next);
    const r = await fetch("/api/support/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: next }),
    });
    setSupportResult(await r.json());
  }

  // ---- centers ----
  const [hotlines, setHotlines] = useState<Hotline[]>([]);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [region, setRegion] = useState("");

  async function openCenters() {
    if (panel === "centers") { setPanel(""); return; }
    const data = await (await fetch("/api/centers")).json();
    setHotlines(data.hotlines);
    setRegions(data.regions);
    setPanel("centers");
  }

  // ---- feedback ----
  async function rate(index: number, helpful: boolean) {
    const m = messages[index];
    if (m.role !== "bot") return;
    setMessages((prev) => prev.map((x, i) => (i === index && x.role === "bot" ? { ...x, rated: true } : x)));
    let reason = "";
    if (!helpful) reason = prompt("어떤 점이 아쉬웠는지 알려주시면 개선에 큰 도움이 됩니다 (선택)") ?? "";
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ helpful, question: m.question ?? "", reason }),
    }).catch(() => {});
  }

  // ---- summary ----
  async function downloadSummary() {
    if (!messages.length || busy) return;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey.trim()) headers["X-Anthropic-Key"] = apiKey.trim();
    const r = await fetch("/api/summary", {
      method: "POST",
      headers,
      body: JSON.stringify({ messages: messages.map((m) => ({ role: m.role, text: m.text })) }),
    });
    const data = await r.json();
    const blob = new Blob([data.content], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "상담준비요약서.md";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ---- chat ----
  const abortRef = useRef<AbortController | null>(null);
  const pendingRef = useRef("");
  const rafRef = useRef(0);

  /** Flush buffered delta text at most once per animation frame (perf: avoids
   *  one React re-render per SSE chunk). */
  function scheduleFlush() {
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      flushPending();
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  }

  function flushPending() {
    const text = pendingRef.current;
    if (!text) return;
    pendingRef.current = "";
    setMessages((m) => {
      const last = m[m.length - 1];
      if (last?.role !== "bot") return m;
      return [...m.slice(0, -1), { ...last, text: last.text + text }];
    });
  }

  function applyEvent(ev: SSEEvent) {
    if (ev.event === "delta") {
      pendingRef.current += JSON.parse(ev.data).text;
      scheduleFlush();
      return;
    }
    flushPending(); // keep ordering for non-delta events
    setMessages((m) => {
      const last = m[m.length - 1];
      if (last?.role !== "bot") return m;
      if (ev.event === "sources") return [...m.slice(0, -1), { ...last, sources: JSON.parse(ev.data) }];
      if (ev.event === "verified") return [...m.slice(0, -1), { ...last, verified: JSON.parse(ev.data) }];
      if (ev.event === "clarify") return [...m.slice(0, -1), { ...last, clarify: JSON.parse(ev.data) }];
      return m;
    });
  }

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    abortRef.current?.abort(); // a new question cancels any running stream
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setInput("");
    setMessages((m) => [
      ...m,
      { role: "user", text: question },
      { role: "bot", text: "", sources: [], question },
    ]);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey.trim()) headers["X-Anthropic-Key"] = apiKey.trim();
      const res = await fetch("/api/chat", {
        method: "POST",
        headers,
        body: JSON.stringify({ question, lang, simple }),
        signal: controller.signal,
      });
      const reader = res.body!.getReader();
      const decoder = new SSEDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const ev of decoder.feed(value)) applyEvent(ev);
      }
      for (const ev of decoder.end()) applyEvent(ev);
      flushPending();
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setMessages((m) => {
        const last = m[m.length - 1];
        if (last?.role === "bot" && !last.text)
          return [...m.slice(0, -1), { ...last, text: "서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요." }];
        return m;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <button className="quick-exit" onClick={quickExit} title="이 페이지를 즉시 벗어납니다">
        ✕ 빠른 나가기
      </button>

      <div className="header">
        <div className="header-row">
          <h1>⚖️ Legal-AI — 생활법령 AI 도우미</h1>
        </div>
        <div className="toolbar">
          <button className="settings-btn" onClick={openChecklists}>📋 증거 체크리스트</button>
          <button className="settings-btn highlight" onClick={openSupport}>🤝 무료 지원 확인</button>
          <button className="settings-btn" onClick={openCenters}>📞 지원기관 찾기</button>
          <button className="settings-btn" onClick={openProcedure}>🧭 절차 안내</button>
          <button className="settings-btn" onClick={openDeadlines}>⏰ 기한 계산</button>
          <a className="settings-btn" href="/glossary">📖 용어 사전</a>
          <a className="settings-btn" href="/journal">📔 증거 일지</a>
          {messages.length > 0 && (
            <button className="settings-btn" onClick={downloadSummary}>📄 상담 준비 요약서</button>
          )}
          <select className="settings-btn" value={lang} onChange={(e) => setLang(e.target.value)}>
            {LANGS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
          <button className={`settings-btn ${simple ? "on" : ""}`} onClick={() => setSimple(!simple)}>
            {simple ? "✓ 쉬운 말" : "쉬운 말"}
          </button>
          <button className="settings-btn" onClick={() => setPanel(panel === "settings" ? "" : "settings")}>
            {apiKey ? "🔑 키 설정됨" : "⚙️ API 키"}
          </button>
        </div>

        {panel === "settings" && (
          <div className="settings">
            <label>Anthropic API 키 (브라우저에만 저장되며 답변 생성에만 사용됩니다)</label>
            <input type="password" value={apiKey} onChange={(e) => saveApiKey(e.target.value)} placeholder="sk-ant-..." />
            <p>
              키가 없으면 관련 조문 원문만 표시됩니다. 키는{" "}
              <a href="https://console.anthropic.com" target="_blank" rel="noreferrer">console.anthropic.com</a>
              에서 발급받을 수 있습니다.
            </p>
          </div>
        )}

        {panel === "check" && (
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
                    <span><b>🚨 {it.item}</b> — {it.deadline}{it.why && <em>{it.why}</em>}</span>
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

        {panel === "support" && (
          <div className="checklist-panel">
            <p className="panel-note">
              무료 변호사 지원이나 국가 지원금을 받을 수 있는지 확인해 보세요. 많은 분들이 자격이
              있는데도 모르고 계십니다. 몇 가지만 선택하시면 됩니다.
            </p>
            {supportQs.map((q) => (
              <div key={q.id} className="support-q">
                <div className="support-label">{q.label}</div>
                <div className="check-tabs">
                  {q.options.map((o) => (
                    <button
                      key={o.value}
                      className={supportAnswers[q.id] === o.value ? "active" : ""}
                      onClick={() => matchSupport({ ...supportAnswers, [q.id]: o.value })}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {supportResult && (
              <div className="check-body">
                <div className="support-head">받으실 수 있는 지원 {supportResult.matched.length}건</div>
                {supportResult.matched.map((p) => (
                  <div key={p.id} className="program matched">
                    <b>✅ {p.title}</b>
                    <p>{p.what}</p>
                    <p><b>신청 방법:</b> {p.how}</p>
                    <p className="contact">📞 {p.contact}</p>
                  </div>
                ))}
                {supportResult.notes.map((n, i) => (
                  <p key={i} className="panel-note">⚠️ {n}</p>
                ))}
                <details>
                  <summary>조건에 따라 해당될 수 있는 그 밖의 제도 {supportResult.others.length}건</summary>
                  {supportResult.others.map((p) => (
                    <div key={p.id} className="program">
                      <b>{p.title}</b>
                      <p>{p.who}</p>
                      <p className="contact">📞 {p.contact}</p>
                    </div>
                  ))}
                </details>
                <p className="panel-note">{supportResult.disclaimer}</p>
              </div>
            )}
          </div>
        )}

        {panel === "centers" && (
          <div className="checklist-panel">
            <p className="panel-note">전화 한 통이면 전문가 상담으로 연결됩니다. 오프라인에서도 확인하실 수 있습니다.</p>
            <div className="check-body">
              {hotlines.map((h) => (
                <a key={h.phone + h.name} className="hotline" href={`tel:${h.phone}`}>
                  <b>{h.name}</b>
                  <span className="phone">{h.phone}</span>
                  <em>{h.for} · {h.hours}</em>
                </a>
              ))}
            </div>
            <div className="support-label" style={{ marginTop: 12 }}>지역별 기관</div>
            <select className="date-input" value={region} onChange={(e) => setRegion(e.target.value)}>
              <option value="">지역을 선택하세요</option>
              {regions.map((r) => <option key={r.region} value={r.region}>{r.region}</option>)}
            </select>
            {region && (() => {
              const r = regions.find((x) => x.region === region)!;
              return (
                <div className="check-body">
                  <div className="program"><b>법률구조공단</b><p>{r.klac}</p></div>
                  <div className="program"><b>범죄피해자지원센터</b><p>{r.victim_center}</p></div>
                  <div className="program"><b>해바라기센터</b><p>{r.sunflower}</p></div>
                </div>
              );
            })()}
          </div>
        )}

        {panel === "procedure" && (
          <div className="checklist-panel">
            <p className="panel-note">2026. 10. 2. 시행 개정 형사소송법 기준 · 단계를 눌러 자세히 보세요</p>
            {stages.map((s) => (
              <div key={s.id} className="stage">
                <button className="stage-title" onClick={() => setOpenStage(openStage === s.id ? "" : s.id)}>
                  {s.title} {openStage === s.id ? "▾" : "▸"}
                </button>
                {openStage === s.id && (
                  <div className="stage-body">
                    <p>{s.desc}</p>
                    <p><b>이 단계에서의 권리:</b> {s.rights.join(" · ")}</p>
                    <p className="tip">💡 {s.tips}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {panel === "deadline" && (
          <div className="checklist-panel">
            <p className="panel-note">
              사건 발생일(또는 알게 된 날)을 선택하면 주요 기한을 계산해 드립니다. 죄명·사안에 따라 다를 수
              있으니 반드시 전문가와 확인하세요.
            </p>
            <input type="date" className="date-input" value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
            {incidentDate && (
              <div className="check-body">
                <button
                  className="settings-btn"
                  style={{ alignSelf: "flex-start" }}
                  onClick={() =>
                    downloadIcs(
                      rules
                        .map((r) => {
                          const d = deadlineFor(r);
                          if (!d || d.passed || d.text === "죄명에 따라 상이") return null;
                          const base = new Date(incidentDate + "T00:00:00");
                          if (r.hours) base.setHours(base.getHours() + r.hours);
                          else if (r.days) base.setDate(base.getDate() + r.days);
                          else if (r.months) base.setMonth(base.getMonth() + r.months);
                          else if (r.years) base.setFullYear(base.getFullYear() + r.years);
                          return { title: `[법률 기한] ${r.label}`, date: base, description: r.desc };
                        })
                        .filter(Boolean) as { title: string; date: Date; description: string }[]
                    )
                  }
                >
                  📅 달력에 기한 저장 (.ics)
                </button>
                {rules.map((r) => {
                  const d = deadlineFor(r);
                  return (
                    <div key={r.id} className={`deadline-item ${r.urgency} ${d?.passed ? "passed" : ""}`}>
                      <b>{r.label}</b>
                      <span className="deadline-date">
                        {d?.text}{d?.passed && " — 기한 경과 가능성"}
                      </span>
                      <em>{r.desc}</em>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div className="notice">
          AI가 생성하는 <b>일반 법령 정보</b>입니다. 법률 자문이 아니며, 구체적인 사안은 변호사 또는
          대한법률구조공단(국번없이 132) 상담을 이용하세요. 대화 내용은 서버에 저장되지 않으며, 우측 상단
          '빠른 나가기'로 언제든 즉시 화면을 벗어날 수 있습니다.
        </div>
      </div>

      {messages.length === 0 && (
        <div className="examples">
          {EXAMPLES.map((q) => <button key={q} onClick={() => ask(q)}>{q}</button>)}
        </div>
      )}

      <div className="messages">
        {messages.map((m, i) => (
          <MessageView
            key={i}
            m={m}
            onRate={m.role === "bot" ? (helpful) => rate(i, helpful) : undefined}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {offline && (
        <div className="offline-banner">
          오프라인 상태입니다 · 체크리스트·절차 안내·서식·증거 일지는 계속 사용하실 수 있습니다
        </div>
      )}

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
