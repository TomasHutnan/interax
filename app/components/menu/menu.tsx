"use client";
import Link from "next/link";
import { Button } from "../ui/button";
import { SquareArrowRightExit, UserCircle } from "lucide-react";
import { useAuth } from "../contexts/auth";
import { useRouter } from "next/navigation";
import { toast } from "../ui/toast";
import { baseFetcher } from "@/lib/hooks/use-swr-fetch";

export default function Menu() {
  const { user, loaded, setUser } = useAuth();
  const router = useRouter();

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
      title: "Logged out successfully.",
    });
    router.replace("/doctor");
  }

  return (
    <header
      className={
        "fixed top-0 flex justify-between border-b place-items-center items-center px-4 py-0 w-full bg-background z-50 shadow-md"
      }
    >
      <div>
        <Link href={"/doctor/code"}>
          <p className={"text-center text-sm font-bold tracking-tight"}>
            InteraX
          </p>
        </Link>
      </div>
      <div>
        <Button variant={"ghost"}>
          <UserCircle />
          {!loaded
            ? ""
            : !user
              ? "Not logged in"
              : `Logged in as ${user.username}`}
        </Button>
        {user && (
          <Button variant={"ghost"} onClick={logout}>
            <SquareArrowRightExit />
            Logout
          </Button>
        )}
      </div>
    </header>
  );
}
