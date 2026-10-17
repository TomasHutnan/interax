import type { Metadata } from "next";
import Link from "next/link";
import Preferences from "@/components/menu/preferences";

export const metadata: Metadata = {
  title: "InteraX - Patient",
};

export default function Layout({ children }: LayoutProps<"/patient">) {
  return (
    <div className={"min-h-dvh flex flex-col"}>
      <header
        className={
          "fixed w-full top-0 z-40 flex h-8 items-center justify-between border-b bg-background/85 backdrop-blur px-4 shadow-md"
        }
      >
        <Link href={"/patient"} className={"text-sm font-bold tracking-tight"}>
          InteraX
        </Link>
        <Preferences />
      </header>
      <main
        className={
          "mx-auto flex w-full max-w-xl flex-1 flex-col px-4 py-16 text-sm"
        }
      >
        {children}
      </main>
    </div>
  );
}
