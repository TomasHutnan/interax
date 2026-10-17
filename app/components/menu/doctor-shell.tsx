"use client";
import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthContext } from "@/components/contexts/auth";
import Menu from "@/components/menu/menu";
import { useSession } from "@/lib/hooks/use-session";
import { forgetLegacyUser } from "@/lib/storage";

const LOGIN_PATH = "/doctor";

export default function DoctorShell({ children }: { children: ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const loggedOut = session.loaded && !session.user;

  useEffect(() => forgetLegacyUser(), []);

  // also covers sessions that end while a page is open (expiry, logout elsewhere)
  useEffect(() => {
    if (loggedOut && pathname !== LOGIN_PATH) router.replace(LOGIN_PATH);
  }, [loggedOut, pathname, router]);

  return (
    <AuthContext.Provider value={session}>
      <Menu />
      <main className={"min-h-dvh flex flex-col text-sm py-16 px-8 md:px-32"}>
        {loggedOut && pathname !== LOGIN_PATH ? null : children}
      </main>
    </AuthContext.Provider>
  );
}
