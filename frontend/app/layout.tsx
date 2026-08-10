import "./globals.css";

export const metadata = {
  title: "Legal-AI — 생활법령 AI 도우미",
  description: "대한민국 법령 정보를 쉽게 안내하는 AI 서비스 (법률 자문 아님)",
  manifest: "/manifest.webmanifest",
};

export const viewport = {
  themeColor: "#2f6fed",
  width: "device-width",
  initialScale: 1,
};

// Offline support: checklists, procedure guide, deadlines and templates stay
// available with no network.
const swRegister = `
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  });
}
`;

// Report uncaught frontend errors to the backend (message/stack only, never user input).
const errorReporter = `
window.addEventListener("error", function (e) {
  try {
    fetch("/api/client-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: String(e.message || "unknown"), stack: e.error && e.error.stack ? String(e.error.stack).slice(0, 500) : null, url: location.pathname }),
    });
  } catch (_) {}
});
window.addEventListener("unhandledrejection", function (e) {
  try {
    fetch("/api/client-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "unhandledrejection: " + String(e.reason).slice(0, 300), url: location.pathname }),
    });
  } catch (_) {}
});
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <script dangerouslySetInnerHTML={{ __html: errorReporter }} />
        <script dangerouslySetInnerHTML={{ __html: swRegister }} />
        {children}
      </body>
    </html>
  );
}
