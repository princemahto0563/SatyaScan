"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "../components/Navbar";
import { DashboardView } from "../components/DashboardView";
import { NewScreeningView } from "../components/NewScreeningView";
import { ResultView } from "../components/ResultView";
import { WatchlistView } from "../components/WatchlistView";
import { AnalyticsView } from "../components/AnalyticsView";
import { MethodologyView } from "../components/MethodologyView";
import { CheckpointLoginView } from "../components/CheckpointLoginView";
import { ScreeningDetail, UserSession } from "../lib/types";
import {
  getScreeningDetail, checkBackendHealth, HealthStatus,
  getSession, subscribeAuth, logout
} from "../lib/api";
import { ShieldCheck, AlertCircle, Loader2, WifiOff } from "lucide-react";

export default function Home() {
  const [session, setSession] = useState<UserSession | null>(null);
  const [currentTab, setCurrentTab] = useState<string>("dashboard");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseData, setActiveCaseData] = useState<ScreeningDetail | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [backendHealth, setBackendHealth] = useState<HealthStatus | null>(null);

  // Sync auth state with in-memory auth manager
  useEffect(() => {
    setSession(getSession());
    const unsubscribe = subscribeAuth((updatedSession) => {
      setSession(updatedSession);
      if (!updatedSession) {
        // Reset case states on logout/session expiry
        setActiveCaseId(null);
        setActiveCaseData(null);
        setCurrentTab("dashboard");
      }
    });
    return () => {
      unsubscribe();
    };
  }, []);

  // Register service worker on mount for PWA capability
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("ServiceWorker registration failed:", err);
      });
    }
  }, []);

  // Monitor backend health
  useEffect(() => {
    let isMounted = true;
    const pollHealth = async () => {
      const h = await checkBackendHealth();
      if (isMounted) setBackendHealth(h);
    };
    pollHealth();
    const interval = setInterval(pollHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
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

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Top Navigation Bar */}
      <Navbar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCaseError(null);
          setCurrentTab(tab);
        }}
        activeCaseId={activeCaseId}
        session={session}
        onLogout={session ? handleLogout : undefined}
      />

      {/* Backend Offline Warning Banner if Disconnected */}
      {backendHealth && !backendHealth.online && (
        <div className="border-b border-amber-300 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/40 px-4 py-2 text-xs text-amber-800 dark:text-amber-300">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <WifiOff className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
              <span>
                <strong>Screening Service Unavailable:</strong> The local FastAPI screening service is offline or unreachable. Please start the backend service to run verifications.
              </span>
            </div>
            <span className="font-mono text-[11px] text-amber-700 dark:text-amber-400/80 hidden sm:inline">
              uvicorn backend.app.main:app
            </span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-3 py-5 sm:px-6 sm:py-6">
        {/* Unauthenticated State: Render Checkpoint Login View */}
        {!session ? (
          <CheckpointLoginView onLoginSuccess={(newSession) => setSession(newSession)} />
        ) : (
          /* Authenticated State: Workstation Tabs */
          <>
            {isLoadingCase && (
              <div className="flex flex-col items-center justify-center py-24 space-y-4">
                <Loader2 className="h-8 w-8 text-teal-600 dark:text-teal-400 animate-spin" />
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Retrieving cryptographic dossier from database...
                </p>
              </div>
            )}

            {!isLoadingCase && caseError && (
              <div className="mb-6 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/30 p-4 text-rose-800 dark:text-rose-200 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <AlertCircle className="h-5 w-5 text-rose-600 dark:text-rose-400 flex-shrink-0" />
                  <span className="text-sm font-medium">{caseError}</span>
                </div>
                <button
                  onClick={() => setCurrentTab("dashboard")}
                  className="text-xs underline hover:text-rose-950 dark:hover:text-rose-100 font-medium"
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
                  <div className="text-center py-16 bg-white dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 max-w-md mx-auto shadow-sm">
                    <ShieldCheck className="h-12 w-12 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
                    <h3 className="text-base font-bold text-slate-900 dark:text-slate-200 mb-1">
                      No Active Case Selected
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
                      Select a completed screening from the dashboard or initiate a new inspection.
                    </p>
                    <div className="flex justify-center space-x-3">
                      <button
                        onClick={() => setCurrentTab("dashboard")}
                        className="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
                      >
                        View History
                      </button>
                      <button
                        onClick={() => setCurrentTab("screening")}
                        className="px-4 py-2 text-xs font-semibold rounded-lg bg-teal-600 text-white hover:bg-teal-500 shadow-sm transition"
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
          </>
        )}
      </main>

      {/* Footer Security Badge & Technical Delineation */}
      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 py-3.5 px-4 text-xs text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-600 dark:bg-teal-400"></span>
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              SatyaScan Workstation v1.0.0
            </span>
            <span className="text-slate-300 dark:text-slate-700">·</span>
            <span>SIH26188 (MHA / Sashastra Seema Bal)</span>
          </div>
          <div className="flex items-center space-x-4 text-[11px] text-slate-500 dark:text-slate-400">
            <span>ICAO Doc 9303 Compliant</span>
            <span>SHA-256 Chained Audit Trail</span>
            <span>Edge-Safe Verification</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
