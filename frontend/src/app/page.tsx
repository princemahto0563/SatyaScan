"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "../components/Navbar";
import { DashboardView } from "../components/DashboardView";
import { NewScreeningView } from "../components/NewScreeningView";
import { ResultView } from "../components/ResultView";
import { WatchlistView } from "../components/WatchlistView";
import { AnalyticsView } from "../components/AnalyticsView";
import { MethodologyView } from "../components/MethodologyView";
import { ScreeningDetail } from "../lib/types";
import { getScreeningDetail, getScreeningsList } from "../lib/api";
import { ShieldCheck, AlertCircle, Loader2 } from "lucide-react";

export default function Home() {
  const [currentTab, setCurrentTab] = useState<string>("dashboard");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseData, setActiveCaseData] = useState<ScreeningDetail | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [caseError, setCaseError] = useState<string | null>(null);

  // Register service worker on mount for PWA capability
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("ServiceWorker registration failed:", err);
      });
    }
  }, []);

  // Handle opening a specific case from dashboard or case list
  const handleOpenCase = async (caseId: string) => {
    setIsLoadingCase(true);
    setCaseError(null);
    try {
      const data = await getScreeningDetail(caseId);
      setActiveCaseId(caseId);
      setActiveCaseData(data);
      setCurrentTab("result");
    } catch (err: any) {
      console.error("Failed to load case detail:", err);
      setCaseError(err.message || "Failed to load case data.");
    } finally {
      setIsLoadingCase(false);
    }
  };

  // Handle completion of a new screening
  const handleScreeningCompleted = (detail: ScreeningDetail) => {
    setActiveCaseId(detail.id);
    setActiveCaseData(detail);
    setCurrentTab("result");
  };

  // Render view depending on active tab
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-teal-500/30 selection:text-teal-200">
      {/* Top Navigation Bar */}
      <Navbar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCaseError(null);
          setCurrentTab(tab);
        }}
        activeCaseId={activeCaseId}
      />

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 py-6 sm:px-6">
        {isLoadingCase && (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Loader2 className="h-10 w-10 text-teal-400 animate-spin" />
            <p className="text-sm text-slate-400 font-medium">Retrieving cryptographic dossier from database...</p>
          </div>
        )}

        {!isLoadingCase && caseError && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-red-300 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
              <span className="text-sm font-medium">{caseError}</span>
            </div>
            <button
              onClick={() => setCurrentTab("dashboard")}
              className="text-xs underline hover:text-red-200 font-medium"
            >
              Back to Dashboard
            </button>
          </div>
        )}

        {!isLoadingCase && (
          <>
            {currentTab === "dashboard" && (
              <DashboardView
                onStartNewScreening={() => setCurrentTab("screening")}
                onOpenCase={handleOpenCase}
              />
            )}

            {currentTab === "screening" && (
              <NewScreeningView onScreeningCompleted={handleScreeningCompleted} />
            )}

            {currentTab === "result" && activeCaseData && (
              <ResultView
                caseData={activeCaseData}
                onBackToDashboard={() => setCurrentTab("dashboard")}
              />
            )}

            {currentTab === "result" && !activeCaseData && (
              <div className="text-center py-20 bg-slate-900/30 border border-slate-800/80 rounded-2xl p-8 max-w-md mx-auto">
                <ShieldCheck className="h-12 w-12 text-slate-500 mx-auto mb-3" />
                <h3 className="text-base font-bold text-slate-200 mb-1">No Active Case Selected</h3>
                <p className="text-xs text-slate-400 mb-6">
                  Select a completed screening from the dashboard or initiate a new real-time inspection.
                </p>
                <div className="flex justify-center space-x-3">
                  <button
                    onClick={() => setCurrentTab("dashboard")}
                    className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                  >
                    View History
                  </button>
                  <button
                    onClick={() => setCurrentTab("screening")}
                    className="px-4 py-2 text-xs font-semibold rounded-lg bg-teal-600 text-white hover:bg-teal-500 shadow-sm shadow-teal-500/20"
                  >
                    Start New Screening
                  </button>
                </div>
              </div>
            )}

            {currentTab === "watchlist" && <WatchlistView />}

            {currentTab === "analytics" && <AnalyticsView />}

            {currentTab === "methodology" && <MethodologyView />}
          </>
        )}
      </main>

      {/* Footer Security Badge & Build Information */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-4 px-4 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-400"></span>
            <span className="font-medium text-slate-300">SatyaScan v1.0.0-PROD</span>
            <span className="text-slate-500">·</span>
            <span>SIH26188 (MHA / Sashastra Seema Bal)</span>
          </div>
          <div className="flex items-center space-x-4 text-slate-400 text-[11px]">
            <span>ICAO Doc 9303 Compliant</span>
            <span>SHA-256 Chained Audit Trail</span>
            <span>Zero Data Leakage (Edge-Safe)</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
