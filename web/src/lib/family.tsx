// Contexte de la famille courante : famille ouverte, rôle de l'utilisateur, changement de famille.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, session } from "./api";
import type { MyFamily } from "../types";

type FamilyState = {
  family: MyFamily | null;
  loading: boolean;
  isAdmin: boolean;
  canInvite: boolean;
  select: (id: string | null) => void;
  reload: () => Promise<void>;
};

const Ctx = createContext<FamilyState | null>(null);

export function FamilyProvider({ children }: { children: ReactNode }) {
  const [family, setFamily] = useState<MyFamily | null>(null);
  const [familyId, setFamilyId] = useState<string | null>(session.familyId);
  const [loading, setLoading] = useState<boolean>(!!session.familyId);

  const reload = useCallback(async () => {
    if (!session.familyId || !session.access) {
      setFamily(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setFamily(await api<MyFamily>("/families/current"));
    } catch {
      session.setFamily(null);
      setFamily(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [familyId, reload]);

  const select = useCallback((id: string | null) => {
    session.setFamily(id);
    setFamilyId(id);
  }, []);

  return (
    <Ctx.Provider
      value={{
        family,
        loading,
        isAdmin: family?.role === "admin",
        canInvite: family?.role === "admin" || family?.role === "branch_head",
        select,
        reload,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useFamily() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFamily hors de FamilyProvider");
  return ctx;
}
