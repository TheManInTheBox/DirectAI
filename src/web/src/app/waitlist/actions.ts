"use server";

import { addToWaitlist } from "@/lib/waitlist-store";

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

  try {
    const { alreadyExists } = await addToWaitlist(trimmed);

    if (alreadyExists) {
      return { success: true, message: "You're already on the waitlist! We'll be in touch." };
    }

    return {
      success: true,
      message: "You're on the list! We'll reach out when it's your turn.",
    };
  } catch (error) {
    console.error("[waitlist] Failed to persist signup:", error);
    return {
      success: false,
      message: "Something went wrong. Please try again.",
    };
  }
}
