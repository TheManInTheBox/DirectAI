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
  const company = formData.get("company");
  const workload = formData.get("workload");
  const details = formData.get("details");

  if (!email || typeof email !== "string") {
    return { success: false, message: "Please enter a valid email address." };
  }

  const trimmed = email.trim().toLowerCase();

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) {
    return { success: false, message: "Please enter a valid email address." };
  }

  // Log the full inquiry for now — will route to CRM / email later
  console.log("[inquiry]", {
    email: trimmed,
    company: typeof company === "string" ? company.trim() : "",
    workload: typeof workload === "string" ? workload : "",
    details: typeof details === "string" ? details.trim() : "",
    timestamp: new Date().toISOString(),
  });

  try {
    const { alreadyExists } = await addToWaitlist(trimmed);

    if (alreadyExists) {
      return {
        success: true,
        message: "We already have your info — an engineer will follow up shortly.",
      };
    }

    return {
      success: true,
      message: "Got it. An engineer will reach out within one business day.",
    };
  } catch (error) {
    console.error("[inquiry] Failed to persist signup:", error);
    return {
      success: false,
      message: "Something went wrong. Please try again.",
    };
  }
}
