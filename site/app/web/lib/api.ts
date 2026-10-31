"use client";

import useSWR, { type KeyedMutator } from "swr";
import { api, ApiError } from "./api-core";

// Client-facing entry: `import { api, ApiError, useApi } from "@/lib/api"`.
// Server components must import { api } from "@/lib/api-core" instead (SWR is client-only).
export { api, ApiError, baseUrl } from "./api-core";

export interface UseApiResult<T> {
  data: T | undefined;
  error: ApiError | undefined;
  isLoading: boolean;
  mutate: KeyedMutator<T>;
}

/** SWR hook. Pass null as path to skip fetching. Client components only. */
export function useApi<T>(
  path: string | null,
  opts?: { refreshMs?: number },
): UseApiResult<T> {
  const { data, error, isLoading, mutate } = useSWR<T, ApiError>(
    path,
    (p: string) => api.get<T>(p),
    { refreshInterval: opts?.refreshMs, revalidateOnFocus: false },
  );
  return { data, error, isLoading, mutate };
}
