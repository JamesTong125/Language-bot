import type { Metadata } from "next";

import { AuthForm } from "@/components/AuthForm";

export const metadata: Metadata = { title: "Sign up · Language learning bot" };

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
