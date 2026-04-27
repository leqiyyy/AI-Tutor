import { createContext } from "react";
import type { AuthSession, UserProfile } from "@/types/auth";

export interface AuthContextValue {
  user: UserProfile | null;
  session: AuthSession | null;
  loading: boolean;
  isAuthenticated: boolean;
  refreshSession: () => Promise<UserProfile | null>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
