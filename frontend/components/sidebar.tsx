import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  LayoutDashboard,
  PlugZap,
  Sparkles,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/leaks", label: "Leaks", icon: AlertTriangle },
  { href: "/campaigns", label: "Campaigns", icon: Activity },
  { href: "/connections", label: "Connections", icon: PlugZap },
];

export function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-zinc-200 bg-white px-4 py-6">
      <Link href="/dashboard" className="flex items-center gap-2 px-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-orange-400">
          <Sparkles className="h-4 w-4 text-white" />
        </div>
        <span className="text-base font-semibold tracking-tight">
          BrandPulse
        </span>
      </Link>

      <nav className="mt-8 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-900"
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="mt-auto pt-8 text-xs text-zinc-400 px-2">
        <p>X-ray vision for your</p>
        <p>leaking ad spend.</p>
      </div>
    </aside>
  );
}
