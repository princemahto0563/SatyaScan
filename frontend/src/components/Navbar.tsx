"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, Activity, PlusCircle, Search, Database, 
  BarChart3, BookOpen, Sun, Moon, Wifi, WifiOff, Menu, X, Monitor,
  LogOut, MapPin, User
} from "lucide-react";
import { checkBackendHealth, HealthStatus } from "../lib/api";
import { UserSession } from "../lib/types";

interface NavbarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  activeCaseId?: string | null;
  session?: UserSession | null;
  onLogout?: () => void;
}

export function Navbar({ currentTab, onSelectTab, activeCaseId, session, onLogout }: NavbarProps) {
  const [isDark, setIsDark] = useState(true);
  const [backendHealth, setBackendHealth] = useState<HealthStatus | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isNetworkOnline, setIsNetworkOnline] = useState(true);

  // Initialize theme state from DOM
  useEffect(() => {
    if (typeof window !== "undefined") {
      const hasDark = document.documentElement.classList.contains("dark");
      setIsDark(hasDark);
      setIsNetworkOnline(navigator.onLine);

      const handleOnline = () => setIsNetworkOnline(true);
      const handleOffline = () => setIsNetworkOnline(false);

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
      };
    }
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (typeof window !== "undefined") {
      if (nextDark) {
        document.documentElement.classList.add("dark");
        localStorage.setItem("satyascan_theme", "dark");
      } else {
        document.documentElement.classList.remove("dark");
        localStorage.setItem("satyascan_theme", "light");
      }
    }
  };

  // Poll backend health status
  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      const status = await checkBackendHealth();
      if (isMounted) {
        setBackendHealth(status);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: Activity },
    { id: "screening", label: "New Screening", icon: PlusCircle, isPrimary: true },
    ...(activeCaseId ? [{ id: "result", label: `Case #${activeCaseId.replace("SAT-2026-", "")}`, icon: Search }] : []),
    { id: "watchlist", label: "Watchlist", icon: Database },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
    { id: "methodology", label: "Standards & Docs", icon: BookOpen },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/95 backdrop-blur-md transition-colors duration-200">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-3 py-2.5 sm:px-6">
        
        {/* Left: Brand & Authority */}
        <div 
          className="flex items-center space-x-3 cursor-pointer select-none" 
          onClick={() => {
            onSelectTab("dashboard");
            setIsMobileMenuOpen(false);
          }}
          title="Return to Dashboard"
        >
          <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-lg bg-teal-600/10 dark:bg-teal-500/10 border border-teal-600/30 dark:border-teal-500/30 text-teal-700 dark:text-teal-400">
            <ShieldCheck className="h-5 w-5 sm:h-6 sm:w-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-base sm:text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                SatyaScan
              </span>
              <span className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-mono">
                SIH26188
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
              Sashastra Seema Bal · Border Checkpoint Verification
            </p>
          </div>
        </div>

        {/* Center: Desktop Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 p-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            
            if (item.isPrimary) {
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
                    isActive
                      ? "bg-teal-700 dark:bg-teal-600 text-white shadow-sm"
                      : "bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 hover:bg-teal-100 dark:hover:bg-teal-900/40 border border-teal-200 dark:border-teal-800/40"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            }

            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  isActive
                    ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 shadow-sm border border-slate-200 dark:border-slate-700"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right: Active Checkpoint + Officer Identity + Health + Logout */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          
          {/* Active Checkpoint Badge */}
          {session?.checkpoint_name && (
            <div 
              className="hidden xl:flex items-center space-x-1.5 rounded-md px-2.5 py-1 text-xs border border-teal-200 dark:border-teal-800/60 bg-teal-50/70 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 shadow-sm"
              title={`Active Border Station: ${session.checkpoint_name} (${session.location || "Indo-Border"})`}
            >
              <MapPin className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400 flex-shrink-0" />
              <span className="font-mono text-[10px] font-bold bg-teal-200/50 dark:bg-teal-900/50 px-1 py-0.5 rounded">
                {session.checkpoint_id}
              </span>
              <span className="truncate max-w-[140px] font-medium text-[11px]">
                {session.checkpoint_name.replace(" Checkpoint", "").replace(" Immigration", "")}
              </span>
            </div>
          )}

          {/* Active Officer Identity */}
          {session && (
            <div 
              className="hidden sm:flex items-center space-x-1.5 rounded-md px-2 py-1 text-xs border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300"
              title={`Screening Officer: ${session.full_name} (${session.badge_number})`}
            >
              <User className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-mono text-teal-700 dark:text-teal-400 font-semibold text-[11px]">
                {session.username}
              </span>
            </div>
          )}

          {/* Connectivity Status Badge */}
          <div 
            className="flex items-center space-x-1.5 rounded-md px-2 py-1 text-xs border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900"
            title={
              backendHealth?.online
                ? !isNetworkOnline
                  ? "Local screening service active on workstation · External internet disconnected (Air-Gapped)"
                  : "Connected to local screening service · Internet connection not required for core screening"
                : "Screening service unavailable. Start the local screening backend to continue."
            }
          >
            {backendHealth?.online ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300 hidden lg:inline">
                  {!isNetworkOnline ? "Air-Gapped" : "Local Mode"}
                </span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 hidden 2xl:inline font-mono">
                  ({backendHealth.latencyMs ? `${backendHealth.latencyMs}ms` : "local"})
                </span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse"></span>
                <span className="text-[11px] font-medium text-rose-600 dark:text-rose-400">
                  Offline
                </span>
              </>
            )}
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            aria-label="Toggle theme"
          >
            {isDark ? (
              <Sun className="h-4 w-4 text-amber-400" />
            ) : (
              <Moon className="h-4 w-4 text-slate-600" />
            )}
          </button>

          {/* Logout Button */}
          {session && onLogout && (
            <button
              id="navbar-logout-button"
              onClick={onLogout}
              className="flex items-center space-x-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-2.5 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-rose-600 dark:hover:text-rose-400 hover:border-rose-300 dark:hover:border-rose-800 transition"
              title="Sign out of checkpoint session"
              aria-label="Sign out"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden md:inline">Logout</span>
            </button>
          )}

          {/* Mobile Hamburger Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="flex md:hidden h-8 w-8 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300"
            aria-label="Toggle navigation menu"
          >
            {isMobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-4 py-3 space-y-1.5 shadow-lg">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectTab(item.id);
                  setIsMobileMenuOpen(false);
                }}
                className={`w-full flex items-center space-x-2.5 rounded-lg px-3 py-2 text-xs font-medium transition ${
                  isActive
                    ? "bg-teal-50 dark:bg-slate-800 text-teal-700 dark:text-teal-400 font-semibold border border-teal-200 dark:border-slate-700"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
          {session && (
            <div className="pt-2.5 border-t border-slate-100 dark:border-slate-900 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
              <div className="flex flex-col">
                <span className="font-medium text-slate-700 dark:text-slate-300">
                  Officer: <strong className="font-mono text-teal-600">{session.username}</strong>
                </span>
                <span className="font-mono text-[10px] text-slate-500">
                  {session.checkpoint_id ? `[${session.checkpoint_id}] ${session.checkpoint_name || ""}` : "Station"}
                </span>
              </div>
              {onLogout && (
                <button
                  onClick={() => {
                    setIsMobileMenuOpen(false);
                    onLogout();
                  }}
                  className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/60 font-semibold text-[11px]"
                >
                  <LogOut className="h-3 w-3" />
                  <span>Logout</span>
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </header>
  );
}
