"use client";

import React, { useEffect, useState } from "react";
import { Database, Search, Plus, ShieldAlert, CheckCircle2 } from "lucide-react";
import { getWatchlist } from "../lib/api";

export function WatchlistView() {
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    getWatchlist()
      .then(setWatchlist)
      .catch(() => {
        setWatchlist([
          { id: 1, document_id: "DEMO-WATCH-01", full_name: "VIKRAM SINGH", nationality: "IND", reason: "Flagged in simulated financial fraud lookout circular.", risk_category: "LOOKOUT_CIRCULAR", status: "ACTIVE" },
          { id: 2, document_id: "Z9999999", full_name: "UNKNOWN HOLDER", nationality: "IND", reason: "Simulated reported lost or stolen passport blank.", risk_category: "STOLEN_PASSPORT", status: "ACTIVE" },
          { id: 3, document_id: "DEMO-006", full_name: "RAHUL VERMA", nationality: "IND", reason: "Simulated multi-identity reuse alert subject.", risk_category: "SUSPENDED", status: "ACTIVE" }
        ]);
      });
  }, []);

  const filtered = watchlist.filter(w =>
    w.document_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    w.full_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg backdrop-blur flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-white tracking-tight">Prototype Reference Watchlist</h1>
            <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400 border border-amber-500/20">
              DEMO / SYNTHETIC REFERENCE DATA
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Simulates border watchlists (stolen passports, lookout circulars) without accessing classified government networks.
          </p>
        </div>

        <div className="relative">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search Document ID or Name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-800/80 pl-9 pr-4 py-1.5 text-xs text-white focus:outline-none focus:border-teal-500 w-64"
          />
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-[11px] uppercase text-slate-400 border-b border-slate-800">
            <tr>
              <th className="px-5 py-3 font-semibold">Document ID</th>
              <th className="px-5 py-3 font-semibold">Subject Name</th>
              <th className="px-4 py-3 font-semibold">Nationality</th>
              <th className="px-4 py-3 font-semibold">Flag Category</th>
              <th className="px-5 py-3 font-semibold">Operational Reason</th>
              <th className="px-4 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filtered.map((item) => (
              <tr key={item.id} className="hover:bg-slate-800/30 transition">
                <td className="px-5 py-3.5 font-mono font-bold text-teal-300">
                  {item.document_id}
                </td>
                <td className="px-5 py-3.5 font-medium text-white">
                  {item.full_name}
                </td>
                <td className="px-4 py-3.5 font-mono text-slate-400">
                  {item.nationality}
                </td>
                <td className="px-4 py-3.5">
                  <span className="rounded bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400 border border-rose-500/20">
                    {item.risk_category}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-slate-300 max-w-md">
                  {item.reason}
                </td>
                <td className="px-4 py-3.5">
                  <span className="text-emerald-400 font-medium text-[11px] flex items-center space-x-1">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>{item.status}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
