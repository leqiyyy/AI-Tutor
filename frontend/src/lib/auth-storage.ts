import { appEnv } from "@/lib/env";
import type { AuthSession } from "@/types/auth";

export const AUTH_SESSION_EVENT = "auth-session-changed";

function emitAuthSessionChange() {
  window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
}

export function getAuthSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(appEnv.authStorageKey);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function saveAuthSession(session: AuthSession) {
  localStorage.setItem(appEnv.authStorageKey, JSON.stringify(session));
  emitAuthSessionChange();
}

export function clearAuthSession() {
  localStorage.removeItem(appEnv.authStorageKey);
  emitAuthSessionChange();
}
