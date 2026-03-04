"use client";

import { usePathname } from "next/navigation";
import { Footer } from "./footer";

/**
 * Renders the Footer only on non-dashboard pages.
 * Dashboard has its own layout chrome — no marketing footer.
 */
export function ConditionalFooter() {
  const pathname = usePathname();
  if (pathname.startsWith("/dashboard")) return null;
  return <Footer />;
}
