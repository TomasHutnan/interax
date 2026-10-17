import type { Metadata } from "next";
import DoctorShell from "@/components/menu/doctor-shell";

export const metadata: Metadata = {
    title: "InteraX - Doctor"
};

export default function Layout({ children }: LayoutProps<"/doctor">) {
    return <DoctorShell>{children}</DoctorShell>
}
