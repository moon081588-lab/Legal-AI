/** @type {import('next').NextConfig} */

// In production set BACKEND_URL to the deployed API (e.g. https://legal-ai-api.fly.dev).
// Keeping the browser on one origin means no CORS preflight on the SSE stream.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          // A victim's device may be shared; never let this page be cached by proxies.
          { key: "Cache-Control", value: "no-store, max-age=0" },
        ],
      },
    ];
  },
};

export default nextConfig;
