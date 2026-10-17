import { createContext, useContext } from "react"

export type User = {
    username: string,
    password: string
}

export const AuthContext = createContext<{ user: User | null, loaded: boolean, setUser: (u: User | null) => void }>({
    user: null,
    loaded: false,
    setUser: () => {}
});

export function useAuth() {
    return useContext(AuthContext);
}