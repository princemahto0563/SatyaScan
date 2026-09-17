"use client";

import React from "react";
import { Scale, Cpu, AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";

export function MethodologyView() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-5 shadow-sm">
        <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight">
          System Methodology & Standards Compliance
        </h1>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          Technical specifications, verified international standards, and clear delineation between Official Standards and Decision-Support Guidelines.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: ICAO Doc 9303 TD3 MRZ */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 space-y-3 shadow-sm">
          <div className="flex items-center space-x-2 text-teal-700 dark:text-teal-400 font-bold text-sm">
            <Scale className="h-4 w-4" />
            <span>ICAO Doc 9303 Part 4 Standard</span>
          </div>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            Machine Readable Travel Documents (MRTDs) specify 2 lines of 44 alphanumeric characters.
            SatyaScan strictly implements the 7-3-1 modulus 10 weighting check digit algorithm across:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-1 font-mono">
            <li>Document Number Check Digit (Line 2, Pos 10)</li>
            <li>Date of Birth Check Digit (Line 2, Pos 20)</li>
            <li>Date of Expiry Check Digit (Line 2, Pos 28)</li>
            <li>Composite Check Digit (Line 2, Pos 44)</li>
          </ul>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-2.5 text-[11px] text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800">
            <span className="font-semibold text-slate-800 dark:text-slate-200">Standard Scope:</span> Valid check digits verify mathematical internal consistency of the encoded fields, alerting officers to altered numbers or dates.
          </div>
        </div>

        {/* Card 2: Multi-Signal Tamper Forensics */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 space-y-3 shadow-sm">
          <div className="flex items-center space-x-2 text-cyan-700 dark:text-cyan-400 font-bold text-sm">
            <Cpu className="h-4 w-4" />
            <span>Multi-Signal Forensic Methodology</span>
          </div>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            Forensic examination synthesizes orthogonal physical and compression signals without relying on single-point heuristics:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-1">
            <li><b className="text-slate-800 dark:text-slate-200">Error Level Analysis (ELA):</b> Identifies differential compression quantization noise across spliced regions.</li>
            <li><b className="text-slate-800 dark:text-slate-200">Sensor Noise Residual:</b> Isolates high-pass PRNU sensor noise across document patches.</li>
            <li><b className="text-slate-800 dark:text-slate-200">Copy-Move (CMFD):</b> ORB descriptor matching with spatial offset clustering to flag duplicated visa stamps.</li>
            <li><b className="text-slate-800 dark:text-slate-200">Edge Boundary Analysis:</b> Gradient jump transitions around portrait perimeter boundaries.</li>
          </ul>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-2.5 text-[11px] text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800">
            <span className="font-semibold text-slate-800 dark:text-slate-200">Reporting Rule:</span> Findings report observed evidence as <i>"Compression inconsistency detected"</i> rather than making premature legal conclusions.
          </div>
        </div>

        {/* Card 3: Biometric Identity vs Appearance */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 space-y-3 shadow-sm">
          <div className="flex items-center space-x-2 text-emerald-700 dark:text-emerald-400 font-bold text-sm">
            <ShieldCheck className="h-4 w-4" />
            <span>Identity Similarity vs Appearance Variation</span>
          </div>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            SatyaScan distinguishes invariant biometric facial geometry from visible physical appearance variations:
          </p>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-3 text-xs text-slate-700 dark:text-slate-300 space-y-1 border border-slate-200 dark:border-slate-800">
            <p>• <b>Biometric Metric:</b> Cosine similarity on 512-dimensional Gabor-LBP feature descriptor vectors (Decision Threshold: 0.65).</p>
            <p>• <b>Visible Differences:</b> Facial hair growth, spectacle frames, and illumination variations are noted separately.</p>
            <p>• <b>Operational Outcome:</b> An individual who grew a beard is verified as an identity match while recording the beard as a moderate visible variation.</p>
          </div>
        </div>

        {/* Card 4: Official vs Prototype Delineation */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 space-y-3 shadow-sm">
          <div className="flex items-center space-x-2 text-amber-700 dark:text-amber-400 font-bold text-sm">
            <AlertTriangle className="h-4 w-4" />
            <span>Technical Honesty & Decision Support</span>
          </div>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            Strict adherence to security workstation operational requirements:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-1">
            <li><b className="text-slate-800 dark:text-slate-200">Decision-Support Only:</b> The workstation never autonomously issues legal admissibility verdicts; authority remains with the screening officer.</li>
            <li><b className="text-slate-800 dark:text-slate-200">Controlled Prototype Records:</b> All passport, visa, and watchlist records are synthetic demo fixtures.</li>
            <li><b className="text-slate-800 dark:text-slate-200">Verifiable Evidence:</b> Every displayed score corresponds to a genuine computer-vision or cryptographic calculation.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
