"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/history", label: "History" },
  { href: "/upload", label: "Upload" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <header className="border-b border-stone-200">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Link href="/dashboard" className="font-display text-lg tracking-tight text-stone-900">
          Aperture
        </Link>
        <nav className="hidden items-center gap-8 sm:flex">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm transition-colors",
                pathname?.startsWith(link.href)
                  ? "text-stone-900 font-medium"
                  : "text-stone-500 hover:text-stone-900"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        {/* Signing out is meaningless when auth is bypassed -- the next
            request would just resolve the owner account again. */}
        {!user.single_user_mode && (
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            Sign out
          </button>
        )}
      </div>
      <div className="flex items-center gap-6 overflow-x-auto border-t border-stone-100 px-6 py-2 sm:hidden">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "whitespace-nowrap text-sm",
              pathname?.startsWith(link.href) ? "text-stone-900 font-medium" : "text-stone-500"
            )}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </header>
  );
}
