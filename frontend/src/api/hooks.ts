import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Params } from "./client";
import type { Paginated } from "./types";

export function useList<T>(resource: string, params: Params, enabled = true) {
  return useQuery({
    queryKey: [resource, "list", params],
    queryFn: () => api.get<Paginated<T>>(`/${resource}/`, params),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useOne<T>(resource: string, id: string | number | undefined) {
  return useQuery({
    queryKey: [resource, "one", id],
    queryFn: () => api.get<T>(`/${resource}/${id}/`),
    enabled: id !== undefined,
  });
}

/** First 100 records of a resource, for select inputs. */
export function useOptions<T>(resource: string, params: Params = {}) {
  return useQuery({
    queryKey: [resource, "options", params],
    queryFn: async () => {
      // Most resources are paginated; small lookup lists (tags) return a plain array.
      const data = await api.get<Paginated<T> | T[]>(`/${resource}/`, { page_size: 100, ...params });
      return Array.isArray(data) ? data : data.results;
    },
    staleTime: 60_000,
  });
}

/** Any mutation refreshes every query: the app is small and cross-resource data (dashboard, notifications) stays honest. */
export function useSave<T>(resource: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: unknown }) =>
      id ? api.patch<T>(`/${resource}/${id}/`, data) : api.post<T>(`/${resource}/`, data),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useRemove(resource: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/${resource}/${id}/`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useAction<T = unknown>(resource: string, action: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data?: unknown }) => api.post<T>(`/${resource}/${id}/${action}/`, data),
    onSuccess: () => qc.invalidateQueries(),
  });
}
