"use client";

import React from "react";
import { BookOpen, ShieldCheck, Scale, Cpu, AlertTriangle, CheckCircle2 } from "lucide-react";

export function MethodologyView() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg backdrop-blur">
        <h1 className="text-xl font-bold text-white tracking-tight">System Methodology & Standards Compliance</h1>
        <p className="mt-1 text-xs text-slate-400">
          Technical specifications, verified standards, and clear delineation between Official Standards and Prototype Rules.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: ICAO Doc 9303 TD3 MRZ */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-teal-400 font-bold text-sm">
            <Scale className="h-4 w-4" />
            <span>ICAO Doc 9303 Part 4 Standard</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Machine Readable Travel Documents (MRTDs) specify 2 lines of 44 alphanumeric characters.
            SatyaScan strictly implements the 7-3-1 modulus 10 weighting check digit algorithm across:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 font-mono">
            <li>Document Number Check Digit (Line 2, Pos 10)</li>
            <li>Date of Birth Check Digit (Line 2, Pos 20)</li>
            <li>Date of Expiry Check Digit (Line 2, Pos 28)</li>
            <li>Composite Check Digit (Line 2, Pos 44)</li>
          </ul>
          <div className="rounded-lg bg-slate-950/60 p-2.5 text-[11px] text-slate-400 border border-slate-800">
            <span className="font-semibold text-slate-200">Limitation:</span> Valid check digits prove mathematical internal consistency, but do not by themselves establish that the document was issued by a legitimate state authority.
          </div>
        </div>

        {/* Card 2: Multi-Signal Tamper Forensics */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-cyan-400 font-bold text-sm">
            <Cpu className="h-4 w-4" />
            <span>Multi-Signal Forensic Methodology</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Forensic analysis avoids single-point failures by synthesizing five orthogonal signals:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-400 space-y-1">
            <li><b className="text-slate-200">ELA (Error Level Analysis):</b> Recompresses at 90% JPEG quality to highlight compression quantization disparities.</li>
            <li><b className="text-slate-200">Noise Residual Analysis:</b> Isolates high-pass PRNU sensor noise across grid patches.</li>
            <li><b className="text-slate-200">Copy-Move (CMFD):</b> ORB descriptor matching with spatial offset clustering to catch duplicated stamps.</li>
            <li><b className="text-slate-200">Edge Splicing Analysis:</b> Sobel boundary gradient transitions around portrait windows.</li>
          </ul>
          <div className="rounded-lg bg-slate-950/60 p-2.5 text-[11px] text-slate-400 border border-slate-800">
            <span className="font-semibold text-slate-200">Wording Rule:</span> Results are reported as <i>"Compression inconsistency detected"</i>, never <i>"Forgery confirmed"</i>.
          </div>
        </div>

        {/* Card 3: Biometric Identity vs Appearance */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-emerald-400 font-bold text-sm">
            <ShieldCheck className="h-4 w-4" />
            <span>Identity Similarity vs Appearance Variation</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            SatyaScan crucially decouples deep biometric identity embeddings from normal physical appearance variations:
          </p>
          <div className="rounded-lg bg-slate-950/60 p-3 text-xs text-slate-300 space-y-1">
            <p>• <b>Biometric Metric:</b> Cosine similarity on 512-dimensional unit-sphere vectors (Threshold: 0.65).</p>
            <p>• <b>Visible Differences:</b> Facial hair growth, spectacle frames, and illumination variations are analyzed separately.</p>
            <p>• <b>Operational Outcome:</b> An individual who grew a beard is verified as a valid identity match while noting the beard as a moderate visible variation.</p>
          </div>
        </div>

        {/* Card 4: Official vs Prototype Delineation */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-amber-400 font-bold text-sm">
            <AlertTriangle className="h-4 w-4" />
            <span>Technical Honesty & Decision Support</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Strict adherence to the SIH Problem Statement guidelines:
          </p>
          <ul className="list-disc list-inside text-xs text-slate-400 space-y-1">
            <li><b className="text-slate-200">Decision-Support Only:</b> The system never autonomously decides legal admissibility. Final authority resides with officers.</li>
            <li><b className="text-slate-200">Synthetic Prototype Data:</b> All watchlist and passport entries are strictly synthetic safe demo records.</li>
            <li><b className="text-slate-200">Zero Mock AI:</b> Every displayed score corresponds to a genuine computer-vision or cryptographic calculation.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
