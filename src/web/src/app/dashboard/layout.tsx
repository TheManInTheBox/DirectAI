import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { DashboardSidebar } from "@/components/dashboard-sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Defense-in-depth — middleware already protects /dashboard/*
  const session = await auth();
  if (!session?.user) redirect("/login");

  return (
    <div className="flex min-h-[calc(100vh-65px)]">
      <DashboardSidebar />
      <div className="flex-1 overflow-y-auto p-6 lg:p-8">{children}</div>
    </div>
  );
}
