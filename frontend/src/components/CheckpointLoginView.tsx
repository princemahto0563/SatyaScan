"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck, Lock, User, Eye, EyeOff, MapPin,
  AlertTriangle, CheckCircle2, ArrowRight, Loader2, Building2
} from "lucide-react";
import { getCheckpoints, loginCheckpoint } from "../lib/api";
import { CheckpointInfo, UserSession } from "../lib/types";

// Canonical fallback in case the backend is momentarily booting
const FALLBACK_CHECKPOINTS: CheckpointInfo[] = [
  { id: "CP-DEL-AIR", code: "CP-DEL-AIR", name: "Delhi Airport Immigration Checkpoint", location: "Delhi Airport (IGI)", username: "delhi_airport", role: "OFFICER", is_active: true },
  { id: "CP-ATTARI", code: "CP-ATTARI", name: "Attari Border Checkpoint", location: "Attari, Punjab", username: "attari_border", role: "OFFICER", is_active: true },
  { id: "CP-RAXAUL", code: "CP-RAXAUL", name: "Raxaul Border Checkpoint", location: "Raxaul, Bihar (Indo-Nepal)", username: "raxaul_border", role: "OFFICER", is_active: true },
  { id: "CP-JOGBANI", code: "CP-JOGBANI", name: "Jogbani Border Checkpoint", location: "Jogbani, Bihar (Indo-Nepal)", username: "jogbani_border", role: "OFFICER", is_active: true },
  { id: "CP-SUNAULI", code: "CP-SUNAULI", name: "Sunauli Border Checkpoint", location: "Sunauli, UP (Indo-Nepal)", username: "sunauli_border", role: "OFFICER", is_active: true },
  { id: "CP-RUPAIDIHA", code: "CP-RUPAIDIHA", name: "Rupaidiha Border Checkpoint", location: "Rupaidiha, UP (Indo-Nepal)", username: "rupaidiha_border", role: "OFFICER", is_active: true },
  { id: "CP-PANITANKI", code: "CP-PANITANKI", name: "Panitanki Border Checkpoint", location: "Panitanki, WB (Indo-Nepal)", username: "panitanki_border", role: "OFFICER", is_active: true },
  { id: "CP-PETRAPOLE", code: "CP-PETRAPOLE", name: "Petrapole Border Checkpoint", location: "Petrapole, WB (Indo-Bangladesh)", username: "petrapole_border", role: "OFFICER", is_active: true },
];

interface CheckpointLoginViewProps {
  onLoginSuccess: (session: UserSession) => void;
}

