"use client";

import { useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  isServer,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";

import { Toaster } from "@/components/ui/sonner";

/**
 * Build a QueryClient with defaults tuned for the SUN.RISER QA workflow demo:
 *
 * - Backend artifacts (features, tasks, sync events, coverage) rarely change
 *   inside a single run; 30s staleTime keeps the UI feeling live without
 *   hammering /api/v1/runs/{id} after every focus event.
 * - We disable refetchOnWindowFocus because the demo backend logs every
 *   request — focus refetch makes the local terminal noisy during Alt-Tab.
 * - We don't throwOnError; pages render Skeleton on isPending and an
 *   inline error banner on isError, so the error stays scoped to the panel
 *   that owns the query.
 * - Mutations get retry: 0 — review-decision and sign-off are user actions
 *   that we want to surface failures on immediately, not silently retry.
 */
function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
        refetchOnWindowFocus: false,
        throwOnError: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

/**
 * Next.js App Router renders `Providers` on the server during initial HTML
 * generation and again on the client. We need a fresh QueryClient per SSR
 * request (no cross-request cache pollution) but a single persistent client
 * in the browser (cache survives navigation).
 */
function getQueryClient(): QueryClient {
  if (isServer) return makeQueryClient();
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: React.ReactNode }) {
  // useState lazy initialiser ensures the reference is stable across the
  // Strict Mode double-render in development.
  const [queryClient] = useState(() => getQueryClient());

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster position="bottom-right" richColors closeButton />
        {process.env.NODE_ENV === "development" ? (
          <ReactQueryDevtools
            initialIsOpen={false}
            buttonPosition="bottom-left"
          />
        ) : null}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
