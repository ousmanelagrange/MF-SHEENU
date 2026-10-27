// Fournisseur de données Refine : traduit les appels génériques de Refine vers l'API Sheenu.

import type { DataProvider } from "@refinedev/core";
import { api } from "../lib/api";

// Ressource Refine → chemin de l'API
const PATHS: Record<string, string> = {
  persons: "/persons",
  titles: "/titles",
  members: "/members",
  invitations: "/invitations",
  audit: "/audit",
};

const path = (resource: string) => PATHS[resource] ?? `/${resource}`;

export const dataProvider: DataProvider = {
  getApiUrl: () => "",

  getList: async ({ resource, pagination, filters, sorters, meta }) => {
    const query: Record<string, string | number | undefined> = { ...(meta?.query ?? {}) };
    if (pagination?.mode !== "off") {
      const current = pagination?.currentPage ?? 1;
      const size = pagination?.pageSize ?? 20;
      query.skip = (current - 1) * size;
      query.limit = size;
    }
    for (const f of filters ?? []) {
      if ("field" in f && f.value !== undefined && f.value !== null && f.value !== "") {
        query[f.field] = f.value as string;
      }
    }
    if (sorters?.[0]) query.sort = sorters[0].field;
    const data = await api<unknown>(path(resource), { query });
    if (Array.isArray(data)) return { data, total: data.length };
    const page = data as { items: unknown[]; total: number };
    return { data: page.items as never[], total: page.total };
  },

  getOne: async ({ resource, id }) => ({
    data: await api(`${path(resource)}/${id}`),
  }) as never,

  create: async ({ resource, variables }) => ({
    data: await api(path(resource), { method: "POST", body: variables }),
  }) as never,

  update: async ({ resource, id, variables }) => ({
    data: await api(`${path(resource)}/${id}`, { method: "PATCH", body: variables }),
  }) as never,

  deleteOne: async ({ resource, id }) => {
    await api(`${path(resource)}/${id}`, { method: "DELETE" });
    return { data: { id } } as never;
  },

  custom: async ({ url, method, payload, query }) => ({
    data: await api(url, {
      method: method.toUpperCase(),
      body: payload,
      query: query as Record<string, string>,
    }),
  }) as never,
};
