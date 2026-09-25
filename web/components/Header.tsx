import Link from "next/link";
import SignOutButton from "./SignOutButton";

export default function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-5">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-lg">📡</span>
            <span className="font-semibold tracking-tight">GTA 6 News Radar</span>
          </Link>
          <nav className="flex items-center gap-3 text-sm text-zinc-400">
            <Link href="/" className="hover:text-zinc-100">Feed</Link>
            <Link href="/trending" className="hover:text-zinc-100">Trending</Link>
          </nav>
        </div>
        <SignOutButton />
      </div>
    </header>
  );
}
