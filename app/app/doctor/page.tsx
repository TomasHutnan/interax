"use client";
import { useEffect, useState, SubmitEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { parseUser, useAuth } from "@/components/contexts/auth";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import {
  baseFetcher,
  getErrorMessage,
  HttpError,
} from "@/lib/hooks/use-swr-fetch";

const INPUT_CLASS =
  "w-full rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export default function Page() {
  const { user, loaded, setUser } = useAuth();
  const router = useRouter();
  const t = useTranslations("auth");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) router.replace("/doctor/code");
  }, [user, router]);

  function onSubmit(e: SubmitEvent) {
    e.preventDefault();
    if (!username || !password || loading) return;

    setLoading(true);
    const promise = baseFetcher("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }).then(async (res) => {
      if (!res.ok) throw new HttpError(res.status, res.statusText);

      const user = parseUser(await res.json());
      if (!user) throw new Error(t("login.unexpectedResponse"));
      return user;
    });

    toast
      .promise(promise, {
        loading: t("login.toast.loading"),
        success: t("login.toast.success"),
        error: (e) =>
          getErrorMessage(e, {
            401: t("login.toast.invalidCredentials"),
            429: t("login.toast.tooManyAttempts"),
          }),
      })
      .then((user) => {
        setPassword("");
        setUser(user);
        router.push("/doctor/code");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  if (!loaded || user) return null;

  return (
    <div className={"flex-1 grid place-items-center"}>
      <form
        onSubmit={onSubmit}
        className={
          "flex flex-col gap-2 min-w-64 border border-muted-foreground surface p-6 shadow-md"
        }
      >
        <h1 className={"text-center text-sm"}>{t("login.heading")}</h1>
        <input
          type={"text"}
          className={INPUT_CLASS}
          placeholder={t("login.username")}
          autoComplete={"username"}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type={"password"}
          className={INPUT_CLASS}
          placeholder={t("login.password")}
          autoComplete={"current-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div className={"flex justify-center"}>
          <Button
            className={"min-w-1/3"}
            type={"submit"}
            disabled={!username || !password || loading}
          >
            {loading ? t("login.submitting") : t("login.submit")}
          </Button>
        </div>
      </form>
    </div>
  );
}
