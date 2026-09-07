import Link from "next/link";
import { ArrowRight, ShieldCheck, Upload, Video } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function Home() {
  return (
    <div className="space-y-8">
      {/* Hero Welcome */}
      <div className="bg-gradient-to-r from-blue-950/40 via-slate-900 to-slate-900 border border-slate-800 rounded-2xl p-8 relative overflow-hidden">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950/80 border border-blue-800/80 text-blue-400 text-xs font-mono mb-4">
            <ShieldCheck className="w-3.5 h-3.5" />
            Deterministic Inspection Engine
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight sm:text-4xl mb-3">
            Warehouse Handling Video Intelligence
          </h1>
          <p className="text-slate-400 text-sm leading-relaxed mb-6">
            Automated detection and human-in-the-loop review of package drops, forceful releases, dragging, and placement zone violations.
          </p>
          <div className="flex items-center gap-3">
            <Link href="/upload">
              <Button variant="primary">
                <Upload className="w-4 h-4 mr-2" />
                Upload Video for Analysis
              </Button>
            </Link>
            <Link href="/settings/camera">
              <Button variant="secondary">Configure Calibration</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
