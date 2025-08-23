import React, { useEffect, useMemo, useState } from "react";
import { Download, Play, ShieldCheck, Settings2, MoonStar, Sun, Server, CheckCircle2, XCircle, Rocket, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import clsx from "clsx";
import type { Provider, TestSuite, OrchestratorRequest, OrchestratorResult } from "../types";
import TestDataPanel from "../features/testdata/TestDataPanel";
import { getTestdataMeta, ApiError } from "../lib/api";

const DEFAULT_SUITES: TestSuite[] = ["rag_quality","red_team","safety","performance","regression","gibberish"];
const REQUIRED_SHEETS = ["Summary","Detailed","API_Details","Inputs_And_Expected"];

export default function App() {
  // Theme
  const [dark, setDark] = useState<boolean>(false);
  useEffect(() => {
    const root = document.documentElement;
    if (dark) root.classList.add("dark"); else root.classList.remove("dark");
  }, [dark]);

  // Back-end configuration
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [token, setToken] = useState("");
  const [targetMode, setTargetMode] = useState<"api"|"mcp">("api");

  // Provider & model
  const [provider, setProvider] = useState<Provider>("mock");
  const [model, setModel] = useState("mock-1");

  // Suites & thresholds
  const [suites, setSuites] = useState<TestSuite[]>([...DEFAULT_SUITES]);
  const [faithMin, setFaithMin] = useState("0.80");
  const [crecMin, setCrecMin] = useState("0.80");
  const [toxMax, setToxMax] = useState("0");

  // Volume controls
  const [qaSampleSize, setQaSampleSize] = useState<string>("");
  const [attackMutators, setAttackMutators] = useState<string>("1");
  const [perfRepeats, setPerfRepeats] = useState<string>("2");

  // Run status
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [run, setRun] = useState<OrchestratorResult | null>(null);

  // Test data state
  const [testDataExpanded, setTestDataExpanded] = useState(false);
  const [testdataId, setTestdataId] = useState("");
  const [testdataValid, setTestdataValid] = useState<boolean | null>(null);
  const [validatingTestdata, setValidatingTestdata] = useState(false);

  const thresholds = useMemo(() => ({
    faithfulness_min: Number(faithMin),
    context_recall_min: Number(crecMin),
    toxicity_max: Number(toxMax)
  }), [faithMin, crecMin, toxMax]);

  function toggleSuite(s: TestSuite) {
    setSuites(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }
  function selectAll() { setSuites([...DEFAULT_SUITES]); }
  function clearAll() { setSuites([]); }

  // Run profiles
  function setProfile(profile: "smoke" | "full" | "red_team_heavy") {
    if (profile === "smoke") {
      setQaSampleSize("2");
      setAttackMutators("1");
      setPerfRepeats("2");
    } else if (profile === "full") {
      setQaSampleSize("20");
      setAttackMutators("3");
      setPerfRepeats("5");
    } else if (profile === "red_team_heavy") {
      setQaSampleSize("5");
      setAttackMutators("5");
      setPerfRepeats("3");
    }
  }

  async function postJSON(url: string, body: unknown): Promise<Response> {
    const headers: Record<string, string> = { "Content-Type":"application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  }

  async function runTests() {
    setBusy(true); setMessage("");
    try {
      const payload: OrchestratorRequest = {
        target_mode: targetMode,
        api_base_url: targetMode === "api" ? baseUrl : undefined,
        api_bearer_token: targetMode === "api" ? token : undefined,
        suites,
        thresholds,
        testdata_id: testdataId.trim() || undefined,
        options: { 
          provider, 
          model,
          qa_sample_size: qaSampleSize ? parseInt(qaSampleSize) : undefined,
          attack_mutators: parseInt(attackMutators),
          perf_repeats: parseInt(perfRepeats)
        }
      };
      const res = await postJSON(`${baseUrl}/orchestrator/run_tests`, payload);
      if (!res.ok) {
        console.log(`run_tests failed: ${res.status} ${res.statusText}`);
        throw new Error(`run_tests failed: ${res.status}`);
      }
      const data: OrchestratorResult = await res.json();
      setRun(data);
      setMessage("Run completed. Download your reports below.");
    } catch (e: any) {
      console.error("Run tests error:", e);
      setMessage(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  // Load last testdata_id from localStorage
  const loadLastTestdataId = () => {
    try {
      const lastId = localStorage.getItem('aqk:last_testdata_id');
      if (lastId) {
        setTestdataId(lastId);
        setTestdataValid(null); // Reset validation state
      }
    } catch (error) {
      console.warn('Failed to load testdata_id from localStorage:', error);
    }
  };

  // Validate testdata_id
  const validateTestdataId = async () => {
    if (!testdataId.trim()) {
      setTestdataValid(null);
      return;
    }

    setValidatingTestdata(true);
    try {
      await getTestdataMeta(testdataId.trim(), token);
      setTestdataValid(true);
    } catch (error) {
      console.error('Testdata validation error:', error);
      setTestdataValid(false);
    } finally {
      setValidatingTestdata(false);
    }
  };

  // Reset testdata validation when testdata_id changes
  useEffect(() => {
    if (testdataId.trim()) {
      setTestdataValid(null);
    }
  }, [testdataId]);

  const canRun = !!baseUrl && suites.length > 0 && !busy && (testdataId.trim() === '' || testdataValid !== false);

  // Estimated test count calculation
  const estimatedTests = useMemo(() => {
    let total = 0;
    const qaSize = qaSampleSize ? parseInt(qaSampleSize) : 8; // Default sample size
    const attacks = parseInt(attackMutators) || 1;
    const perf = parseInt(perfRepeats) || 2;
    
    if (suites.includes("rag_quality")) total += qaSize;
    if (suites.includes("red_team")) total += 10 * attacks; // ~10 base attacks
    if (suites.includes("safety")) total += 5 * attacks; // ~5 safety tests
    if (suites.includes("performance")) total += perf;
    if (suites.includes("regression")) total += qaSize;
    if (suites.includes("gibberish")) total += 15; // 15 gibberish tests
    
    return total;
  }, [suites, qaSampleSize, attackMutators, perfRepeats]);

  // --- downloads: compute robust paths ---
  const hasRun = !!run?.run_id;
  const jsonPath = hasRun
    ? (run?.artifacts as any)?.json_path ?? `/orchestrator/report/${run!.run_id}.json`
    : "";
  const xlsxPath = hasRun
    ? (run?.artifacts as any)?.xlsx_path ?? `/orchestrator/report/${run!.run_id}.xlsx`
    : "";

  async function safeDownload(href: string, filename: string) {
    try {
      if (!href) throw new Error("Empty href");
      const headers: Record<string,string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      
      // Build proper URL - if href starts with /, it's relative to baseUrl
      const downloadUrl = href.startsWith('/') ? `${baseUrl}${href}` : href;
      
      const res = await fetch(downloadUrl, { headers });
      if (!res.ok) throw new Error(`download failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e:any) {
      console.error("Download error:", e);
      alert(`Download failed: ${e.message || String(e)}`);
    }
  }

  return (
    <div className={clsx("min-h-full")}>
      {/* Top bar */}
      <div className="sticky top-0 z-10 backdrop-blur border-b border-slate-200/80 dark:border-slate-700/70 bg-white/70 dark:bg-slate-900/60">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-3">
          <span className="badge"><Rocket size={16}/> LLM Configured Testing QA</span>
          <span className="text-sm text-slate-500 dark:text-slate-400">Privacy: No user data persisted by default</span>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn btn-ghost" onClick={()=>setDark(v=>!v)} aria-label="Toggle theme">
              {dark ? <Sun size={16}/> : <MoonStar size={16}/>}
              <span>{dark ? "Light" : "Dark"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-4 py-6 grid gap-6">
        {/* Control panel */}
        <div className="card p-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label">Target Mode</label>
              <select className="input" value={targetMode} onChange={e=>setTargetMode(e.target.value as any)}>
                <option value="api">API (HTTP)</option>
                <option value="mcp">MCP</option>
              </select>
            </div>

            <div>
              <label className="label">Backend Base URL</label>
              <input className="input" placeholder="http://localhost:8000" value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} />
            </div>

            <div>
              <label className="label">Bearer Token (kept in memory)</label>
              <input className="input" type="password" placeholder="SECRET_USER" value={token} onChange={e=>setToken(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="label">Provider</label>
              <select className="input" value={provider} onChange={e=>setProvider(e.target.value as Provider)}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
                <option value="custom_rest">Custom REST (local)</option>
                <option value="mock">Mock (offline)</option>
              </select>
            </div>
            <div>
              <label className="label">Model</label>
              <input className="input" placeholder="gpt-4o-mini / claude-3-5-sonnet / gemini-1.5-pro / custom / mock-1" value={model} onChange={e=>setModel(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="label">Test Suites</label>
              <div className="flex flex-wrap gap-2">
                {DEFAULT_SUITES.map(s => (
                  <label key={s} className="pill cursor-pointer select-none">
                    <input type="checkbox" className="mr-2 accent-brand-600" checked={suites.includes(s)} onChange={()=>toggleSuite(s)} />
                    {s}
                  </label>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <button className="btn btn-ghost" onClick={selectAll}>Select all</button>
                <button className="btn btn-ghost" onClick={clearAll}>Clear</button>
              </div>
            </div>

            <div>
              <label className="label">Thresholds & Policies</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">faithfulness_min</small><input className="input" value={faithMin} onChange={e=>setFaithMin(e.target.value)} /></div>
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">context_recall_min</small><input className="input" value={crecMin} onChange={e=>setCrecMin(e.target.value)} /></div>
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">toxicity_max</small><input className="input" value={toxMax} onChange={e=>setToxMax(e.target.value)} /></div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="label">Test Volume Controls</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">qa_sample_size</small><input className="input" placeholder="empty = all" value={qaSampleSize} onChange={e=>setQaSampleSize(e.target.value)} /></div>
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">attack_mutators</small><input className="input" value={attackMutators} onChange={e=>setAttackMutators(e.target.value)} /></div>
                <div><small className="block text-slate-500 dark:text-slate-400 mb-1">perf_repeats</small><input className="input" value={perfRepeats} onChange={e=>setPerfRepeats(e.target.value)} /></div>
              </div>
              <div className="mt-3 flex gap-2">
                <button className="btn btn-ghost" onClick={()=>setProfile("smoke")}>Smoke</button>
                <button className="btn btn-ghost" onClick={()=>setProfile("full")}>Full</button>
                <button className="btn btn-ghost" onClick={()=>setProfile("red_team_heavy")}>Red Team Heavy</button>
              </div>
            </div>

            <div>
              <label className="label">Estimated Tests</label>
              <div className="text-2xl font-bold text-brand-600 dark:text-brand-400">
                ~{estimatedTests} tests
              </div>
              <div className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                Based on selected suites and volume settings
              </div>
            </div>
          </div>

          {/* Test Data ID Section */}
          <div className="mt-4 p-4 border border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50 dark:bg-slate-800/50">
            <label className="label">Test Data ID (Optional)</label>
            <div className="flex flex-wrap items-center gap-3">
              <input
                className="input flex-1 min-w-0"
                placeholder="Enter testdata_id to override default data sources"
                value={testdataId}
                onChange={(e) => setTestdataId(e.target.value)}
              />
              <button
                className="btn btn-ghost"
                onClick={loadLastTestdataId}
                title="Load last used testdata_id"
              >
                Use Last
              </button>
              <button
                className="btn btn-ghost"
                onClick={validateTestdataId}
                disabled={validatingTestdata || !testdataId.trim()}
                title="Validate testdata_id"
              >
                {validatingTestdata ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                    Validating...
                  </>
                ) : (
                  <>
                    <RefreshCw size={16} />
                    Validate
                  </>
                )}
              </button>
              {testdataValid !== null && (
                <div className={clsx(
                  "flex items-center gap-1 text-sm px-2 py-1 rounded-lg",
                  testdataValid 
                    ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                    : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300"
                )}>
                  {testdataValid ? (
                    <>
                      <CheckCircle2 size={14} />
                      Valid
                    </>
                  ) : (
                    <>
                      <XCircle size={14} />
                      Invalid/Expired
                    </>
                  )}
                </div>
              )}
            </div>
            <small className="block text-slate-500 dark:text-slate-400 mt-1">
              When provided, overrides default passages, qaset, and attacks data sources
            </small>
          </div>

          <div className="mt-5 flex items-center gap-3">
            <button className="btn btn-primary" onClick={runTests} disabled={!canRun}>
              {busy ? <span className="animate-pulse">Running…</span> : <><Play size={16}/> Run tests</>}
            </button>
            {message && <span className="text-sm text-slate-600 dark:text-slate-300">{message}</span>}
            {testdataId.trim() && testdataValid === false && (
              <span className="text-sm text-red-600 dark:text-red-400">
                Invalid test data ID - please validate before running
              </span>
            )}
          </div>
        </div>

        {/* Test Data Section */}
        <div className="card p-5">
          <button
            onClick={() => setTestDataExpanded(!testDataExpanded)}
            className="w-full flex items-center justify-between p-0 bg-transparent border-0 text-left"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold">Test Data</span>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Upload, fetch from URLs, or paste custom test data
              </span>
            </div>
            {testDataExpanded ? (
              <ChevronDown size={20} className="text-slate-400" />
            ) : (
              <ChevronRight size={20} className="text-slate-400" />
            )}
          </button>
          
          {testDataExpanded && (
            <div className="mt-4">
              <TestDataPanel token={token} />
            </div>
          )}
        </div>

        {/* Summary row */}
        {run?.summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="kpi">
              <div className="title">Run</div>
              <div className="value truncate">{run.run_id}</div>
            </div>
            <div className="kpi">
              <div className="title">Artifacts</div>
              <div className="value">JSON & Excel</div>
            </div>
            <div className="kpi">
              <div className="title">Status</div>
              <div className="value flex items-center gap-2"><CheckCircle2 className="text-emerald-500" /> Ready</div>
            </div>
            <div className="kpi">
              <div className="title">Sheets</div>
              <div className="value text-sm leading-tight">{REQUIRED_SHEETS.join(", ")}</div>
            </div>
          </div>
        )}

        {/* Download card */}
        {hasRun && (
          <div className="card p-5">
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn btn-primary" onClick={()=>safeDownload(jsonPath, `${run!.run_id}.json`)}>
                <Download size={16}/> Download JSON
              </button>
              <button className="btn btn-primary" onClick={()=>safeDownload(xlsxPath, `${run!.run_id}.xlsx`)}>
                <Download size={16}/> Download Excel
              </button>
              <div className="ml-auto flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <Server size={16}/> Backend: {baseUrl}
              </div>
            </div>
            {run?.summary && (
              <pre className="mt-4 text-sm bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl p-3 overflow-auto">{JSON.stringify(run.summary, null, 2)}</pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}