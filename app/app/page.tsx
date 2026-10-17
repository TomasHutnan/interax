"use client";
import { Button } from "@/components/ui/button";
import { ClipboardPlus, UserRound } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import Preferences from "@/components/menu/preferences";

export default function Page() {
  const t = useTranslations("home");

  return (
    <div className={"min-h-dvh grid place-items-center"}>
      <Preferences className={"fixed top-2 right-4"} />
      <div
        className={
          "flex flex-col gap-4 min-w-64 border border-muted-foreground surface p-6 shadow-md"
        }
      >
        <div>
          <h1 className={"text-center text-4xl font-bold tracking-tight"}>
            InteraX
          </h1>
          <p className={"text-center"}>{t("selectView")}</p>
        </div>
        <div className={"space-y-1"}>
          <Link href={"/doctor"}>
            <Button className={"w-full"}>
              <ClipboardPlus />
              {t("doctor")}
            </Button>
          </Link>
          <Link href={"/patient"}>
            <Button className={"w-full"}>
              <UserRound />
              {t("patient")}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
