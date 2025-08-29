import React, { useEffect, useMemo, useState } from "react";
import { Download, Play, ShieldCheck, Settings2, MoonStar, Sun, Server, CheckCircle2, XCircle, Rocket, ChevronDown, ChevronRight, RefreshCw, X, MessageCircle, Info } from "lucide-react";
import clsx from "clsx";
import type { Provider, TestSuite, OrchestratorRequest, OrchestratorResult } from "../types";
import TestDataPanel from "../features/testdata/TestDataPanel";
import { getTestdataMeta, ApiError } from "../lib/api";
import ChatWizard from "../components/ChatWizard";
import ChatWizardV2 from "../components/ChatWizardV2";
import RequirementsMatrix from "../components/RequirementsMatrix";
import GroundTruthEvaluationPanel from "../components/GroundTruthEvaluationPanel";
import RagQualitySuite from "../components/suites/RagQualitySuite";
import RedTeamSuite from "../components/suites/RedTeamSuite";
import SafetySuite from "../components/suites/SafetySuite";
import PerformanceSuite from "../components/suites/PerformanceSuite";
import CompactGroundTruthPanel from "../components/CompactGroundTruthPanel";
import TestSuiteSelector from "../components/TestSuiteSelector";
import { computeRequirementMatrix, ProvidedIntake } from "../lib/requirementStatus";

const DEFAULT_SUITES: TestSuite[] = ["rag_reliability_robustness","red_team","safety","performance","regression","resilience","compliance_smoke","bias_smoke"];
const REQUIRED_SHEETS = ["Summary","Detailed","API_Details","Inputs_And_Expected"];

