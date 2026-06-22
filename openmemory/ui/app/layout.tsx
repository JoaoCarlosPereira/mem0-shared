import type React from "react";
import type { Metadata } from "next";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { Navbar } from "@/components/Navbar";
import { Toaster } from "@/components/ui/toaster";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Providers } from "./providers";
import { APP_DESCRIPTION, APP_PAGE_TITLE } from "@/lib/branding";

export const metadata: Metadata = {
  title: APP_PAGE_TITLE,
  description: APP_DESCRIPTION,
  icons: {
    icon: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className="h-screen font-sans antialiased flex flex-col bg-zinc-950">
        <Providers>
          <ThemeProvider
            attribute="class"
            defaultTheme="dark"
            enableSystem
            disableTransitionOnChange
          >
            <Navbar />
            <ScrollArea className="h-[calc(100vh-64px)]">{children}</ScrollArea>
            <Toaster />
          </ThemeProvider>
        </Providers>
      </body>
    </html>
  );
}
