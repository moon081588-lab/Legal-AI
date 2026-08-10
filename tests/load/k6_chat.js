// k6 load test: 50 concurrent users streaming chat answers.
// Run: k6 run tests/load/k6_chat.js  (against a running backend on :8000)
// Pass criteria are encoded as thresholds — k6 exits non-zero if violated.

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "1m", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],      // <1% errors
    http_req_duration: ["p(95)<3000"],   // p95 under 3s (fallback mode)
  },
};

const QUESTIONS = [
  "전세 보증금을 못 돌려받고 있어요",
  "폭행을 당했는데 증거를 어떻게 모아야 하나요?",
  "가해자와 통화한 내용을 녹음해도 되나요?",
  "연차휴가는 며칠까지 받을 수 있나요?",
];

export default function () {
  const question = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(
    "http://localhost:8000/api/chat",
    JSON.stringify({ question }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(res, {
    "status 200": (r) => r.status === 200,
    "has sources event": (r) => String(r.body).includes("event: sources"),
    "has done event": (r) => String(r.body).includes("event: done"),
  });
  sleep(1);
}
