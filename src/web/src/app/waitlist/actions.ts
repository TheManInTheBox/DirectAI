"use server";

// Phase 1: In-memory waitlist store. Replaced by PostgreSQL in Phase 2.
// This is intentionally simple — just collect emails and prove the form works.

const waitlist = new Set<string>();

export interface WaitlistResult {
  success: boolean;
  message: string;
}

export async function joinWaitlist(
  _prev: WaitlistResult | null,
  formData: FormData,
): Promise<WaitlistResult> {
  const email = formData.get("email");

  if (!email || typeof email !== "string") {
    return { success: false, message: "Please enter a valid email address." };
  }

  const trimmed = email.trim().toLowerCase();

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) {
    return { success: false, message: "Please enter a valid email address." };
  }

  if (waitlist.has(trimmed)) {
    return { success: true, message: "You're already on the waitlist! We'll be in touch." };
  }

  waitlist.add(trimmed);
  console.log(`[waitlist] New signup: ${trimmed} (total: ${waitlist.size})`);

  return {
    success: true,
    message: "You're on the list! We'll reach out when it's your turn.",
  };
}
