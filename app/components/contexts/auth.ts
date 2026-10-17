import { createContext, useContext } from "react";

export type Role = "clinician" | "admin";

/**
 * The logged-in clinician. The session itself lives in an HttpOnly cookie the page cannot read.
 */
export type User = {
  username: string;
  role: Role;
};

export const AuthContext = createContext<{
  user: User | null;
  loaded: boolean;
  setUser: (u: User | null) => void;
}>({
  user: null,
  loaded: false,
  setUser: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function parseUser(data: unknown): User | null {
  const u = data as Partial<Record<keyof User, unknown>> | null;
  if (
    typeof u?.username !== "string" ||
    (u.role !== "clinician" && u.role !== "admin")
  )
    return null;

  return { username: u.username, role: u.role };
}
