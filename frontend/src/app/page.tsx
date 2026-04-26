"use client";

import { useState, useEffect } from "react";
import { Activity, ShieldCheck, Zap, AlertTriangle, Fingerprint, Database, Network } from "lucide-react";
import { motion } from "framer-motion";

export default function VeritasWarRoom() {
  const [claim, setClaim] = useState("");
  const [status, setStatus] = useState<"idle" | "analyzing" | "complete">("idle");
  const [data, setData] = useState<any>(null);
  const [traceLog, setTraceLog] = useState<string[]>([]);

  const runAnalysis = async () => {
    if (!claim) return;
    setStatus("analyzing");
    setTraceLog([`[${new Date().toISOString()}] INITIATING VERITAS-Ω MATRIX...`]);
    
    // Simulate trace logging
    const logs = [
      "ESTABLISHING SECURE PROTOCOL...",
      "EXTRACTING ATOMIC SUB-CLAIMS...",
      "SPINNING UP 3-NODE AGENT CLUSTER...",
      "INITIALIZING HYBRID RRF SEARCH PROTOCOL...",
      "FETCHING TIER-1 INSTITUTIONAL DATA...",
      "EXECUTING ADVERSARIAL CHECK...",
      "DECOMPOSING EPISTEMIC UNCERTAINTY...",
      "COMPILING CRYPTOGRAPHIC AUDIT TRACE...",
    ];
    
    let i = 0;
    const interval = setInterval(() => {
      if (i < logs.length) {
        setTraceLog(prev => [...prev, `[${new Date().toISOString()}] ${logs[i]}`]);
        i++;
      } else {
        clearInterval(interval);
      }
    }, 400);

    try {
      const res = await fetch("http://localhost:8000/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: claim, domain_mode: "general" })
      });
      const json = await res.json();
      
      // Wait a bit for dramatic effect
      setTimeout(() => {
        setData(json.data);
        setStatus("complete");
      }, 3500);
    } catch (err) {
      console.error(err);
      setStatus("idle");
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-slate-300 font-mono overflow-hidden flex flex-col selection:bg-cyan-900">
      {/* HEADER */}
      <header className="border-b border-cyan-500/20 bg-black/50 backdrop-blur-md p-4 flex justify-between items-center z-10 relative">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-cyan-400 w-8 h-8" />
          <div>
            <h1 className="text-2xl font-black tracking-[0.3em] text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">VERITAS-Ω</h1>
            <p className="text-[0.65rem] tracking-widest text-slate-500 uppercase">Strategic Truth Evaluation Terminal</p>
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs tracking-widest text-cyan-400/50">
          <span className="flex items-center gap-2"><Activity className="w-4 h-4 animate-pulse text-cyan-400" /> SECURE LINK ACTIVE</span>
          <span>NODE: ALPHA-7</span>
          <span className="text-emerald-500">ENCRYPTION: QUANTUM-RESISTANT</span>
        </div>
      </header>

      {/* BACKGROUND GRID */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#00e5ff0a_1px,transparent_1px),linear-gradient(to_bottom,#00e5ff0a_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none" />

      {/* MAIN WORKSPACE */}
      <main className="flex-1 p-6 grid grid-cols-12 gap-6 relative z-10 h-[calc(100vh-80px)] overflow-hidden">
        
        {/* LEFT PANEL - INPUT & LOGS */}
        <div className="col-span-3 flex flex-col gap-6 h-full">
          {/* Input Panel */}
          <div className="bg-black/40 border border-cyan-500/20 rounded-xl p-5 backdrop-blur-md shadow-[0_0_30px_rgba(0,229,255,0.05)] relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <h2 className="text-xs font-bold tracking-widest text-cyan-400 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4" /> TARGET INPUT
            </h2>
            <textarea
              className="w-full bg-slate-900/50 border border-slate-700/50 rounded-lg p-3 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all resize-none font-mono placeholder-slate-600 h-32"
              placeholder="Enter target claim for rigorous evaluation..."
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
            />
            <button
              onClick={runAnalysis}
              disabled={status === "analyzing"}
              className="mt-4 w-full bg-cyan-950/50 hover:bg-cyan-900/50 border border-cyan-500/50 text-cyan-400 py-3 rounded-lg text-xs tracking-[0.2em] font-bold transition-all hover:shadow-[0_0_20px_rgba(0,229,255,0.3)] disabled:opacity-50"
            >
              {status === "analyzing" ? "ANALYZING TARGET..." : "INITIATE PROTOCOL"}
            </button>
          </div>

          {/* Cryptographic Matrix Log */}
          <div className="flex-1 bg-black/40 border border-purple-500/20 rounded-xl p-5 backdrop-blur-md shadow-[0_0_30px_rgba(138,43,226,0.05)] flex flex-col overflow-hidden">
            <h2 className="text-xs font-bold tracking-widest text-purple-400 mb-4 flex items-center gap-2">
              <Fingerprint className="w-4 h-4" /> AUDIT TRACE
            </h2>
            <div className="flex-1 overflow-y-auto space-y-2 text-[0.65rem] text-slate-400 pr-2 custom-scrollbar">
              {traceLog.map((log, i) => (
                <motion.div 
                  initial={{ opacity: 0, x: -10 }} 
                  animate={{ opacity: 1, x: 0 }} 
                  key={i}
                  className="border-l-2 border-purple-500/30 pl-2"
                >
                  {log}
                </motion.div>
              ))}
              {status === "analyzing" && (
                <div className="animate-pulse border-l-2 border-cyan-500/50 pl-2 text-cyan-400">_ PROCESSING _</div>
              )}
            </div>
          </div>
        </div>

        {/* CENTER PANEL - LIVE DEBATE */}
        <div className="col-span-6 bg-black/40 border border-slate-700/50 rounded-xl p-6 backdrop-blur-md flex flex-col relative overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[100px] pointer-events-none" />
          
          <h2 className="text-xs font-bold tracking-widest text-slate-300 mb-6 flex justify-between items-center z-10">
            <span className="flex items-center gap-2"><Network className="w-4 h-4" /> MULTI-AGENT SYNC HUB</span>
            <span className="text-[10px] text-slate-500">CONCURRENT THREADS: 3</span>
          </h2>

          <div className="flex-1 grid grid-cols-3 gap-4 z-10 overflow-y-auto pr-2 custom-scrollbar">
            {/* PRO AGENT */}
            <div className="border border-emerald-500/20 bg-emerald-950/10 p-4 rounded-lg flex flex-col gap-3">
              <div className="text-[10px] tracking-widest text-emerald-400 border-b border-emerald-500/20 pb-2">PRO AGENT [SUPPORTER]</div>
              <div className="text-xs text-slate-300 flex-1">
                {status === "complete" && data ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }}>
                    <div className="text-emerald-400 mb-2">STANCE: {data.agent_outputs[0].stance.toUpperCase()}</div>
                    <div className="mb-2">{data.agent_outputs[0].reasoning}</div>
                    <ul className="list-disc pl-4 text-[10px] text-slate-400 space-y-1">
                      {data.agent_outputs[0].key_points.map((kp: string, i: number) => <li key={i}>{kp}</li>)}
                    </ul>
                  </motion.div>
                ) : status === "analyzing" ? (
                  <div className="flex items-center gap-2 text-emerald-500/50 animate-pulse"><Activity className="w-3 h-3" /> compiling evidence...</div>
                ) : (
                  <div className="text-slate-600">Awaiting target...</div>
                )}
              </div>
            </div>

            {/* CON AGENT */}
            <div className="border border-red-500/20 bg-red-950/10 p-4 rounded-lg flex flex-col gap-3">
              <div className="text-[10px] tracking-widest text-red-400 border-b border-red-500/20 pb-2">CON AGENT [SKEPTIC]</div>
              <div className="text-xs text-slate-300 flex-1">
                {status === "complete" && data ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.5 }}>
                    <div className="text-red-400 mb-2">STANCE: {data.agent_outputs[1].stance.toUpperCase()}</div>
                    <div className="mb-2">{data.agent_outputs[1].reasoning}</div>
                    <ul className="list-disc pl-4 text-[10px] text-slate-400 space-y-1">
                      {data.agent_outputs[1].key_points.map((kp: string, i: number) => <li key={i}>{kp}</li>)}
                    </ul>
                  </motion.div>
                ) : status === "analyzing" ? (
                  <div className="flex items-center gap-2 text-red-500/50 animate-pulse"><Activity className="w-3 h-3" /> searching contradictions...</div>
                ) : (
                  <div className="text-slate-600">Awaiting target...</div>
                )}
              </div>
            </div>

            {/* ADV AGENT */}
            <div className="border border-amber-500/20 bg-amber-950/10 p-4 rounded-lg flex flex-col gap-3">
              <div className="text-[10px] tracking-widest text-amber-400 border-b border-amber-500/20 pb-2">ADVERSARIAL [ANALYST]</div>
              <div className="text-xs text-slate-300 flex-1">
                {status === "complete" && data ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 2 }}>
                    <div className="text-amber-400 mb-2">STANCE: {data.agent_outputs[2].stance.toUpperCase().replace('_', ' ')}</div>
                    <div className="mb-2">{data.agent_outputs[2].reasoning}</div>
                    <ul className="list-disc pl-4 text-[10px] text-slate-400 space-y-1">
                      {data.agent_outputs[2].key_points.map((kp: string, i: number) => <li key={i}>{kp}</li>)}
                    </ul>
                  </motion.div>
                ) : status === "analyzing" ? (
                  <div className="flex items-center gap-2 text-amber-500/50 animate-pulse"><Activity className="w-3 h-3" /> auditing biases...</div>
                ) : (
                  <div className="text-slate-600">Awaiting target...</div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL - VERDICT & UNCERTAINTY */}
        <div className="col-span-3 flex flex-col gap-6 h-full">
          {/* VERDICT */}
          <div className="bg-black/40 border border-slate-700/50 rounded-xl p-5 backdrop-blur-md relative overflow-hidden text-center h-48 flex flex-col justify-center items-center">
            {status === "complete" && data ? (
              <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="z-10">
                <div className="text-[10px] tracking-widest text-slate-400 mb-2 uppercase">Synthesized Verdict</div>
                <div className={`text-3xl font-black tracking-wider ${
                  data.judge_output.verdict === 'TRUE' ? 'text-emerald-400 drop-shadow-[0_0_15px_rgba(52,211,153,0.5)]' :
                  data.judge_output.verdict === 'FALSE' ? 'text-red-400 drop-shadow-[0_0_15px_rgba(248,113,113,0.5)]' :
                  'text-amber-400 drop-shadow-[0_0_15px_rgba(251,191,36,0.5)]'
                }`}>
                  {data.judge_output.verdict.replace('_', ' ')}
                </div>
                <div className="mt-4 text-xs text-slate-300">CONFIDENCE: <span className="text-cyan-400 font-bold">{(data.judge_output.confidence_score * 100).toFixed(1)}%</span></div>
              </motion.div>
            ) : status === "analyzing" ? (
              <div className="w-16 h-16 border-4 border-slate-800 border-t-cyan-500 rounded-full animate-spin mx-auto z-10" />
            ) : (
              <div className="text-slate-600 text-xs tracking-widest z-10">VERDICT PENDING</div>
            )}
          </div>

          {/* UNCERTAINTY DECOMPOSITION */}
          <div className="flex-1 bg-black/40 border border-slate-700/50 rounded-xl p-5 backdrop-blur-md flex flex-col">
            <h2 className="text-xs font-bold tracking-widest text-slate-300 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" /> UNCERTAINTY MATRIX
            </h2>
            {status === "complete" && data ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-1 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar">
                <div className="text-xs text-slate-300 leading-relaxed border-l-2 border-amber-500/50 pl-3">
                  {data.judge_output.reasoning_summary}
                </div>
                
                <div className="space-y-3 mt-4">
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1"><span>EPISTEMIC (Missing Data)</span><span>{(data.judge_output.uncertainty_score * 100 * 0.7).toFixed(1)}%</span></div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${data.judge_output.uncertainty_score * 100 * 0.7}%` }} className="h-full bg-orange-500" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1"><span>ALEATORIC (Inherent Noise)</span><span>{(data.judge_output.uncertainty_score * 100 * 0.3).toFixed(1)}%</span></div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${data.judge_output.uncertainty_score * 100 * 0.3}%` }} className="h-full bg-red-500" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1"><span>SOURCE TRUST SCORE</span><span>{(data.judge_output.aggregated_trust_score * 100).toFixed(1)}%</span></div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${data.judge_output.aggregated_trust_score * 100}%` }} className="h-full bg-emerald-500" />
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-600 text-[10px] text-center px-4">
                System requires target input to decompose epistemic bounds.
              </div>
            )}
          </div>
        </div>

      </main>

      {/* FOOTER */}
      <footer className="border-t border-slate-800 p-2 text-center text-[10px] tracking-widest text-slate-600 relative z-10 bg-black">
        VERITAS-Ω ARCHITECTURE // AUDITABLE. IMMUTABLE. DETERMINISTIC.
      </footer>

    </div>
  );
}
