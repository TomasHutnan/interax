import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/toast";

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-sans"
});

export const metadata: Metadata = {
  title: "InteraX - MVP",
  description: "InteraX drug interaction checker",
};

export default function Layout({ children }: LayoutProps<"/">) {
    return <html lang={"en"} className={cn("h-full", "antialiased", "font-sans", inter.variable)}>
        <body>
            {children}
            <Toaster/>
        </body>
    </html>
}
