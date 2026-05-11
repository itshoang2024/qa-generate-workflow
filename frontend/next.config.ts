import { resolve } from "node:path";
import type { NextConfig } from "next";

// Keep next/font/google usable in offline builds by serving checked-in Google
// CSS responses and WOFF2 files instead of fetching fonts.googleapis.com.
process.env.NEXT_FONT_GOOGLE_MOCKED_RESPONSES ??= resolve(
  "src/app/fonts/google-font-responses.cjs"
);

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
