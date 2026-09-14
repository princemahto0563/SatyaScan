"use client";

import React from "react";
import { ShieldCheck, Activity, Search, Database, BarChart3, BookOpen, UserCircle, PlusCircle } from "lucide-react";

interface NavbarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  activeCaseId?: string | null;
}

export function Navbar({ currentTab, onSelectTab, activeCaseId }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-3 py-2.5 sm:px-6">
        {/* Left: Brand & Authority */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onSelectTab("dashboard")}>
          <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400 shadow-sm shadow-teal-500/10">
            <ShieldCheck className="h-5 w-5 sm:h-6 sm:w-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-lg sm:text-xl font-bold tracking-tight text-white">SatyaScan</span>
              <span className="rounded bg-teal-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-teal-300 border border-teal-500/30">
                SIH26188
              </span>
            </div>
            <p className="text-[11px] sm:text-xs text-slate-400 font-medium">
              Sashastra Seema Bal (SSB) · Ministry of Home Affairs
            </p>
          </div>
        </div>

        {/* Center: Navigation Actions (Responsive scroll on mobile/tablet) */}
        <nav className="flex items-center space-x-1 rounded-lg border border-slate-800/80 bg-slate-900/60 p-1 overflow-x-auto max-w-full">
          <button
            onClick={() => onSelectTab("dashboard")}
            className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              currentTab === "dashboard"
                ? "bg-slate-800 text-teal-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => onSelectTab("screening")}
            className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
              currentTab === "screening"
                ? "bg-teal-600 text-white shadow-sm shadow-teal-600/30"
                : "bg-teal-950/40 text-teal-300 hover:bg-teal-900/40 border border-teal-800/40"
            }`}
          >
            <PlusCircle className="h-3.5 w-3.5" />
            <span>New Screening</span>
          </button>

          {activeCaseId && (
            <button
              onClick={() => onSelectTab("result")}
              className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                currentTab === "result"
                  ? "bg-cyan-950/80 text-cyan-300 border border-cyan-700/50 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              <Search className="h-3.5 w-3.5" />
              <span>Case: {activeCaseId.replace("SAT-2026-", "#")}</span>
            </button>
          )}

          <button
            onClick={() => onSelectTab("watchlist")}
            className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              currentTab === "watchlist"
                ? "bg-slate-800 text-teal-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Database className="h-3.5 w-3.5" />
            <span>Watchlist</span>
          </button>

          <button
            onClick={() => onSelectTab("analytics")}
            className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              currentTab === "analytics"
                ? "bg-slate-800 text-teal-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Analytics</span>
          </button>

          <button
            onClick={() => onSelectTab("methodology")}
            className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              currentTab === "methodology"
                ? "bg-slate-800 text-teal-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Standards & Docs</span>
          </button>
        </nav>

        {/* Right: Station & Operator Status */}
        <div className="flex items-center space-x-3">
          <div className="hidden lg:block text-right text-xs">
            <div className="flex items-center justify-end space-x-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="font-semibold text-slate-200">Insp. R. Kumar</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">CP-DEL-NORTH · ONLINE</span>
          </div>

          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 border border-slate-700 text-slate-300">
            <UserCircle className="h-5 w-5" />
          </div>
        </div>
      </div>
    </header>
  );
}
