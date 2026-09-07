import type { Metadata } from "next";
import Link from "next/link";
import { Activity, Camera, LayoutDashboard, ShieldAlert, Upload } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Warehouse AI Video Intelligence",
  description: "Automated warehouse handling video intelligence and risk event review.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 flex flex-col min-h-screen">
        {/* Top Navigation */}
        <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link href="/" className="flex items-center gap-3 group">
                <div className="w-9 h-9 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:bg-blue-600/30 transition-colors">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <span className="font-bold text-base tracking-tight text-white block">
                    Warehouse<span className="text-blue-500">AI</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono tracking-wider uppercase block -mt-0.5">
                    Video Intelligence
                  </span>
                </div>
              </Link>

              <nav className="hidden md:flex items-center gap-1">
                <Link
                  href="/"
                  className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </Link>
                <Link
                  href="/upload"
                  className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  Upload Video
                </Link>
                <Link
                  href="/settings/camera"
                  className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
                >
                  <Camera className="w-4 h-4" />
                  Camera Setup
                </Link>
              </nav>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                API Connected
              </div>
            </div>
          </div>
        </header>

        {/* Mandatory Policy & Responsible-AI Banner per Section 16.2 */}
        <div className="bg-slate-900/90 border-b border-slate-800/60 py-1.5 px-4 text-center text-xs text-slate-400 tracking-wide flex items-center justify-center gap-4">
          <span>⚠️ <strong>Policy Notice:</strong> Risk event, not confirmed damage.</span>
          <span className="hidden sm:inline text-slate-600">|</span>
          <span className="hidden sm:inline">Evidence quality is a diagnostic metric, not probability.</span>
        </div>

        {/* Main Content Area */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-600">
          Warehouse AI Video Intelligence Prototype &bull; Local Deterministic Verification Engine
        </footer>
      </body>
    </html>
  );
}