export function CheckpointLoginView({ onLoginSuccess }: CheckpointLoginViewProps) {
  const [checkpoints, setCheckpoints] = useState<CheckpointInfo[]>(FALLBACK_CHECKPOINTS);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string>("CP-DEL-AIR");
  const [username, setUsername] = useState<string>("delhi_airport");
  const [password, setPassword] = useState<string>("Demo@123");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getCheckpoints().then((cps) => {
      if (isMounted && cps && cps.length > 0) {
        setCheckpoints(cps);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSelectCheckpointChange = (cpId: string) => {
    setSelectedCheckpointId(cpId);
    setErrorMessage(null);
    const matched = checkpoints.find((c) => c.id === cpId);
    if (matched) {
      setUsername(matched.username);
      setPassword("Demo@123");
    }
  };

  const handleQuickFill = (cp: CheckpointInfo) => {
    setSelectedCheckpointId(cp.id);
    setUsername(cp.username);
    setPassword("Demo@123");
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCheckpointId || !username.trim() || !password) {
      setErrorMessage("Please select a checkpoint and provide your username and password.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    const result = await loginCheckpoint(selectedCheckpointId, username, password);
    setIsLoading(false);

    if (result.success && result.session) {
      onLoginSuccess(result.session);
    } else {
      setErrorMessage(result.error || "Authentication failed. Please verify credentials.");
    }
  };

  const selectedCheckpoint = checkpoints.find((c) => c.id === selectedCheckpointId) || checkpoints[0];

  return (
    <div className="min-h-[85vh] flex flex-col items-center justify-center px-4 py-8">
      {/* Disclaimer Banner */}
      <div className="w-full max-w-4xl mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-800 dark:text-amber-200 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
          <span>
            <strong>EVALUATION / DEMO ENVIRONMENT:</strong> Prototype system created for Smart India Hackathon (SIH26188). Not for operational deployment.
          </span>
        </div>
        <span className="font-mono text-[10px] bg-amber-200/50 dark:bg-amber-900/50 px-2 py-0.5 rounded font-semibold">
          DEMO CREDENTIALS ONLY
        </span>
      </div>

      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Login Card */}
        <div className="lg:col-span-7 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl overflow-hidden">
          {/* Header */}
          <div className="px-6 pt-6 pb-4 border-b border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="flex items-center space-x-3 mb-2">
              <div className="h-10 w-10 rounded-xl bg-teal-600/10 dark:bg-teal-500/10 border border-teal-600/30 dark:border-teal-500/30 flex items-center justify-center text-teal-700 dark:text-teal-400">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                  <span>SatyaScan Checkpoint Access</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                    SIH26188
                  </span>
                </h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Document Integrity & Identity Verification Workstation
                </p>
              </div>
            </div>
            <div className="text-[11px] text-slate-600 dark:text-slate-400 font-medium">
              Sashastra Seema Bal · Border Checkpoint Authentication
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            {errorMessage && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-300 flex items-start space-x-2">
                <AlertTriangle className="h-4 w-4 text-rose-600 dark:text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Authentication Denied:</span> {errorMessage}
                </div>
              </div>
            )}

            {/* Checkpoint Selector */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Border / Immigration Checkpoint
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Building2 className="h-4 w-4" />
                </div>
                <select
                  id="checkpoint-selector"
                  value={selectedCheckpointId}
                  onChange={(e) => handleSelectCheckpointChange(e.target.value)}
                  className="w-full pl-9 pr-8 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-teal-500 focus:outline-none transition"
                  disabled={isLoading}
                >
                  {checkpoints.map((cp) => (
                    <option key={cp.id} value={cp.id}>
                      [{cp.code}] {cp.name}
                    </option>
                  ))}
                </select>
              </div>
              {selectedCheckpoint && (
                <div className="flex items-center space-x-1.5 text-[11px] text-teal-700 dark:text-teal-400 pl-1 font-medium">
                  <MapPin className="h-3 w-3" />
                  <span>Location: {selectedCheckpoint.location}</span>
                </div>
              )}
            </div>

            {/* Username */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Checkpoint Operator Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setErrorMessage(null);
                  }}
                  placeholder="e.g. delhi_airport"
                  className="w-full pl-9 pr-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-teal-500 focus:outline-none transition"
                  disabled={isLoading}
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Operator Security Credential (Password)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setErrorMessage(null);
                  }}
                  placeholder="Enter credential"
                  className="w-full pl-9 pr-10 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-teal-500 focus:outline-none transition"
                  disabled={isLoading}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              id="login-submit-button"
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-2.5 px-4 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-md hover:shadow-lg transition duration-150 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Verifying Station Credentials...</span>
                </>
              ) : (
                <>
                  <span>Authenticate Checkpoint Workstation</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            {/* Security note */}
            <p className="text-[10px] text-slate-500 dark:text-slate-400 text-center pt-2">
              Authentication event is cryptographically linked with SHA-256 to the workstation audit ledger.
            </p>
          </form>
        </div>

        {/* Right Column: Evaluation Demo Quick-Fill Cards */}
        <div className="lg:col-span-5 space-y-3">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Evaluation Quick-Fill Checkpoints
              </h2>
              <span className="text-[10px] font-mono text-teal-700 dark:text-teal-400 font-semibold">
                Demo@123
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-3">
              Click any canonical checkpoint below to populate credentials instantly:
            </p>

            <div className="space-y-1.5 max-h-[380px] overflow-y-auto pr-1">
              {checkpoints.map((cp) => {
                const isSelected = selectedCheckpointId === cp.id;
                return (
                  <button
                    key={cp.id}
                    type="button"
                    onClick={() => handleQuickFill(cp)}
                    className={`w-full text-left p-2.5 rounded-lg border text-xs transition flex items-center justify-between ${
                      isSelected
                        ? "border-teal-600 dark:border-teal-500 bg-teal-50 dark:bg-teal-950/40 text-teal-900 dark:text-teal-200"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80"
                    }`}
                  >
                    <div>
                      <div className="font-semibold flex items-center space-x-1.5">
                        <span className="font-mono text-[10px] px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                          {cp.code}
                        </span>
                        <span className="text-[11px]">{cp.name}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 flex items-center space-x-2">
                        <span>User: <strong className="font-mono text-slate-700 dark:text-slate-300">{cp.username}</strong></span>
                        <span>·</span>
                        <span>{cp.location}</span>
                      </div>
                    </div>
                    {isSelected ? (
                      <CheckCircle2 className="h-4 w-4 text-teal-600 dark:text-teal-400 flex-shrink-0" />
                    ) : (
                      <span className="text-[10px] text-teal-600 dark:text-teal-400 font-medium opacity-0 group-hover:opacity-100">
                        Select
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* HQ Account Fallbacks */}
            <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 block mb-1.5">
                Legacy Officer / Supervisor Credentials:
              </span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedCheckpointId("CP-DEL-AIR");
                    setUsername("officer");
                    setPassword("officer123");
                    setErrorMessage(null);
                  }}
                  className="text-left p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] transition"
                >
                  <div className="font-semibold text-slate-800 dark:text-slate-200">Insp. Rajesh (Officer)</div>
                  <div className="text-slate-500 font-mono">officer / officer123</div>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedCheckpointId("CP-DEL-AIR");
                    setUsername("supervisor");
                    setPassword("super123");
                    setErrorMessage(null);
                  }}
                  className="text-left p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] transition"
                >
                  <div className="font-semibold text-slate-800 dark:text-slate-200">Asst. Cmdt. Anita</div>
                  <div className="text-slate-500 font-mono">supervisor / super123</div>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
