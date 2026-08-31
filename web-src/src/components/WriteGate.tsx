import type { ReactNode } from "react";

export function currentRole(): string {
  try {
    const user = JSON.parse(localStorage.getItem("pdp_user") || "null");
    return user?.role || "operator";
  } catch {
    return "operator";
  }
}

export function isViewer(): boolean {
  return currentRole() === "viewer";
}

export function WriteGate({ children }: { children: ReactNode }) {
  if (isViewer()) return null;
  return <>{children}</>;
}
