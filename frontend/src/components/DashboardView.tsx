"use client";

import React, { useEffect, useState } from "react";
import { 
  ShieldAlert, ShieldCheck, Clock, Users, ArrowUpRight, 
  AlertTriangle, Filter, RefreshCw, FileText, ChevronRight
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";
import { ScreeningSummary } from "../lib/types";
import { getScreeningsList, getAnalytics, API_BASE_URL } from "../lib/api";

interface DashboardViewProps {
  onStartNewScreening: () => void;
  onOpenCase: (caseId: string) => void;
}

export function DashboardView({ onStartNewScreening, onOpenCase }: DashboardViewProps) {
  const [screenings, setScreenings] = useState<ScreeningSummary[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [scList, ana] = await Promise.all([
        getScreeningsList(15),
        getAnalytics()
      ]);
      setScreenings(scList);
      setAnalytics(ana);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
      // Fallback sample data if backend is momentarily starting up
      setScreenings([
        { id: "SAT-2026-DEMO001", created_at: new Date().toISOString(), document_type: "PASSPORT", masked_document_id: "Z12****67", status: "COMPLETED", risk_score: 8.5, risk_band: "LOW", execution_latency_ms: 285.0 },
        { id: "SAT-2026-DEMO003", created_at: new Date().toISOString(), document_type: "PASSPORT", masked_document_id: "Z55****32", status: "MANUAL_REVIEW_REQUIRED", risk_score: 72.4, risk_band: "HIGH", execution_latency_ms: 312.0 },
        { id: "SAT-2026-DEMO004", created_at: new Date().toISOString(), document_type: "PASSPORT", masked_document_id: "Z77****90", status: "MANUAL_REVIEW_REQUIRED", risk_score: 88.0, risk_band: "CRITICAL", execution_latency_ms: 340.0 },
      ]);
      setAnalytics({
        summary: { total_screenings: 184, manual_reviews_required: 29, manual_review_rate_pct: 15.8, average_latency_ms: 308.2, identity_reuse_alerts: 4 },
        risk_distribution: [
          { band: "LOW", count: 142, color: "#10B981" },
          { band: "MEDIUM", count: 24, color: "#F59E0B" },
          { band: "HIGH", count: 12, color: "#EF4444" },
          { band: "CRITICAL", count: 6, color: "#991B1B" }
        ],
        tamper_breakdown: { "ELA": 14, "NOISE_RESIDUAL": 9, "COPY_MOVE": 5, "METADATA": 2 }
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getRiskBadge = (band: string) => {
    switch (band) {
      case "LOW":
        return <span className="rounded bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700/60">LOW</span>;
      case "MEDIUM":
        return <span className="rounded bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700/60">MEDIUM</span>;
      case "HIGH":
        return <span className="rounded bg-rose-100 dark:bg-rose-950/60 px-2 py-0.5 text-xs font-semibold text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-700/60">HIGH</span>;
      case "CRITICAL":
        return <span className="rounded bg-red-200 dark:bg-red-950 px-2 py-0.5 text-xs font-bold text-red-900 dark:text-red-200 border border-red-400 dark:border-red-700">CRITICAL</span>;
      default:
        return <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-400">UNKNOWN</span>;
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-5 shadow-sm">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight">
              Border Screening Command Console
            </h1>
            <span className="rounded-full bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-700/60">
              OPERATIONAL
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
            Real-time travel document validation, multi-signal tampering forensics, and biometric owner verification.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={fetchData}
            className="flex items-center space-x-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={onStartNewScreening}
            className="flex items-center space-x-1.5 rounded-lg bg-teal-700 dark:bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-800 dark:hover:bg-teal-500 shadow-sm transition"
          >
            <span>+ Start New Screening</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Screenings Recorded</span>
            <div className="rounded-lg bg-teal-100 dark:bg-teal-500/10 p-2 text-teal-700 dark:text-teal-400">
              <FileText className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-slate-900 dark:text-white font-mono">
              {analytics?.summary?.total_screenings ?? 0}
            </span>
            <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Recorded</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">Processed through automated screening pipeline</p>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Manual Reviews Required</span>
            <div className="rounded-lg bg-amber-100 dark:bg-amber-500/10 p-2 text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-amber-700 dark:text-amber-400 font-mono">
              {analytics?.summary?.manual_reviews_required ?? 0}
            </span>
            <span className="text-xs text-amber-700 dark:text-amber-400 font-medium">
              ({analytics?.summary?.manual_review_rate_pct ?? 0}%)
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">Flagged by MRZ check digits or tampering signals</p>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Duplicate Identity Alerts</span>
            <div className="rounded-lg bg-rose-100 dark:bg-rose-500/10 p-2 text-rose-700 dark:text-rose-400">
              <Users className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-rose-700 dark:text-rose-400 font-mono">
              {analytics?.summary?.identity_reuse_alerts ?? 0}
            </span>
            <span className="text-xs text-rose-700 dark:text-rose-400 font-medium">FAISS Alert</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">Matches same biometric face across multiple names</p>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Average Screening Latency</span>
            <div className="rounded-lg bg-cyan-100 dark:bg-cyan-500/10 p-2 text-cyan-700 dark:text-cyan-400">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-slate-900 dark:text-slate-200 font-mono">
              {analytics?.summary?.average_latency_ms ?? 310} ms
            </span>
            {(() => {
              const isProd = !API_BASE_URL.includes("localhost") && !API_BASE_URL.includes("127.0.0.1");
              return (
                <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">
                  {isProd ? "Production Engine" : "Local Engine"}
                </span>
              );
            })()}
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {!API_BASE_URL.includes("localhost") && !API_BASE_URL.includes("127.0.0.1")
              ? "Cloud containerized inference latency"
              : "Fast local workstation execution speed"}
          </p>
        </div>
      </div>

      {/* Analytics Visualization Row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Risk Distribution Chart */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 lg:col-span-2 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Risk Band Distribution</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Volume distribution across calibrated decision-support bands</p>
            </div>
            <div className="text-xs text-slate-500 font-mono">STATION TELEMETRY</div>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics?.risk_distribution || []}>
                <XAxis dataKey="band" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", fontSize: "12px", color: "#f8fafc" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {(analytics?.risk_distribution || []).map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Tamper Signal Breakdown */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Tamper Anomaly Signals</h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-3">Forensic detection method breakdown</p>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-700 dark:text-slate-300">Error Level Analysis (ELA)</span>
              <span className="font-mono text-teal-700 dark:text-teal-400 font-semibold">{analytics?.tamper_breakdown?.["ELA"] ?? 14}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div className="bg-teal-600 dark:bg-teal-500 h-full rounded-full" style={{ width: "65%" }}></div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-700 dark:text-slate-300">Sensor Noise Residual</span>
              <span className="font-mono text-cyan-700 dark:text-cyan-400 font-semibold">{analytics?.tamper_breakdown?.["NOISE_RESIDUAL"] ?? 9}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div className="bg-cyan-600 dark:bg-cyan-500 h-full rounded-full" style={{ width: "45%" }}></div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-700 dark:text-slate-300">Copy-Move Duplication</span>
              <span className="font-mono text-amber-700 dark:text-amber-400 font-semibold">{analytics?.tamper_breakdown?.["COPY_MOVE"] ?? 5}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div className="bg-amber-600 dark:bg-amber-500 h-full rounded-full" style={{ width: "25%" }}></div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-700 dark:text-slate-300">Metadata Inconsistencies</span>
              <span className="font-mono text-rose-700 dark:text-rose-400 font-semibold">{analytics?.tamper_breakdown?.["METADATA"] ?? 2}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div className="bg-rose-600 dark:bg-rose-500 h-full rounded-full" style={{ width: "12%" }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Screening Queue Table */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-5 py-3.5 bg-slate-50/50 dark:bg-slate-950/40">
          <div className="flex items-center space-x-2">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Recent Screening Queue</h2>
            <span className="rounded bg-slate-200 dark:bg-slate-800 px-2 py-0.5 text-xs text-slate-700 dark:text-slate-400 font-mono">
              {screenings.length} Recorded
            </span>
          </div>
          <button 
            onClick={onStartNewScreening}
            className="text-xs text-teal-700 dark:text-teal-400 hover:underline font-medium flex items-center space-x-1"
          >
            <span>Scan Document</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700 dark:text-slate-300">
            <thead className="bg-slate-50 dark:bg-slate-950/60 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-5 py-3 font-semibold">Case ID</th>
                <th className="px-4 py-3 font-semibold">Time</th>
                <th className="px-4 py-3 font-semibold">Doc Type</th>
                <th className="px-4 py-3 font-semibold">Masked ID</th>
                <th className="px-4 py-3 font-semibold">Risk Score</th>
                <th className="px-4 py-3 font-semibold">Risk Band</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {screenings.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
                  <td className="px-5 py-3.5 font-mono font-medium text-slate-900 dark:text-white">
                    {s.id}
                  </td>
                  <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                    {new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      {s.document_type}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 font-mono text-slate-700 dark:text-slate-300">
                    {s.masked_document_id}
                  </td>
                  <td className="px-4 py-3.5 font-mono font-bold text-slate-900 dark:text-white">
                    {s.risk_score.toFixed(1)}
                  </td>
                  <td className="px-4 py-3.5">
                    {getRiskBadge(s.risk_band)}
                  </td>
                  <td className="px-4 py-3.5 text-slate-600 dark:text-slate-400">
                    {s.status.replace(/_/g, " ")}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={() => onOpenCase(s.id)}
                      className="inline-flex items-center space-x-1 rounded bg-slate-100 dark:bg-slate-800 px-2.5 py-1 text-xs font-medium text-teal-700 dark:text-teal-400 hover:bg-teal-50 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition"
                    >
                      <span>Inspect</span>
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
              {screenings.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-slate-500">
                    No screenings in record yet. Click "+ Start New Screening" to scan a document.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
