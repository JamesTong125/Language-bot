import type { NextConfig } from "next";

// Docker bind mounts on Windows and macOS don't deliver file-change events, so Compose
// turns on polling for the dev server through this variable.
const pollIntervalMs = Number(process.env.NEXT_WATCH_POLL_MS) || undefined;

const nextConfig: NextConfig = {
  cacheComponents: true,
  ...(pollIntervalMs ? { watchOptions: { pollIntervalMs } } : {}),
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
