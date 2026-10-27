// Fournisseur d'authentification Refine : connexion, inscription, déconnexion, identité.

import type { AuthProvider } from "@refinedev/core";
import { api, ApiError, session } from "../lib/api";

type Tokens = { access_token: string; refresh_token: string };

export const authProvider: AuthProvider = {
  login: async ({ login, password, redirectTo }) => {
    try {
      const t = await api<Tokens>("/auth/login", {
        method: "POST",
        body: { login, password },
        family: false,
      });
      session.setTokens(t.access_token, t.refresh_token);
      return { success: true, redirectTo: redirectTo ?? "/familles" };
    } catch (e) {
      return {
        success: false,
        error: { name: "Connexion impossible", message: (e as Error).message },
      };
    }
  },

  register: async ({ full_name, login, password, redirectTo }) => {
    const isEmail = String(login).includes("@");
    try {
      const t = await api<Tokens>("/auth/register", {
        method: "POST",
        family: false,
        body: {
          full_name,
          password,
          ...(isEmail ? { email: login } : { phone: login }),
        },
      });
      session.setTokens(t.access_token, t.refresh_token);
      return { success: true, redirectTo: redirectTo ?? "/familles" };
    } catch (e) {
      return {
        success: false,
        error: { name: "Inscription impossible", message: (e as Error).message },
      };
    }
  },

  logout: async () => {
    session.clear();
    return { success: true, redirectTo: "/connexion" };
  },

  check: async () => {
    if (!session.access) return { authenticated: false, redirectTo: "/connexion" };
    return { authenticated: true };
  },

  onError: async (error) => {
    if (error instanceof ApiError && error.status === 401) {
      session.clear();
      return { logout: true, redirectTo: "/connexion" };
    }
    if (error instanceof ApiError && error.code === "not_a_member") {
      session.setFamily(null);
      return { redirectTo: "/familles" };
    }
    return {};
  },

  getIdentity: async () => {
    if (!session.access) return null;
    try {
      return await api("/auth/me", { family: false });
    } catch {
      return null;
    }
  },
};
