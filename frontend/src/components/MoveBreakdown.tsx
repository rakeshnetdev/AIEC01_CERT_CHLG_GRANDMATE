import { BookOpen, CheckCircle } from "lucide-react";
import type { CoachReport, Severity } from "../lib/api";

interface MoveBreakdownProps {
  report: CoachReport;
}

export function MoveBreakdown({ report }: MoveBreakdownProps) {
  const getSeverityColor = (label: Severity) => {
    switch (label) {
      case "blunder": return "bg-red-500/20 text-red-400 border border-red-500/30";
      case "mistake": return "bg-amber-500/20 text-amber-400 border border-amber-500/30";
      case "inaccuracy": return "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20";
      default: return "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-4 shadow-xl">
      <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-indigo-400" /> Move-by-Move Analysis
      </h4>
      {report.findings.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/5 text-slate-500 font-semibold">
                <th className="py-3 px-4">Ply</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Mistake Explanation</th>
                <th className="py-3 px-4 text-right">Action Plan</th>
              </tr>
            </thead>
            <tbody>
              {report.findings.map((f, index) => (
                <tr key={index} className="border-b border-white/5 hover:bg-slate-900/20 transition-all">
                  <td className="py-4 px-4 font-mono font-semibold text-slate-400">#{f.ply}</td>
                  <td className="py-4 px-4">
                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${getSeverityColor(f.label)}`}>
                      {f.label}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-slate-200 leading-normal max-w-xs md:max-w-sm">
                    {f.why}
                  </td>
                  <td className="py-4 px-4 text-right font-medium text-sky-400 max-w-xs">
                    {f.correct_plan}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm p-4 rounded-lg">
          <CheckCircle className="w-5 h-5" />
          <span>No errors detected in this game! Exceptional play!</span>
        </div>
      )}
    </div>
  );
}
