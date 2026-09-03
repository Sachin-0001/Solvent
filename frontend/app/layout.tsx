import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

/**
 * Display face used only for the Solvent wordmark (the text *is* the logo -
 * there is no icon mark). Space Grotesk's geometric, slightly condensed
 * letterforms read as fintech/infrastructure rather than generic SaaS, and
 * sit distinctly apart from Inter's UI text without clashing with it.
 */
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["500", "700"],
});

export const metadata: Metadata = {
  title: "Solvent - Settlement Intelligence",
  description: "AI finance-controller pipeline for reconciliation, tax, and settlement forecasting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${spaceGrotesk.variable} h-full`}
    >
      <body className="min-h-full bg-[var(--bg)] text-[var(--fg)] antialiased" suppressHydrationWarning>{children}</body>
    </html>
  );
}
