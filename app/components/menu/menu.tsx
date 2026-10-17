"use client";
import Link from "next/link";
import { Button } from "../ui/button";
import { SquareArrowRightExit, UserCircle } from "lucide-react";
import { useAuth } from "../contexts/auth";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "../ui/toast";
import { baseFetcher } from "@/lib/hooks/use-swr-fetch";
import Preferences from "./preferences";

export default function Menu() {
  const { user, loaded, setUser } = useAuth();
  const router = useRouter();
  const t = useTranslations("menu");

  async function logout() {
    try {
      // ends the session on the server; the cookie alone cannot be removed by the page
      await baseFetcher("/api/auth/logout", { method: "POST" });
    } catch {
      // offline: the session still expires on its own
    }
    setUser(null);
    toast.add({
      type: "info",
      title: t("logout.success"),
    });
    router.replace("/doctor");
  }

  return (
    <header
      className={
        "fixed top-0 flex justify-between border-b place-items-center items-center px-4 py-0 w-full bg-background/85 backdrop-blur z-50 shadow-md"
      }
    >
      <div>
        <Link href={"/doctor/code"}>
          <p className={"text-center text-sm font-bold tracking-tight"}>
            InteraX
          </p>
        </Link>
      </div>
      <div className={"flex items-center"}>
        <Preferences />
        <Button variant={"ghost"}>
          <UserCircle />
          {!loaded
            ? ""
            : !user
              ? t("user.notLoggedIn")
              : t("user.loggedInAs", { username: user.username })}
        </Button>
        {user && (
          <Button variant={"ghost"} onClick={logout}>
            <SquareArrowRightExit />
            {t("logout.button")}
          </Button>
        )}
      </div>
    </header>
  );
}
