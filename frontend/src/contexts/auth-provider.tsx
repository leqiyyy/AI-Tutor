import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AuthContext, type AuthContextValue } from "@/contexts/auth-context";
import {
  AUTH_SESSION_EVENT,
  getAuthSession,
  saveAuthSession,
} from "@/lib/auth-storage";
import { authService } from "@/services/auth";
import type { AuthSession, UserProfile } from "@/types/auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => getAuthSession());
  const [user, setUser] = useState<UserProfile | null>(() => getAuthSession()?.user || null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const syncFromStorage = () => {
      const nextSession = getAuthSession();
      setSession(nextSession);
      setUser(nextSession?.user || null);
    };

    window.addEventListener(AUTH_SESSION_EVENT, syncFromStorage);

    return () => {
      window.removeEventListener(AUTH_SESSION_EVENT, syncFromStorage);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrapSession = async () => {
      const storedSession = getAuthSession();

      if (!storedSession) {
        if (!cancelled) {
          setLoading(false);
        }
        return;
      }

      try {
        const currentUser = await authService.getCurrentUser();

        if (cancelled) {
          return;
        }

        if (!currentUser) {
          authService.logout();
          return;
        }

        const nextSession: AuthSession = {
          ...storedSession,
          user: {
            ...currentUser,
            isDemo: currentUser.isDemo ?? storedSession.user.isDemo,
          },
          isDemo: currentUser.isDemo ?? storedSession.isDemo ?? storedSession.user.isDemo,
        };

        saveAuthSession(nextSession);
        setSession(nextSession);
        setUser(nextSession.user);
      } catch {
        if (!cancelled) {
          authService.logout();
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void bootstrapSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const refreshSession = async () => {
    const storedSession = getAuthSession();

    if (!storedSession) {
      setSession(null);
      setUser(null);
      return null;
    }

    const currentUser = await authService.getCurrentUser();

    if (!currentUser) {
      authService.logout();
      return null;
    }

    const nextSession: AuthSession = {
      ...storedSession,
      user: {
        ...currentUser,
        isDemo: currentUser.isDemo ?? storedSession.user.isDemo,
      },
      isDemo: currentUser.isDemo ?? storedSession.isDemo ?? storedSession.user.isDemo,
    };

    saveAuthSession(nextSession);
    setSession(nextSession);
    setUser(nextSession.user);

    return nextSession.user;
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      session,
      loading,
      isAuthenticated: Boolean(user && session?.accessToken),
      refreshSession,
      logout: () => authService.logout(),
    }),
    [loading, session, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
