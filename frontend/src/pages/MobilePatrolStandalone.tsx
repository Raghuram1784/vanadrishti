import { MobileCameraPanel } from "@/components/live/MobileCameraPanel";
import { Link } from "react-router-dom";
import { ArrowLeft, Shield } from "lucide-react";

export default function MobilePatrolStandalone() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-3 sm:p-6 max-w-4xl mx-auto">
      <header className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
        <Link
          to="/monitor"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          <ArrowLeft size={14} />
          <span>RETURN TO COMMAND CENTER</span>
        </Link>
        <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
          <Shield size={14} className="text-emerald-500" />
          <span>VANADRISHTI FIELD NODE C-21</span>
        </div>
      </header>

      <main>
        <MobileCameraPanel />
      </main>
    </div>
  );
}