export default function App() {
  // Theme
  const [dark, setDark] = useState<boolean>(false);
  useEffect(() => {
    const root = document.documentElement;
    if (dark) root.classList.add("dark"); else root.classList.remove("dark");
  }, [dark]);

  // Back-end configuration
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [mcpServerUrl, setMcpServerUrl] = useState("");
  const [token, setToken] = useState("");
  const [targetMode, setTargetMode] = useState<"api"|"mcp"|"">("");

  // Provider & model
  const [provider, setProvider] = useState<Provider|"">("");
  const [model, setModel] = useState("");

  // Suites & thresholds
  const [suites, setSuites] = useState<TestSuite[]>([...DEFAULT_SUITES]);
  const [faithMin, setFaithMin] = useState("0.80");
  const [crecMin, setCrecMin] = useState("0.80");
  const [toxMax, setToxMax] = useState("0");

  // Volume controls
  const [qaSampleSize, setQaSampleSize] = useState<string>("");
  const [attackMutators, setAttackMutators] = useState<string>("1");
  const [perfRepeats, setPerfRepeats] = useState<string>("2");

  // Resilience options
  const [resilienceExpanded, setResilienceExpanded] = useState(false);
  const [resilienceMode, setResilienceMode] = useState<"synthetic" | "passive">("passive");
  const [resilienceSamples, setResilienceSamples] = useState<string>("10");
  const [resilienceTimeout, setResilienceTimeout] = useState<string>("20000");
  const [resilienceRetries, setResilienceRetries] = useState<string>("0");
  const [resilienceConcurrency, setResilienceConcurrency] = useState<string>("10");
  const [resilienceQueueDepth, setResilienceQueueDepth] = useState<string>("50");
  const [resilienceCircuitFails, setResilienceCircuitFails] = useState<string>("5");
  const [resilienceCircuitReset, setResilienceCircuitReset] = useState<string>("30");

  // Provider limits (for resilience testing)
  const [providerLimitsExpanded, setProviderLimitsExpanded] = useState(false);
  const [providerRPM, setProviderRPM] = useState<string>("");
  const [providerTPM, setProviderTPM] = useState<string>("");
  const [providerConcurrent, setProviderConcurrent] = useState<string>("");
  const [providerTier, setProviderTier] = useState<string>("");
  const [autoDetectLimits, setAutoDetectLimits] = useState<boolean>(true);

  // Compliance smoke options (minimal UI)
  const [complianceExpanded, setComplianceExpanded] = useState(false);
  const [compliancePiiScan, setCompliancePiiScan] = useState<boolean>(true);
  const [compliancePatternsFile, setCompliancePatternsFile] = useState<string>("./data/pii_patterns.json");

  // Bias smoke options (minimal UI)
  const [biasExpanded, setBiasExpanded] = useState(false);
  const [biasMaxPairs, setBiasMaxPairs] = useState<string>("10");
  const [biasGroups, setBiasGroups] = useState<string>("female|male;young|elderly");

  // Run status
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [run, setRun] = useState<OrchestratorResult | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  // Test data state
  const [testDataExpanded, setTestDataExpanded] = useState(false);
  const [testdataId, setTestdataId] = useState("");
  const [testdataValid, setTestdataValid] = useState<boolean | null>(null);
  const [validatingTestdata, setValidatingTestdata] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState<'classic' | 'chat'>('classic');

  // Requirements matrix state
  const [showRequirementsModal, setShowRequirementsModal] = useState(false);

  // Ground Truth evaluation state
  const [useGroundTruth, setUseGroundTruth] = useState(false);
  const [groundTruthExpanded, setGroundTruthExpanded] = useState(false);

  // Test selection state
  const [selectedTests, setSelectedTests] = useState<Record<string, string[]>>({});
  const [suiteConfigs, setSuiteConfigs] = useState<Record<string, any>>({});

  const thresholds = useMemo(() => ({
    faithfulness_min: Number(faithMin),
    context_recall_min: Number(crecMin),
    toxicity_max: Number(toxMax)
  }), [faithMin, crecMin, toxMax]);

  // Compute provided intake for requirements matrix
  const getProvidedIntake = (): ProvidedIntake => {
    const provided: ProvidedIntake = {};
    
    // In classic form, we don't have direct access to uploaded data counts
    // This would need to be integrated with actual test data state
    // For now, we'll assume no data is provided unless testdataId exists
    if (testdataId) {
      // Mock some data if testdata ID is set
      provided.passages = { count: 10 };
      provided.qaset = { count: 5 };
    }
    
    // Handle compliance PII patterns
    if (compliancePatternsFile) {
      provided.pii_patterns = { path: compliancePatternsFile };
    }
    
    // Handle bias groups
    if (biasGroups) {
      const pairs = biasGroups.split(';').length;
      provided.bias_groups = { pairs };
    }
    
    return provided;
  };

  // Compute requirements matrix for classic form
  const providedIntake = getProvidedIntake();
  const requirementRows = computeRequirementMatrix(suites, providedIntake, true); // Default to allowing defaults in classic form

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

  async function planTests() {
    try {
      const payload: OrchestratorRequest = {
        target_mode: targetMode as "api"|"mcp",
        api_base_url: targetMode === "api" ? apiBaseUrl : undefined,
        api_bearer_token: targetMode === "api" ? token : undefined,
        mcp_server_url: targetMode === "mcp" ? mcpServerUrl : undefined,
        suites,
        thresholds,
        testdata_id: testdataId.trim() || undefined,
        use_expanded: true,
        use_ragas: useGroundTruth,
        options: { 
          provider: provider || undefined,
          model: model,
          qa_sample_size: qaSampleSize ? parseInt(qaSampleSize) : undefined,
          attack_mutators: parseInt(attackMutators),
          perf_repeats: parseInt(perfRepeats),
          selected_tests: selectedTests,
          suite_configs: suiteConfigs,
          ...(suites.includes("resilience") ? (() => {
            const resilienceOptions: any = {
              mode: resilienceMode,
              samples: parseInt(resilienceSamples),
              timeout_ms: parseInt(resilienceTimeout),
              retries: parseInt(resilienceRetries),
              concurrency: parseInt(resilienceConcurrency),
              queue_depth: parseInt(resilienceQueueDepth),
              circuit: {
                fails: parseInt(resilienceCircuitFails),
                reset_s: parseInt(resilienceCircuitReset)
              }
            };
            
            if (providerRPM || providerTPM || providerConcurrent || providerTier) {
              resilienceOptions.provider_limits = {
                requests_per_minute: providerRPM ? parseInt(providerRPM) : undefined,
                tokens_per_minute: providerTPM ? parseInt(providerTPM) : undefined,
                max_concurrent: providerConcurrent ? parseInt(providerConcurrent) : undefined,
                tier: providerTier || undefined,
                auto_detect: autoDetectLimits
              };
            }
            
            return { resilience: resilienceOptions };
          })() : {}),
          ...(suites.includes("compliance_smoke") ? {
            compliance_smoke: {
              pii_patterns_file: compliancePatternsFile,
              scan_fields: compliancePiiScan ? ["answer", "final_text"] : [],
              rbac_matrix: {
                "user": ["/ask", "/orchestrator/*", "/testdata/*"],
                "admin": ["*"]
              }
            }
          } : {}),
          ...(suites.includes("bias_smoke") ? {
            bias_smoke: {
              groups: biasGroups.split(';').map(pair => pair.split('|').map(s => s.trim())).filter(pair => pair.length === 2),
              max_pairs: parseInt(biasMaxPairs),
              parity_metric: "refusal_rate" as const,
              parity_threshold: 0.25
            }
          } : {}),
          // RAG Reliability & Robustness configuration
          ...(suiteConfigs['rag_reliability_robustness'] ? {
            rag_reliability_robustness: suiteConfigs['rag_reliability_robustness']
          } : {}),
          // Handle legacy rag_quality alias with deprecation warning
          ...(suites.includes('rag_quality' as TestSuite) ? (() => {
            console.warn('rag_quality is deprecated; use rag_reliability_robustness instead');
            return {
              rag_reliability_robustness: suiteConfigs['rag_reliability_robustness'] || {
                faithfulness_eval: { enabled: true },
                context_recall: { enabled: true },
                ground_truth_eval: { enabled: false },
                prompt_robustness: { enabled: false, prompt_source: 'built_in', include_prompts: true }
              }
            };
          })() : {})
        }
      };
      
      const res = await postJSON(`${apiBaseUrl}/orchestrator/run_tests?dry_run=true`, payload);
      
      if (!res.ok) {
        throw new Error(`Plan failed: ${res.status}`);
      }
      
      const planData = await res.json();
      console.log("Test plan:", planData);
      
      // Display plan results
      setMessage(`Plan: ${planData.total_planned || 0} tests planned across ${Object.keys(planData.sub_suites || {}).length} sub-suites`);
      
    } catch (e: any) {
      console.error("Plan error:", e);
      setMessage(`Plan failed: ${e?.message || String(e)}`);
    }
  }

  async function cancelTests() {
    console.log("🔥 CANCEL: currentRunId =", currentRunId);
    if (!currentRunId) {
      console.log("❌ CANCEL: No currentRunId!");
      return;
    }
    
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      
      console.log("📡 CANCEL: Sending request to:", `${apiBaseUrl}/orchestrator/cancel/${currentRunId}`);
      const res = await fetch(`${apiBaseUrl}/orchestrator/cancel/${currentRunId}`, {
        method: "POST",
        headers
      });
      
      if (res.ok) {
        setMessage("Test cancelled successfully");
        setBusy(false);
        setCurrentRunId(null);
      } else {
        setMessage("Failed to cancel test");
      }
    } catch (e: any) {
      console.error("Cancel error:", e);
      setMessage("Cancel failed - refreshing page...");
      setTimeout(() => window.location.reload(), 2000);
    }
  }

  async function runTests() {
    setBusy(true); setMessage(""); 
    
    // Generate run_id immediately for cancel functionality
    const tempRunId = `run_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
    setCurrentRunId(tempRunId);
    console.log("🆔 UI: Generated temp run_id for cancel:", tempRunId);
    
    try {
      const payload: OrchestratorRequest = {
        target_mode: targetMode as "api"|"mcp",
        api_base_url: targetMode === "api" ? apiBaseUrl : undefined,
        api_bearer_token: targetMode === "api" ? token : undefined,
        mcp_server_url: targetMode === "mcp" ? mcpServerUrl : undefined,
        suites,
        thresholds,
        testdata_id: testdataId.trim() || undefined,
        use_expanded: true,  // Enable expanded dataset by default
        use_ragas: useGroundTruth,  // Enable Ragas evaluation when ground truth is selected
        run_id: tempRunId,  // Send our generated run_id for cancel
        options: { 
          provider: provider || undefined,  // Send provider in options
          model: model,        // Send model in options
          qa_sample_size: qaSampleSize ? parseInt(qaSampleSize) : undefined,
          attack_mutators: parseInt(attackMutators),
          perf_repeats: parseInt(perfRepeats),
          selected_tests: selectedTests, // Send individual test selections
          suite_configs: suiteConfigs, // Send suite-specific configurations
          ...(suites.includes("resilience") ? (() => {
            const resilienceOptions: any = {
              mode: resilienceMode,
              samples: parseInt(resilienceSamples),
              timeout_ms: parseInt(resilienceTimeout),
              retries: parseInt(resilienceRetries),
              concurrency: parseInt(resilienceConcurrency),
              queue_depth: parseInt(resilienceQueueDepth),
              circuit: {
                fails: parseInt(resilienceCircuitFails),
                reset_s: parseInt(resilienceCircuitReset)
              }
            };
            
            if (providerRPM || providerTPM || providerConcurrent || providerTier) {
              resilienceOptions.provider_limits = {
                requests_per_minute: providerRPM ? parseInt(providerRPM) : undefined,
                tokens_per_minute: providerTPM ? parseInt(providerTPM) : undefined,
                max_concurrent: providerConcurrent ? parseInt(providerConcurrent) : undefined,
                tier: providerTier || undefined,
                auto_detect: autoDetectLimits
              };
            }
            
            return { resilience: resilienceOptions };
          })() : {}),
          ...(suites.includes("compliance_smoke") ? {
            compliance_smoke: {
              pii_patterns_file: compliancePatternsFile,
              scan_fields: compliancePiiScan ? ["answer", "final_text"] : [],
              rbac_matrix: {
                "user": ["/ask", "/orchestrator/*", "/testdata/*"],
                "admin": ["*"]
              }
            }
          } : {}),
          ...(suites.includes("bias_smoke") ? {
            bias_smoke: {
              groups: biasGroups.split(';').map(pair => pair.split('|').map(s => s.trim())).filter(pair => pair.length === 2),
              max_pairs: parseInt(biasMaxPairs),
              parity_metric: "refusal_rate" as const,
              parity_threshold: 0.25
            }
          } : {}),
          // RAG Reliability & Robustness configuration
          ...(suiteConfigs['rag_reliability_robustness'] ? {
            rag_reliability_robustness: suiteConfigs['rag_reliability_robustness']
          } : {}),
          // Handle legacy rag_quality alias with deprecation warning
          ...(suites.includes('rag_quality' as TestSuite) ? (() => {
            console.warn('rag_quality is deprecated; use rag_reliability_robustness instead');
            return {
              rag_reliability_robustness: suiteConfigs['rag_reliability_robustness'] || {
                faithfulness_eval: { enabled: true },
                context_recall: { enabled: true },
                ground_truth_eval: { enabled: false },
                prompt_robustness: { enabled: false, prompt_source: 'built_in', include_prompts: true }
              }
            };
          })() : {})
        }
      };
      // Make request and extract run_id from logs/response
      const res = await postJSON(`${apiBaseUrl}/orchestrator/run_tests`, payload);
      
      // Try to extract run_id from response headers if available
      const runIdHeader = res.headers.get('X-Run-ID');
      console.log("🆔 HEADER: X-Run-ID =", runIdHeader);
      if (runIdHeader) {
        console.log("✅ HEADER: Setting currentRunId to", runIdHeader);
        setCurrentRunId(runIdHeader);
      }
      
      if (!res.ok) {
        console.log(`run_tests failed: ${res.status} ${res.statusText}`);
        throw new Error(`run_tests failed: ${res.status}`);
      }
      const data: OrchestratorResult = await res.json();
      setRun(data);
      setCurrentRunId(null); // Clear after completion
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

  const canRun = !!(targetMode === "api" ? apiBaseUrl : mcpServerUrl) && suites.length > 0 && !busy && (testdataId.trim() === '' || testdataValid !== false);

  // Estimated test count calculation based on selected individual tests
  const estimatedTests = useMemo(() => {
    let total = 0;
    
    // Count individual tests selected
    Object.entries(selectedTests).forEach(([suiteId, testIds]) => {
      if (testIds.length > 0) {
        // Base count is number of selected tests
        let suiteTotal = testIds.length;
        
        // Apply multipliers based on suite type and configuration
        if (suiteId === 'rag_quality') {
          const qaSize = qaSampleSize ? parseInt(qaSampleSize) : 8;
          suiteTotal = testIds.length * Math.max(1, Math.floor(qaSize / 3)); // Rough estimate
        } else if (suiteId === 'red_team') {
          const attacks = parseInt(attackMutators) || 1;
          suiteTotal = testIds.length * attacks * 2; // Each test type has multiple attack variations
        } else if (suiteId === 'safety') {
          const attacks = parseInt(attackMutators) || 1;
          suiteTotal = testIds.length * Math.max(3, attacks * 2); // Safety tests have multiple variations
        } else if (suiteId === 'performance') {
          const perf = parseInt(perfRepeats) || 2;
          suiteTotal = testIds.length * perf; // Performance tests repeat
        }
        
        total += suiteTotal;
      }
    });
    
    // Add legacy suite counts for suites not in selectedTests
    const legacySuites = suites.filter(suite => !selectedTests[suite]);
    legacySuites.forEach(suite => {
      const qaSize = qaSampleSize ? parseInt(qaSampleSize) : 8;
      const attacks = parseInt(attackMutators) || 1;
      const perf = parseInt(perfRepeats) || 2;
      
      if (suite === "regression") total += qaSize;
      if (suite === "resilience") total += parseInt(resilienceSamples) || 10;
      if (suite === "compliance_smoke") total += 12;
      if (suite === "bias_smoke") total += parseInt(biasMaxPairs) || 10;
    });
    
    return Math.max(1, total);
  }, [selectedTests, suites, qaSampleSize, attackMutators, perfRepeats, resilienceSamples, biasMaxPairs]);

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
      const downloadUrl = href.startsWith('/') ? `${apiBaseUrl}${href}` : href;
      
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

      {/* Tab Navigation */}
      <div className="border-b border-slate-200/80 dark:border-slate-700/70 bg-white/70 dark:bg-slate-900/60">
        <div className="mx-auto max-w-6xl px-4">
          <nav className="flex space-x-8">
            <button
              onClick={() => setActiveTab('classic')}
              className={`py-3 px-2 text-sm transition-colors ${
                activeTab === 'classic'
                  ? 'text-slate-900 dark:text-slate-100 font-medium'
                  : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
              }`}
            >
              <div className="flex items-center space-x-2">
                <Settings2 size={16} />
                <span>Classic Form</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`py-3 px-2 text-sm transition-colors ${
                activeTab === 'chat'
                  ? 'text-slate-900 dark:text-slate-100 font-medium'
                  : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
              }`}
            >
              <div className="flex items-center space-x-2">
                <MessageCircle size={16} />
                <span>Chat Wizard</span>
              </div>
            </button>

          </nav>
        </div>
      </div>

      {/* Content */}
      {activeTab === 'classic' ? (
        <div className="mx-auto max-w-6xl px-4 py-6 space-y-6">
          {/* Main Layout: Control Panel + Test Data side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Control panel - Left side */}
            <div className="card p-5">
              <div className="space-y-4">
            {/* Target Mode Selection */}
            <div>
              <label className="label">Target Mode</label>
              <select className="input max-w-48" value={targetMode} onChange={e=>setTargetMode(e.target.value as any)}>
                <option value="">Select target mode...</option>
                <option value="api">API (HTTP)</option>
                <option value="mcp">MCP</option>
              </select>
              <p className="text-xs text-slate-500 mt-1">
                {targetMode === "api" 
                  ? "Adapter selection is required; it defines the HTTP schema used to call your LLM."
                  : targetMode === "mcp"
                  ? "MCP uses a standard protocol; no adapter/model selection is needed."
                  : "Choose how you want to connect to your system for testing."
                }
              </p>
            </div>

            {/* Dynamic Connection Settings - Appears after Target Mode selection */}
            {targetMode && (
              <div className="animate-slideDown space-y-4">
                {targetMode === "api" ? (
                  <div>
                    <label className="label">Server URL</label>
                    <input 
                      className="input max-w-lg" 
                      placeholder="Enter your API endpoint (e.g., https://your-chatbot.com/api/chat)" 
                      value={apiBaseUrl} 
                      onChange={e=>{
                        const newUrl = e.target.value;
                        setApiBaseUrl(newUrl);
                        
                        // Auto-infer provider from URL if provider is not set
                        if (targetMode === "api" && !provider) {
                          import('../lib/ui').then(({ inferAdapterFromUrl }) => {
                            const inferred = inferAdapterFromUrl(newUrl);
                            if (inferred) {
                              setProvider(inferred);
                              // Auto-update model based on inferred provider
                              if (inferred === "openai") setModel("gpt-4");
                              else if (inferred === "anthropic") setModel("claude-3-5-sonnet");
                              else if (inferred === "gemini") setModel("gemini-1.5-pro");
                            }
                          });
                        }
                      }} 
                    />
                  </div>
                ) : (
                  <div>
                    <label className="label">MCP Server URL</label>
                    <input 
                      className="input max-w-lg" 
                      placeholder="Enter your MCP server endpoint (e.g., https://your-mcp-server.com:3000)" 
                      value={mcpServerUrl} 
                      onChange={e=>setMcpServerUrl(e.target.value)} 
                    />
                  </div>
                )}
                
                {/* Bearer Token */}
                <div>
                  <label className="label">Bearer Token (optional)</label>
                  <input className="input max-w-xs" type="password" placeholder="Optional: your-auth-token" value={token} onChange={e=>setToken(e.target.value)} />
                </div>
              </div>
            )}

            {/* Adapter Selection - Only for API mode */}
            {targetMode === "api" && (
              <div>
                <label className="label">Adapter (Provider Preset)</label>
                <div className="flex items-end gap-4">
                  <div>
                    <select className="input max-w-xs" value={provider} onChange={e=>{
                      const newProvider = e.target.value as Provider;
                      setProvider(newProvider);
                      
                      // Auto-update model based on provider
                      if (newProvider === "openai") {
                        setModel("gpt-4");
                      } else if (newProvider === "anthropic") {
                        setModel("claude-3-5-sonnet");
                      } else if (newProvider === "gemini") {
                        setModel("gemini-1.5-pro");
                      } else if (newProvider === "synthetic") {
                        setModel("synthetic-v1");
                      } else if (newProvider === "custom_rest") {
                        setModel("custom-model");
                      } else {
                        // If no provider selected, clear model
                        setModel("");
                      }
                    }}>
                      <option value="">Select adapter...</option>
                      <option value="openai">OpenAI (Real LLM)</option>
                      <option value="anthropic">Anthropic (Real LLM)</option>
                      <option value="gemini">Gemini (Real LLM)</option>
                      <option value="custom_rest">Custom REST (Real LLM)</option>
                      <option value="synthetic">Synthetic (Smart Test Data)</option>
                    </select>
                  </div>

                  {/* Model Field - Appears inline next to Adapter */}
                  {provider && (
                    <div className="animate-slideInRight">
                      <label className="label">Model</label>
                      <input className="input max-w-xs" placeholder="gpt-4 / your-model" value={model} onChange={e=>setModel(e.target.value)} />
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {provider 
                    ? "Select how we talk to your LLM API and specify which model your system uses"
                    : "Select how we talk to your LLM API. For MCP targets, an adapter is not required."
                  }
                </p>
              </div>
            )}

            {/* MCP Mode Info */}
            {targetMode === "mcp" && (
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mt-4">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>MCP selected:</strong> Adapter/Model not required. MCP uses a standard protocol; no adapter/model selection is needed.
                </p>
              </div>
            )}

            {/* Synthetic Provider Info */}
            {targetMode === "api" && provider === "synthetic" && (
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 mt-4">
                <p className="text-sm text-green-800 dark:text-green-200">
                  <strong>🤖 Synthetic Provider:</strong> Using intelligent test data generation. Perfect for development, testing, and CI/CD. 
                  <strong>Note:</strong> This is NOT testing a real LLM - use OpenAI/Anthropic/Gemini for actual LLM evaluation.
                </p>
              </div>
            )}

          {/* Mock Provider Info removed - Mock is now only for backend unit tests */}
              </div>
            </div>

            {/* Test Data Panel - Right side */}
            <div className="card p-5">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-lg font-semibold">Test Data</span>
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  Upload, fetch from URLs, or paste custom test data
                </span>
              </div>
              
              {/* Requirements Banner */}
              {suites.length > 0 && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Info size={16} className="text-blue-600" />
                      <span className="text-sm text-blue-800">
                        View which data are required by your selected suites.
                      </span>
                    </div>
                    <button
                      onClick={() => setShowRequirementsModal(true)}
                      className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      Show Requirements
                    </button>
                  </div>
                </div>
              )}
              <TestDataPanel token={token} />
            </div>
          </div>

          {/* Test Suite Selection - Full width below */}
          <div className="card p-5">
            <TestSuiteSelector
              onSelectionChange={(tests) => {
                setSelectedTests(tests);
                // Update suites based on selected tests
                const activeSuites = Object.keys(tests).filter(suiteId => 
                  tests[suiteId].length > 0
                ) as TestSuite[];
                setSuites(activeSuites);
              }}
              onSuiteConfigChange={(suiteId, config) => {
                setSuiteConfigs(prev => ({
                  ...prev,
                  [suiteId]: config
                }));
              }}
            />
            
            {/* Global Controls */}
            <div className="mt-6 border-t border-slate-200 dark:border-slate-700 pt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <label className="label">Test Profiles</label>
                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={()=>setProfile("smoke")}>Smoke</button>
                  <button className="btn btn-ghost btn-sm" onClick={()=>setProfile("full")}>Full</button>
                  <button className="btn btn-ghost btn-sm" onClick={()=>setProfile("red_team_heavy")}>Red Team Heavy</button>
                </div>
                <small className="text-slate-500 dark:text-slate-400 mt-1 block">
                  Quick configuration presets for common testing scenarios
                </small>
              </div>

              <div>
                <label className="label">Estimated Tests</label>
                <div className="text-2xl font-bold text-brand-600 dark:text-brand-400">
                  ~{estimatedTests} tests
                </div>
                <small className="text-slate-500 dark:text-slate-400">
                  Based on selected suites and their individual configurations
                </small>
              </div>
            </div>
            </div>
          </div>

          {/* Resilience Options Panel */}
          {suites.includes("resilience") && (
            <div className="mt-4">
              <div 
                className="flex items-center gap-2 cursor-pointer label" 
                onClick={() => setResilienceExpanded(!resilienceExpanded)}
              >
                {resilienceExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                Resilience Options
              </div>
              {resilienceExpanded && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">mode (default passive)</small>
                    <select className="input" value={resilienceMode} onChange={e=>setResilienceMode(e.target.value as "synthetic" | "passive")}>
                      <option value="passive">passive</option>
                      <option value="synthetic">synthetic</option>
                    </select>
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">samples (default 10)</small>
                    <input className="input" value={resilienceSamples} onChange={e=>setResilienceSamples(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">timeout_ms (default 20000)</small>
                    <input className="input" value={resilienceTimeout} onChange={e=>setResilienceTimeout(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">retries (default 0)</small>
                    <input className="input" value={resilienceRetries} onChange={e=>setResilienceRetries(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">concurrency (default 10)</small>
                    <input className="input" value={resilienceConcurrency} onChange={e=>setResilienceConcurrency(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">queue_depth (default 50)</small>
                    <input className="input" value={resilienceQueueDepth} onChange={e=>setResilienceQueueDepth(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">circuit.fails (default 5)</small>
                    <input className="input" value={resilienceCircuitFails} onChange={e=>setResilienceCircuitFails(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">circuit.reset_s (default 30)</small>
                    <input className="input" value={resilienceCircuitReset} onChange={e=>setResilienceCircuitReset(e.target.value)} />
                  </div>
                </div>
              )}
              
              {resilienceExpanded && (
                <div>
                  {/* Provider Limits Sub-Panel */}
                  <div className="mt-4 p-3 bg-slate-100 dark:bg-slate-700 rounded-lg">
                  <div 
                    className="flex items-center gap-2 cursor-pointer text-sm font-medium" 
                    onClick={() => setProviderLimitsExpanded(!providerLimitsExpanded)}
                  >
                    {providerLimitsExpanded ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                    Provider Rate Limits (Optional)
                  </div>
                  {providerLimitsExpanded && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
                      <div className="flex items-center gap-2">
                        <input 
                          type="checkbox" 
                          id="auto-detect"
                          checked={autoDetectLimits} 
                          onChange={e=>setAutoDetectLimits(e.target.checked)} 
                        />
                        <label htmlFor="auto-detect" className="text-xs">Auto-detect limits</label>
                      </div>
                      <div>
                        <small className="block text-slate-500 dark:text-slate-400 mb-1">Requests/min</small>
                        <input 
                          className="input text-sm" 
                          placeholder="e.g. 3500"
                          value={providerRPM} 
                          onChange={e=>setProviderRPM(e.target.value)}
                          disabled={autoDetectLimits}
                        />
                      </div>
                      <div>
                        <small className="block text-slate-500 dark:text-slate-400 mb-1">Tokens/min</small>
                        <input 
                          className="input text-sm" 
                          placeholder="e.g. 90000"
                          value={providerTPM} 
                          onChange={e=>setProviderTPM(e.target.value)}
                          disabled={autoDetectLimits}
                        />
                      </div>
                      <div>
                        <small className="block text-slate-500 dark:text-slate-400 mb-1">Max concurrent</small>
                        <input 
                          className="input text-sm" 
                          placeholder="e.g. 10"
                          value={providerConcurrent} 
                          onChange={e=>setProviderConcurrent(e.target.value)}
                          disabled={autoDetectLimits}
                        />
                      </div>
                      <div>
                        <small className="block text-slate-500 dark:text-slate-400 mb-1">Provider tier</small>
                        <input 
                          className="input text-sm" 
                          placeholder="e.g. tier-1"
                          value={providerTier} 
                          onChange={e=>setProviderTier(e.target.value)}
                          disabled={autoDetectLimits}
                        />
                      </div>
                    </div>
                  )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Compliance Smoke Options Panel */}
          {suites.includes("compliance_smoke") && (
            <div className="mt-4">
              <div 
                className="flex items-center gap-2 cursor-pointer label" 
                onClick={() => setComplianceExpanded(!complianceExpanded)}
              >
                {complianceExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                Compliance Options
              </div>
              {complianceExpanded && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">PII patterns file</small>
                    <input 
                      className="input" 
                      placeholder="./data/pii_patterns.json"
                      value={compliancePatternsFile} 
                      onChange={e=>setCompliancePatternsFile(e.target.value)} 
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input 
                      type="checkbox" 
                      id="pii-scan"
                      checked={compliancePiiScan} 
                      onChange={e=>setCompliancePiiScan(e.target.checked)} 
                    />
                    <label htmlFor="pii-scan" className="text-sm">Enable PII scanning</label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Bias Smoke Options Panel */}
          {suites.includes("bias_smoke") && (
            <div className="mt-4">
              <div 
                className="flex items-center gap-2 cursor-pointer label" 
                onClick={() => setBiasExpanded(!biasExpanded)}
              >
                {biasExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                Bias Options
              </div>
              {biasExpanded && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">max pairs (default 10)</small>
                    <input className="input" value={biasMaxPairs} onChange={e=>setBiasMaxPairs(e.target.value)} />
                  </div>
                  <div>
                    <small className="block text-slate-500 dark:text-slate-400 mb-1">groups (CSV pairs: female|male;young|elderly)</small>
                    <input 
                      className="input" 
                      placeholder="female|male;young|elderly"
                      value={biasGroups} 
                      onChange={e=>setBiasGroups(e.target.value)} 
                    />
                  </div>
                </div>
              )}
            </div>
          )}

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
            
            {/* Run controls */}
            <div className="flex flex-wrap items-center gap-3 mt-4">
              <button 
                onClick={runTests} 
                disabled={busy || !targetMode || (targetMode === "api" && (!apiBaseUrl || !provider))} 
                className="btn-primary flex items-center gap-2"
              >
                {busy ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
                {busy ? "Running..." : "Run Tests"}
              </button>
              
              <button 
                onClick={planTests} 
                disabled={busy || !targetMode || (targetMode === "api" && (!apiBaseUrl || !provider))} 
                className="btn-secondary flex items-center gap-2"
              >
                <CheckCircle2 size={16} />
                Dry Run (Plan Only)
              </button>
              
              {busy && (
                <button onClick={cancelTests} className="btn-danger flex items-center gap-2">
                  <XCircle size={16} />
                  Cancel
                </button>
              )}
            </div>
            
            {message && <span className="text-sm text-slate-600 dark:text-slate-300">{message}</span>}
            {testdataId.trim() && testdataValid === false && (
              <span className="text-sm text-red-600 dark:text-red-400">
                Invalid test data ID - please validate before running
              </span>
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
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  const base = (apiBaseUrl || "").replace(/\/+$/,"");
                  const htmlUrl = (run?.artifacts as any)?.html_path?.startsWith("/") 
                    ? base + (run?.artifacts as any).html_path
                    : (run?.artifacts as any)?.html_path || `${base}/orchestrator/report/${run!.run_id}.html`;
                  window.open(htmlUrl, "_blank");
                }}
              >
                <Download size={16}/> Open HTML Report
              </button>
              <div className="ml-auto flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <Server size={16}/> Backend: {targetMode === "api" ? apiBaseUrl : mcpServerUrl}
              </div>
            </div>
            {run?.summary && (
              <pre className="mt-4 text-sm bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl p-3 overflow-auto">{JSON.stringify(run.summary, null, 2)}</pre>
            )}
          </div>
        )}
      </div>
      ) : (
        <div className="h-[calc(100vh-200px)]">
          <ChatWizardV2 />
        </div>
      )}

      {/* Requirements Matrix Modal */}
      {showRequirementsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-900">Test Data Requirements Matrix</h2>
                <button
                  onClick={() => setShowRequirementsModal(false)}
                  className="p-2 hover:bg-gray-100 rounded-full"
                >
                  <X size={20} />
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <RequirementsMatrix 
                rows={requirementRows}
                onUploadClick={(kind) => {
                  setShowRequirementsModal(false);
                  // Focus the test data section
                  setTestDataExpanded(true);
                  // TODO: Highlight specific data kind for upload
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}