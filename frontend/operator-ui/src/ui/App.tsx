import React, { useEffect, useMemo, useState } from "react";
import { Download, Play, ShieldCheck, Settings2, MoonStar, Sun, Server, CheckCircle2, XCircle, Rocket, ChevronDown, ChevronRight, RefreshCw, X, Info, Upload } from "lucide-react";
import clsx from "clsx";
import type { Provider, TestSuite, OrchestratorRequest, OrchestratorResult } from "../types";
import TestDataPanel from "../features/testdata/TestDataPanel";
import { getTestdataMeta, ApiError } from "../lib/api";
import RequirementsMatrix from "../components/RequirementsMatrix";
import GroundTruthEvaluationPanel from "../components/GroundTruthEvaluationPanel";
import RagQualitySuite from "../components/suites/RagQualitySuite";
import RedTeamSuite from "../components/suites/RedTeamSuite";
import SafetySuite from "../components/suites/SafetySuite";
import PerformanceSuite from "../components/suites/PerformanceSuite";
import CompactGroundTruthPanel from "../components/CompactGroundTruthPanel";
import TestSuiteSelector from "../components/TestSuiteSelector";
import { computeRequirementMatrix, ProvidedIntake } from "../lib/requirementStatus";

const DEFAULT_SUITES: TestSuite[] = ["rag_reliability_robustness"]; // Only RAG by default
const REQUIRED_SHEETS = ["Summary","Detailed","API_Details","Inputs_And_Expected"];

export default function App() {
  // Backend URL from environment
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

  // Theme
  const [dark, setDark] = useState<boolean>(false);
  useEffect(() => {
    const root = document.documentElement;
    if (dark) root.classList.add("dark"); else root.classList.remove("dark");
    
    // Add responsive layout styles
    const style = document.createElement('style');
    style.textContent = `
      html, body { overflow-x: clip; }
      .app-shell { max-width: 1440px; margin: 0 auto; padding: 0 16px; }
      .main-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
      @media (min-width: 1200px) { .main-grid { grid-template-columns: minmax(0,1fr) minmax(0,1fr); } }
      .panel { min-width: 0; overflow: hidden; }
      .btn { max-width: 100%; text-wrap: balance; }
      .tablist { max-width: 100%; overflow-x: auto; }
    `;
    document.head.appendChild(style);
    
    return () => {
      document.head.removeChild(style);
    };
  }, [dark]);

  // Mode-specific form state
  const [targetMode, setTargetMode] = useState<"api"|"mcp"|"">("");
  
  // API mode state
  const [apiFormState, setApiFormState] = useState({
    serverUrl: "http://localhost:8000",
    bearerToken: "",
    retrievalJsonPath: "",
    retrievalTopK: ""
  });

  // Advanced Options state (separate from API Configuration)
  const [advancedOptions, setAdvancedOptions] = useState({
    retrievedContextsJsonPath: "",
    topKReporting: "4"
  });
  
  // MCP mode state
  const [mcpFormState, setMcpFormState] = useState({
    endpoint: "",
    bearerToken: "",
    customHeaders: "",
    toolName: "",
    questionKey: "",
    systemKey: "",
    contextsKey: "",
    topKKey: "",
    shape: "messages" as "messages" | "prompt",
    staticArgs: "",
    outputType: "json" as "text" | "json",
    outputJsonPath: "",
    contextsJsonPath: "",
    requestIdJsonPath: "",
    availableTools: [] as any[],
    discovering: false
  });
  
  
  
  // Backward compatibility - derive from new state structure
  const apiBaseUrl = apiFormState.serverUrl;
  const token = apiFormState.bearerToken;
  const apiRetrievalJsonPath = apiFormState.retrievalJsonPath;
  const retrievalTopK = apiFormState.retrievalTopK;
  
  // MCP backward compatibility
  const mcpEndpoint = mcpFormState.endpoint;
  const mcpBearerToken = mcpFormState.bearerToken;
  const mcpCustomHeaders = mcpFormState.customHeaders;
  const mcpToolName = mcpFormState.toolName;
  const mcpQuestionKey = mcpFormState.questionKey;
  const mcpSystemKey = mcpFormState.systemKey;
  const mcpContextsKey = mcpFormState.contextsKey;
  const mcpTopKKey = mcpFormState.topKKey;
  const mcpShape = mcpFormState.shape;
  const mcpStaticArgs = mcpFormState.staticArgs;
  const mcpOutputType = mcpFormState.outputType;
  const mcpOutputJsonPath = mcpFormState.outputJsonPath;
  const mcpContextsJsonPath = mcpFormState.contextsJsonPath;
  const mcpRequestIdJsonPath = mcpFormState.requestIdJsonPath;
  const mcpAvailableTools = mcpFormState.availableTools;
  const mcpDiscovering = mcpFormState.discovering;
  
  // Setter functions for backward compatibility
  const setApiBaseUrl = (value: string) => setApiFormState(prev => ({ ...prev, serverUrl: value }));
  const setToken = (value: string) => setApiFormState(prev => ({ ...prev, bearerToken: value }));
  const setRetrievalJsonPath = (value: string) => setApiFormState(prev => ({ ...prev, retrievalJsonPath: value }));
  const setRetrievalTopK = (value: string) => setApiFormState(prev => ({ ...prev, retrievalTopK: value }));
  
  const setMcpEndpoint = (value: string) => setMcpFormState(prev => ({ ...prev, endpoint: value }));
  const setMcpBearerToken = (value: string) => setMcpFormState(prev => ({ ...prev, bearerToken: value }));
  const setMcpCustomHeaders = (value: string) => setMcpFormState(prev => ({ ...prev, customHeaders: value }));
  const setMcpToolName = (value: string) => setMcpFormState(prev => ({ ...prev, toolName: value }));
  const setMcpQuestionKey = (value: string) => setMcpFormState(prev => ({ ...prev, questionKey: value }));
  const setMcpSystemKey = (value: string) => setMcpFormState(prev => ({ ...prev, systemKey: value }));
  const setMcpContextsKey = (value: string) => setMcpFormState(prev => ({ ...prev, contextsKey: value }));
  const setMcpTopKKey = (value: string) => setMcpFormState(prev => ({ ...prev, topKKey: value }));
  const setMcpShape = (value: "messages" | "prompt") => setMcpFormState(prev => ({ ...prev, shape: value }));
  const setMcpStaticArgs = (value: string) => setMcpFormState(prev => ({ ...prev, staticArgs: value }));
  const setMcpOutputType = (value: "text" | "json") => setMcpFormState(prev => ({ ...prev, outputType: value }));
  const setMcpOutputJsonPath = (value: string) => setMcpFormState(prev => ({ ...prev, outputJsonPath: value }));
  const setMcpContextsJsonPath = (value: string) => setMcpFormState(prev => ({ ...prev, contextsJsonPath: value }));
  const setMcpRequestIdJsonPath = (value: string) => setMcpFormState(prev => ({ ...prev, requestIdJsonPath: value }));
  const setMcpAvailableTools = (value: any[]) => setMcpFormState(prev => ({ ...prev, availableTools: value }));
  const setMcpDiscovering = (value: boolean) => setMcpFormState(prev => ({ ...prev, discovering: value }));
  
  // LLM Model Type
  const [llmModelType, setLlmModelType] = useState<"rag"|"agent"|"tool"|"">("");
  
  // Ground Truth availability
  const [hasGroundTruth, setHasGroundTruth] = useState<boolean>(false);
  
  // Run profile
  const [runProfile, setRunProfile] = useState<"smoke" | "full">("smoke");
  
  // Compare Mode Options (shared across all modes)
  const [compareEnabled, setCompareEnabled] = useState<boolean>(false);
  const [compareAutoSelect, setCompareAutoSelect] = useState<boolean>(true);
  const [compareManualPreset, setCompareManualPreset] = useState<string>("");
  const [compareManualModel, setCompareManualModel] = useState<string>("");
  const [compareHintTier, setCompareHintTier] = useState<string>("");
  
  // Test data tracking
  const [testdataId, setTestdataId] = useState<string>("");
  const [uploadedArtifacts, setUploadedArtifacts] = useState<string[]>([]);
  
  // Sticky CTA state
  const [isDryRun, setIsDryRun] = useState<boolean>(false);

  // Provider & model (legacy)
  const [provider, setProvider] = useState<Provider|"">("");
  const [model, setModel] = useState("");
  
  // Mode switching helpers
  const handleModeSwitch = (newMode: "api"|"mcp") => {
    if (newMode === targetMode) return;
    
    // Log warning if hidden fields have values (dev guard)
    if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
      const hiddenValues = getHiddenFieldValues(targetMode);
      if (hiddenValues.length > 0) {
        console.warn('Hidden fields with values detected:', hiddenValues);
      }
    }
    
    setTargetMode(newMode);
    
    // Reset form focus and scroll to top
    setTimeout(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      const firstInput = document.querySelector(`[data-mode="${newMode}"] input:not([disabled])`);
      if (firstInput instanceof HTMLInputElement) {
        firstInput.focus();
      }
    }, 100);
  };
  
  const getHiddenFieldValues = (currentMode: string) => {
    const hiddenValues = [];
    
    if (currentMode !== 'api') {
      if (apiFormState.serverUrl) hiddenValues.push('apiFormState.serverUrl');
      if (apiFormState.bearerToken) hiddenValues.push('apiFormState.bearerToken');
    }
    
    if (currentMode !== 'mcp') {
      if (mcpFormState.endpoint) hiddenValues.push('mcpFormState.endpoint');
      if (mcpFormState.bearerToken) hiddenValues.push('mcpFormState.bearerToken');
    }
    
    
    return hiddenValues;
  };
  
  const resetModeToDefaults = (mode: "api"|"mcp") => {
    switch (mode) {
      case 'api':
        setApiFormState({
          serverUrl: "",
          bearerToken: "",
          retrievalJsonPath: "",
          retrievalTopK: ""
        });
        break;
      case 'mcp':
        setMcpFormState({
          endpoint: "",
          bearerToken: "",
          customHeaders: "",
          toolName: "",
          questionKey: "",
          systemKey: "",
          contextsKey: "",
          topKKey: "",
          shape: "messages",
          staticArgs: "",
          outputType: "json",
          outputJsonPath: "",
          contextsJsonPath: "",
          requestIdJsonPath: "",
          availableTools: [],
          discovering: false
        });
        break;
    }
  };

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
  const [testdataValid, setTestdataValid] = useState<boolean | null>(null);
  const [validatingTestdata, setValidatingTestdata] = useState(false);


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
      setRunProfile("smoke");  // Sync with RAG Advanced Options
    } else if (profile === "full") {
      setQaSampleSize("20");
      setAttackMutators("3");
      setPerfRepeats("5");
      setRunProfile("full");  // Sync with RAG Advanced Options
    } else if (profile === "red_team_heavy") {
      setQaSampleSize("5");
      setAttackMutators("5");
      setPerfRepeats("3");
      // Red Team Heavy doesn't change RAG profile, keep current
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
        mcp_server_url: targetMode === "mcp" ? mcpFormState.endpoint : undefined,
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
      
      const res = await postJSON(`${BACKEND_URL}/orchestrator/run_tests?dry_run=true`, payload);
      
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
      
      console.log("📡 CANCEL: Sending request to:", `${BACKEND_URL}/orchestrator/cancel/${currentRunId}`);
      const res = await fetch(`${BACKEND_URL}/orchestrator/cancel/${currentRunId}`, {
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
    
    // Professional refresh: Auto-validate testdata before running tests
    if (testdataId.trim()) {
      await validateTestdataId(true);
      // If validation failed and cleared testdata_id, stop execution
      if (!testdataId.trim()) {
        setBusy(false);
        return;
      }
    } 
    
    // Generate run_id immediately for cancel functionality
    const tempRunId = `run_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
    setCurrentRunId(tempRunId);
    console.log("🆔 UI: Generated temp run_id for cancel:", tempRunId);
    
    try {
      // Build payload strictly from active mode state (payload hygiene)
      const payload: OrchestratorRequest = {
        target_mode: targetMode as "api"|"mcp",
        provider: provider || "openai",  // ✅ Top-level provider
        model: model || "gpt-4",         // ✅ Top-level model
        suites,
        thresholds,
        testdata_id: testdataId.trim() || undefined,
        use_expanded: true,
        use_ragas: useGroundTruth,
        run_id: tempRunId,
        llm_option: llmModelType || "rag",
        ground_truth: hasGroundTruth ? "available" : "not_available",
        determinism: {
          temperature: 0.0,
          top_p: 1.0,
          seed: 42
        },
        profile: runProfile,
        
        // Mode-specific configuration (only include active mode fields)
        ...(targetMode === "api" && {
          api_base_url: apiFormState.serverUrl,
          api_bearer_token: apiFormState.bearerToken || undefined,
          server_url: apiFormState.serverUrl,
          retrieval: apiFormState.retrievalJsonPath ? {
            contexts_jsonpath: apiFormState.retrievalJsonPath,
            top_k: apiFormState.retrievalTopK ? parseInt(apiFormState.retrievalTopK) : undefined,
          note: "UI configured retrieval metrics"
          } : undefined
        }),
        
        ...(targetMode === "mcp" && {
          mcp_endpoint: mcpFormState.endpoint,
          // Structured target configuration
          target: mcpFormState.endpoint ? {
            mode: "mcp" as const,
            mcp: {
              endpoint: mcpFormState.endpoint,
              auth: {
                ...(mcpFormState.bearerToken ? { bearer: mcpFormState.bearerToken } : {}),
                ...(mcpFormState.customHeaders ? { headers: JSON.parse(mcpFormState.customHeaders) } : {})
              },
              tool: {
                name: mcpFormState.toolName,
                shape: mcpFormState.shape,
                arg_mapping: {
                  ...(mcpFormState.questionKey ? { question_key: mcpFormState.questionKey } : {}),
                  ...(mcpFormState.systemKey ? { system_key: mcpFormState.systemKey } : {}),
                  ...(mcpFormState.contextsKey ? { contexts_key: mcpFormState.contextsKey } : {}),
                  ...(mcpFormState.topKKey ? { topk_key: mcpFormState.topKKey } : {})
                },
                ...(mcpFormState.staticArgs ? { static_args: JSON.parse(mcpFormState.staticArgs) } : {})
              },
              extraction: {
                output_type: mcpFormState.outputType,
                ...(mcpFormState.outputType === "json" && mcpFormState.outputJsonPath ? { output_jsonpath: mcpFormState.outputJsonPath } : {}),
                ...(mcpFormState.contextsJsonPath ? { contexts_jsonpath: mcpFormState.contextsJsonPath } : {}),
                ...(mcpFormState.requestIdJsonPath ? { request_id_jsonpath: mcpFormState.requestIdJsonPath } : {})
              },
              timeouts: { connect_ms: 5000, call_ms: 30000 },
              retry: { retries: 2, backoff_ms: 250 }
            }
          } : undefined
        }),
        
        
        // Compare Mode configuration (shared across all modes)
        compare_with: compareEnabled ? {
          enabled: true,
          baseline: compareAutoSelect ? undefined : {
            preset: (compareManualPreset as Provider) || undefined,
            model: compareManualModel || undefined,
            decoding: {
              temperature: 0,
              top_p: 1,
              max_tokens: 1024
            }
          },
          auto_select: {
            enabled: compareAutoSelect,
            strategy: "same_or_near_tier" as const,
            hint_tier: (compareHintTier as "economy" | "balanced" | "premium") || undefined
          },
          carry_over: {
            use_contexts_from_primary: true,
            require_non_empty: true,
            max_context_items: 7,
            heading: "Context:",
            joiner: "\n- "
          },
          target_display_name: `${targetMode} vs baseline`
        } : undefined,
        
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
      const endpoint = isDryRun 
        ? `${BACKEND_URL}/orchestrator/run_tests?dry_run=true`
        : `${BACKEND_URL}/orchestrator/run_tests`;
      const res = await postJSON(endpoint, payload);
      
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

  // Validate testdata_id with professional expiry handling
  const validateTestdataId = async (showToast = false) => {
    if (!testdataId.trim()) {
      setTestdataValid(null);
      return;
    }

    setValidatingTestdata(true);
    try {
      const meta = await getTestdataMeta(testdataId.trim(), token);
      
      // Check if data is expired or about to expire (within 5 minutes)
      const now = new Date();
      const expiresAt = new Date(meta.expires_at);
      const timeUntilExpiry = expiresAt.getTime() - now.getTime();
      const fiveMinutes = 5 * 60 * 1000;
      
      if (timeUntilExpiry <= 0) {
        // Expired - clear cache and show message
        localStorage.removeItem('aqk:last_testdata_id');
        setTestdataId('');
        setTestdataValid(false);
        if (showToast) {
          setMessage('⚠️ Test data has expired. Please upload new data.');
        }
      } else if (timeUntilExpiry <= fiveMinutes) {
        // About to expire - warn user
        setTestdataValid(true);
        if (showToast) {
          const minutesLeft = Math.ceil(timeUntilExpiry / 60000);
          setMessage(`⏰ Test data expires in ${minutesLeft} minute(s). Consider uploading fresh data.`);
        }
      } else {
        // Valid
        setTestdataValid(true);
        if (showToast) {
          const hoursLeft = Math.floor(timeUntilExpiry / 3600000);
          const minutesLeft = Math.floor((timeUntilExpiry % 3600000) / 60000);
          setMessage(`✅ Test data is valid. Expires in ${hoursLeft}h ${minutesLeft}m.`);
        }
      }
    } catch (error) {
      console.error('Testdata validation error:', error);
      // If validation fails, assume expired and clear cache
      localStorage.removeItem('aqk:last_testdata_id');
      setTestdataId('');
      setTestdataValid(false);
      if (showToast) {
        setMessage('❌ Test data not found or expired. Please upload new data.');
      }
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

  const canRun = !!(
    targetMode === "api" 
      ? apiFormState.serverUrl 
      : targetMode === "mcp" 
        ? (mcpFormState.endpoint && mcpFormState.toolName && (mcpFormState.outputType === "text" || (mcpFormState.outputType === "json" && mcpFormState.outputJsonPath)))
        : false // no legacy fallback needed
  ) && suites.length > 0 && !busy && (testdataId.trim() === '' || testdataValid !== false);

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
      
      // Build proper URL - if href starts with /, it's relative to backend URL
      const downloadUrl = href.startsWith('/') ? `${BACKEND_URL}${href}` : href;
      
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
    <div className={clsx("min-h-full overflow-x-clip", dark ? "dark bg-slate-900" : "bg-gray-50")}>
      {/* Top bar */}
      <div className="sticky top-0 z-10 backdrop-blur border-b border-slate-200/80 dark:border-slate-700/70 bg-white/70 dark:bg-slate-900/60">
        <div className="app-shell max-w-7xl mx-auto px-4 py-3 flex items-center gap-3 min-w-0">
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
              className="py-3 px-2 text-sm transition-colors text-slate-900 dark:text-slate-100 font-medium"
            >
              <div className="flex items-center space-x-2">
                <Settings2 size={16} />
                <span>Classic Form</span>
              </div>
            </button>

          </nav>
        </div>
      </div>

      {/* Content */}
        <div className="mx-auto max-w-6xl px-4 py-6 space-y-6">
          {/* Main Layout: Control Panel + Test Data side by side */}
          <div className="main-grid grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Control panel - Left side */}
            <div className="panel card p-5 min-w-0 overflow-hidden">
              <div className="space-y-4">
            {/* Target Mode Selection */}
            <div>
              <label className="label">Target Mode</label>
              <select 
                className="input max-w-48" 
                value={targetMode} 
                onChange={e => handleModeSwitch(e.target.value as "api"|"mcp")}
              >
                <option value="">Select target mode...</option>
                <option value="api">API (HTTP)</option>
                <option value="mcp">MCP</option>
              </select>
              <p className="text-xs text-slate-500 mt-1">
                {targetMode === "api" 
                  ? "Direct HTTP API connection to your system."
                  : targetMode === "mcp"
                  ? "Model Context Protocol - structured tool-based communication."
                  : "Choose how you want to connect to your system for testing."
                }
              </p>
            </div>

            {/* LLM Options - Appears after Target Mode selection */}
            {targetMode && (
              <div className="animate-slideDown">
                <label className="label">LLM Options</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <label className="flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <input 
                      type="radio" 
                      name="llmModelType" 
                      value="rag" 
                      className="radio" 
                      checked={llmModelType === "rag"}
                      onChange={e => setLlmModelType(e.target.value as any)}
                    />
                    <div>
                      <div className="text-sm font-medium">🔍 RAG System</div>
                      <div className="text-xs text-slate-500">Retrieval-Augmented Generation</div>
                    </div>
                  </label>
                  
                  <label className="flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <input 
                      type="radio" 
                      name="llmModelType" 
                      value="agent" 
                      className="radio" 
                      checked={llmModelType === "agent"}
                      onChange={e => setLlmModelType(e.target.value as any)}
                    />
                    <div>
                      <div className="text-sm font-medium">🤖 AI Agent</div>
                      <div className="text-xs text-slate-500">Agent with Tools</div>
                    </div>
                  </label>
                  
                  <label className="flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <input 
                      type="radio" 
                      name="llmModelType" 
                      value="tool" 
                      className="radio" 
                      checked={llmModelType === "tool"}
                      onChange={e => setLlmModelType(e.target.value as any)}
                    />
                    <div>
                      <div className="text-sm font-medium">🛠️ Function/Tool</div>
                      <div className="text-xs text-slate-500">Function Testing</div>
                    </div>
                  </label>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Choose the type of LLM system you want to test for optimized evaluation options.
                </p>
              </div>
            )}

            {/* Ground Truth Data Availability - Only for RAG */}
            {llmModelType === "rag" && (
              <div className="animate-slideDown">
                <label className="label">Ground Truth Data</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <input 
                      type="radio" 
                      name="groundTruth" 
                      value="no" 
                      className="radio" 
                      checked={!hasGroundTruth}
                      onChange={() => setHasGroundTruth(false)}
                    />
                    <span className="text-sm">No Ground Truth Available</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input 
                      type="radio" 
                      name="groundTruth" 
                      value="yes" 
                      className="radio" 
                      checked={hasGroundTruth}
                      onChange={() => setHasGroundTruth(true)}
                    />
                    <span className="text-sm">Ground Truth Available</span>
                  </label>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {hasGroundTruth 
                    ? "🎯 With ground truth: 8 RAGas evaluation metrics available (3 required + 5 advanced: Faithfulness, Context Recall, Answer Relevancy, Context Precision, Answer Correctness, Answer Similarity, Context Entities Recall, Context Relevancy)"
                    : "📊 Without ground truth: 3 required RAGas metrics (Faithfulness, Context Recall, Answer Relevancy)"
                  }
                </p>
                
                {hasGroundTruth && (
                  <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                    <div className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">Ground Truth Data Required</div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">
                      📋 Use the <strong>Test Data Intake</strong> panel below to download templates and upload your QA data.
                      Templates include Excel and JSONL formats with proper column headers.
                    </div>
                  </div>
                )}
                
                {/* RAG Advanced Options */}
                <div className="mt-4 p-3 border border-slate-200 dark:border-slate-700 rounded-lg">
                  <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">Advanced Options</h4>
                  
                  <div className="space-y-3">
                    {/* Retrieved Contexts JSONPath */}
                    <div>
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                        Retrieved Contexts JSONPath (optional)
                      </label>
                      <input
                        type="text"
                        value={advancedOptions.retrievedContextsJsonPath}
                        onChange={(e) => setAdvancedOptions(prev => ({ ...prev, retrievedContextsJsonPath: e.target.value }))}
                        placeholder="e.g., $.context[*].id"
                        className="w-full px-2 py-1 text-sm border border-slate-300 dark:border-slate-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        JSONPath to extract retrieved contexts for recall@k, MRR@k, NDCG@k metrics
                      </p>
                    </div>
                    
                    {/* Top-K for reporting */}
                    <div>
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                        Top-K (for reporting)
                      </label>
                      <input
                        type="number"
                        value={advancedOptions.topKReporting}
                        onChange={(e) => setAdvancedOptions(prev => ({ ...prev, topKReporting: e.target.value }))}
                        placeholder="e.g., 5"
                        min="1"
                        max="20"
                        className="w-full px-2 py-1 text-sm border border-slate-300 dark:border-slate-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        Number of top results to consider for retrieval metrics
                      </p>
                    </div>
                    
                    {/* Run Profile */}
                    <div>
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Run Profile
                      </label>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-2">
                          <input 
                            type="radio" 
                            name="runProfile" 
                            value="smoke" 
                            className="radio" 
                            checked={runProfile === "smoke"}
                            onChange={() => {
                              setRunProfile("smoke");
                              // Sync with bottom chips
                              setQaSampleSize("2");
                              setAttackMutators("1");
                              setPerfRepeats("2");
                            }}
                          />
                          <span className="text-sm">Smoke (20 samples)</span>
                        </label>
                        <label className="flex items-center gap-2">
                          <input 
                            type="radio" 
                            name="runProfile" 
                            value="full" 
                            className="radio" 
                            checked={runProfile === "full"}
                            onChange={() => {
                              setRunProfile("full");
                              // Sync with bottom chips
                              setQaSampleSize("20");
                              setAttackMutators("3");
                              setPerfRepeats("5");
                            }}
                          />
                          <span className="text-sm">Full (all samples)</span>
                        </label>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        Smoke: Quick test with limited samples. Full: Complete evaluation with all data.
                      </p>
                    </div>
                    
                    {/* Compare Mode */}
                    <div>
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Compare Mode (optional)
                      </label>
                      
                      {/* Enable Compare Toggle */}
                      <div className="flex items-center gap-2 mb-3">
                        <input
                          type="checkbox"
                          id="compare-enabled"
                          className="checkbox"
                          checked={compareEnabled}
                          onChange={(e) => setCompareEnabled(e.target.checked)}
                        />
                        <label htmlFor="compare-enabled" className="text-sm text-slate-700 dark:text-slate-300">
                          Enable Compare with Vendor Model
                        </label>
                  </div>

                      {compareEnabled && (
                        <div className="space-y-3 pl-4 border-l-2 border-blue-200 dark:border-blue-800">
                          {/* Auto-select vs Manual */}
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <input
                                type="radio"
                                id="compare-auto"
                                name="compare-mode"
                                className="radio"
                                checked={compareAutoSelect}
                                onChange={() => setCompareAutoSelect(true)}
                              />
                              <label htmlFor="compare-auto" className="text-xs text-slate-700 dark:text-slate-300">
                                Auto-select baseline (recommended)
                              </label>
                            </div>
                            {compareAutoSelect && (
                              <div className="ml-4 text-xs text-slate-600 dark:text-slate-400">
                                <p className="mb-2">Strategy: same model if known, else near-tier suggestion.</p>
                                <div className="flex items-center gap-2">
                                  <label className="text-xs">Tier hint:</label>
                                  <select
                                    className="px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                                    value={compareHintTier}
                                    onChange={(e) => setCompareHintTier(e.target.value)}
                                  >
                                    <option value="">Auto-detect</option>
                                    <option value="economy">Economy</option>
                                    <option value="balanced">Balanced</option>
                                    <option value="premium">Premium</option>
                                  </select>
                                </div>
                              </div>
                            )}

                            <div className="flex items-center gap-2">
                              <input
                                type="radio"
                                id="compare-manual"
                                name="compare-mode"
                                className="radio"
                                checked={!compareAutoSelect}
                                onChange={() => setCompareAutoSelect(false)}
                              />
                              <label htmlFor="compare-manual" className="text-xs text-slate-700 dark:text-slate-300">
                                Manual select
                              </label>
                            </div>
                            {!compareAutoSelect && (
                              <div className="ml-4 grid grid-cols-2 gap-2">
                                <div>
                                  <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                    Vendor
                                  </label>
                                  <select
                                    className="w-full px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                                    value={compareManualPreset}
                                    onChange={(e) => setCompareManualPreset(e.target.value)}
                                  >
                                    <option value="">Select...</option>
                                    <option value="openai">OpenAI</option>
                                    <option value="anthropic">Anthropic</option>
                                    <option value="gemini">Gemini</option>
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                    Model
                                  </label>
                                  <input
                                    type="text"
                                    className="w-full px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                                    placeholder="e.g., gpt-4o-mini"
                                    value={compareManualModel}
                                    onChange={(e) => setCompareManualModel(e.target.value)}
                                  />
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Warning if no contexts JSONPath */}
                          {!advancedOptions.retrievedContextsJsonPath && (
                            <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded p-2">
                              <p className="text-xs text-yellow-800 dark:text-yellow-200">
                                <strong>Warning:</strong> No contexts JSONPath configured; comparison may skip all items.
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                      
                      <p className="text-xs text-slate-500 mt-1">
                        Compare your primary model against a vendor baseline using the same retrieved contexts.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Dynamic Connection Settings - Appears after Target Mode selection */}
            {targetMode && (
              <div className="animate-slideDown space-y-4" data-mode={targetMode}>
                {targetMode === "api" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">API Configuration</h3>
                      <button 
                        type="button" 
                        onClick={() => resetModeToDefaults('api')}
                        className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                      >
                        Reset to defaults
                      </button>
                    </div>
                    
                  <div>
                      <label className="label">Backend URL *</label>
                    <input 
                      className="input max-w-lg" 
                        placeholder="http://localhost:8000" 
                        value={apiFormState.serverUrl} 
                        onChange={e => setApiFormState(prev => ({ ...prev, serverUrl: e.target.value }))}
                      />
                    </div>
                    
                    <div>
                      <label className="label">Bearer Token</label>
                      <input 
                        className="input max-w-xs" 
                        type="password" 
                        placeholder="Optional: your-auth-token" 
                        value={apiFormState.bearerToken} 
                        onChange={e => setApiFormState(prev => ({ ...prev, bearerToken: e.target.value }))}
                      />
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="label">Retrieval JSONPath</label>
                        <input 
                          className="input" 
                          placeholder="$.contexts[*].text" 
                          value={apiFormState.retrievalJsonPath} 
                          onChange={e => setApiFormState(prev => ({ ...prev, retrievalJsonPath: e.target.value }))}
                        />
                        <p className="text-xs text-slate-500 mt-1">Path to extract retrieved contexts</p>
                      </div>
                      <div>
                        <label className="label">Top-K</label>
                        <input 
                          className="input" 
                          type="number" 
                          placeholder="5" 
                          value={apiFormState.retrievalTopK} 
                          onChange={e => setApiFormState(prev => ({ ...prev, retrievalTopK: e.target.value }))}
                        />
                        <p className="text-xs text-slate-500 mt-1">Number of contexts to retrieve</p>
                      </div>
                    </div>
                  </div>
                ) : targetMode === "mcp" ? (
                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-blue-900 dark:text-blue-100">MCP (Model Context Protocol) Configuration</h3>
                      <button 
                        type="button" 
                        onClick={() => resetModeToDefaults('mcp')}
                        className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
                      >
                        Reset to defaults
                      </button>
                    </div>
                    
                    {/* MCP Endpoint */}
                    <div className="space-y-2">
                      <label className="label">Endpoint *</label>
                      <input 
                        className="input max-w-lg" 
                        placeholder="wss://your-mcp-server.com/mcp" 
                        value={mcpFormState.endpoint} 
                        onChange={e => setMcpFormState(prev => ({ ...prev, endpoint: e.target.value }))}
                      />
                      <p className="text-xs text-slate-500">WebSocket endpoint for your MCP server</p>
                    </div>

                    {/* Authentication */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      <div>
                        <label className="label">Bearer Token</label>
                        <input 
                          className="input" 
                          type="password" 
                          placeholder="Optional bearer token" 
                          value={mcpBearerToken} 
                          onChange={e=>setMcpBearerToken(e.target.value)} 
                        />
                      </div>
                      <div>
                        <label className="label">Custom Headers JSON</label>
                        <input 
                          className="input" 
                          placeholder='{"X-Org": "your-org"}' 
                          value={mcpCustomHeaders} 
                          onChange={e=>setMcpCustomHeaders(e.target.value)} 
                        />
                        <p className="text-xs text-slate-500 mt-1">JSON object with custom headers</p>
                      </div>
                    </div>

                    {/* Tool Configuration */}
                    <div className="mt-4">
                      <div className="flex items-center gap-2 mb-2">
                        <label className="label">Tool Configuration</label>
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost"
                          disabled={!mcpEndpoint || mcpDiscovering}
                          onClick={async () => {
                            if (!mcpEndpoint) return;
                            setMcpDiscovering(true);
                            try {
                              // Call the real MCP tools discovery API
                              const response = await fetch('/mcp/tools', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                  endpoint: mcpEndpoint, 
                                  auth: mcpBearerToken ? { bearer: mcpBearerToken } : undefined 
                                })
                              });
                              
                              if (!response.ok) {
                                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                              }
                              
                              const result = await response.json();
                              if (result.error) {
                                throw new Error(result.error);
                              }
                              
                              setMcpAvailableTools(result.tools || []);
                            } catch (error) {
                              console.error('Tool discovery failed:', error);
                            } finally {
                              setMcpDiscovering(false);
                            }
                          }}
                        >
                          {mcpDiscovering ? "Discovering..." : "Discover Tools"}
                        </button>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="label">Tool Name *</label>
                          {mcpAvailableTools.length > 0 ? (
                            <select 
                              className="input" 
                              value={mcpToolName} 
                              onChange={e=>setMcpToolName(e.target.value)}
                            >
                              <option value="">Select tool...</option>
                                                              {mcpAvailableTools.map((tool: any) => (
                                  <option key={tool.name} value={tool.name}>
                                    {tool.name} - {tool.description}
                                  </option>
                                ))}
                            </select>
                          ) : (
                            <input 
                              className="input" 
                              placeholder="generate" 
                              value={mcpToolName} 
                              onChange={e=>setMcpToolName(e.target.value)} 
                            />
                          )}
                        </div>
                  <div>
                          <label className="label">Argument Shape *</label>
                          <select 
                            className="input" 
                            value={mcpShape} 
                            onChange={e=>setMcpShape(e.target.value as "messages" | "prompt")}
                          >
                            <option value="messages">Messages (structured)</option>
                            <option value="prompt">Prompt (single string)</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Argument Mapping */}
                    <div className="mt-4">
                      <label className="label">Argument Mapping</label>
                      <p className="text-xs text-slate-500 mb-2">Map message components to tool arguments (leave empty if not needed)</p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">Question Key</label>
                          <input 
                            className="input input-sm" 
                            placeholder="question | query | prompt | input"
                            value={mcpQuestionKey} 
                            onChange={e=>setMcpQuestionKey(e.target.value)} 
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">System Key</label>
                          <input 
                            className="input input-sm" 
                            placeholder="system | system_prompt"
                            value={mcpSystemKey} 
                            onChange={e=>setMcpSystemKey(e.target.value)} 
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">Contexts Key</label>
                          <input 
                            className="input input-sm" 
                            placeholder="contexts | documents | passages | evidence"
                            value={mcpContextsKey} 
                            onChange={e=>setMcpContextsKey(e.target.value)} 
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">Top-K Key</label>
                          <input 
                            className="input input-sm" 
                            placeholder="top_k | k | limit"
                            value={mcpTopKKey} 
                            onChange={e=>setMcpTopKKey(e.target.value)} 
                          />
                        </div>
                      </div>
                    </div>

                    {/* Static Arguments */}
                    <div className="mt-4">
                      <label className="label">Static Arguments</label>
                    <input 
                      className="input max-w-lg" 
                        placeholder='{"format": "text", "domain": "support"}' 
                        value={mcpStaticArgs} 
                        onChange={e=>setMcpStaticArgs(e.target.value)} 
                      />
                      <p className="text-xs text-slate-500 mt-1">JSON object with constant arguments (optional)</p>
                    </div>

                    {/* Response Extraction */}
                    <div className="mt-4">
                      <label className="label">Response Extraction</label>
                      
                      {/* Output Type Toggle */}
                      <div className="flex items-center gap-4 mb-3">
                        <label className="text-sm text-slate-600 dark:text-slate-400">Output Type:</label>
                        <div className="flex items-center gap-2">
                          <input 
                            type="radio" 
                            id="output-text" 
                            name="output-type" 
                            value="text" 
                            checked={mcpOutputType === "text"}
                            onChange={e=>setMcpOutputType(e.target.value as "text" | "json")}
                            className="radio"
                          />
                          <label htmlFor="output-text" className="text-sm">Text</label>
                        </div>
                        <div className="flex items-center gap-2">
                          <input 
                            type="radio" 
                            id="output-json" 
                            name="output-type" 
                            value="json" 
                            checked={mcpOutputType === "json"}
                            onChange={e=>setMcpOutputType(e.target.value as "text" | "json")}
                            className="radio"
                          />
                          <label htmlFor="output-json" className="text-sm">JSON</label>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {mcpOutputType === "json" && (
                          <div>
                            <label className="text-xs text-slate-600 dark:text-slate-400">Output JSONPath *</label>
                            <input 
                              className="input" 
                              placeholder="$.answer"
                              value={mcpOutputJsonPath} 
                              onChange={e=>setMcpOutputJsonPath(e.target.value)} 
                            />
                            <p className="text-xs text-slate-500 mt-1">Path to extract answer text</p>
                          </div>
                        )}
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">Contexts JSONPath</label>
                          <input 
                            className="input" 
                            placeholder="$.contexts[*].text"
                            value={mcpContextsJsonPath} 
                            onChange={e=>setMcpContextsJsonPath(e.target.value)} 
                          />
                          <p className="text-xs text-slate-500 mt-1">Path to extract retrieved contexts</p>
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 dark:text-slate-400">Request ID JSONPath</label>
                          <input 
                            className="input" 
                            placeholder="$.request_id"
                            value={mcpRequestIdJsonPath} 
                            onChange={e=>setMcpRequestIdJsonPath(e.target.value)} 
                          />
                          <p className="text-xs text-slate-500 mt-1">Path for trace follow-up</p>
                        </div>
                      </div>
                    </div>

                    {/* Validation Warnings */}
                    {mcpEndpoint && !mcpToolName && (
                      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded p-2 mt-4">
                        <p className="text-xs text-yellow-800 dark:text-yellow-200">
                          <strong>Warning:</strong> Tool name is required for MCP mode.
                        </p>
                      </div>
                    )}
                    
                    {mcpOutputType === "json" && !mcpOutputJsonPath && (
                      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded p-2 mt-4">
                        <p className="text-xs text-yellow-800 dark:text-yellow-200">
                          <strong>Warning:</strong> Output JSONPath is required when Output Type is JSON.
                        </p>
                      </div>
                    )}
                    
                    {compareEnabled && !mcpContextsJsonPath && (
                      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded p-2 mt-4">
                        <p className="text-xs text-yellow-800 dark:text-yellow-200">
                          <strong>Warning:</strong> No contexts JSONPath configured; comparison may skip all items.
                        </p>
                      </div>
                    )}
                  </div>
                ) : null}
                
                {/* Bearer Token - only show for API mode */}
                {targetMode === "api" && (
                <div>
                  <label className="label">Bearer Token (optional)</label>
                  <input className="input max-w-xs" type="password" placeholder="Optional: your-auth-token" value={token} onChange={e=>setToken(e.target.value)} />
                </div>
                )}

                {/* Test Data ID */}
                <div>
                  <label className="label">Test Data ID (Optional)</label>
                  <div className="flex flex-wrap items-center gap-3 max-w-4xl">
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
                      onClick={() => validateTestdataId(true)}
                      disabled={validatingTestdata || !testdataId.trim()}
                      title="Check if test data is still valid and show expiry info"
                    >
                      {validatingTestdata ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                          Checking...
                        </>
                      ) : (
                        <>
                          <RefreshCw size={16} />
                          Check Status
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
                            Invalid
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    When provided, overrides default passages, qaset, and attacks data sources
                  </p>
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
            <div className="panel card p-5 min-w-0 overflow-hidden">
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
              <TestDataPanel 
                token={token} 
                onTestDataUploaded={(testdataId, artifacts) => {
                  setTestdataId(testdataId);
                  setUploadedArtifacts(artifacts);
                }}
              />
            </div>
          </div>

          {/* Test Suite Selection - Full width below */}
          <div className="card p-5">
            <TestSuiteSelector
              llmModelType={llmModelType}
              hasGroundTruth={hasGroundTruth}
              onSelectionChange={(tests) => {
                setSelectedTests(tests);
                // Update suites based on selected tests
                const activeSuites = Object.keys(tests).filter(suiteId => 
                  tests[suiteId].length > 0
                ) as TestSuite[];
                setSuites(activeSuites);
              }}
              onSuitesChange={(enabledSuites) => {
                console.log("🎯 UI: Suite selection changed:", enabledSuites);
                setSuites(enabledSuites as TestSuite[]);
              }}
              onSuiteConfigChange={(suiteId, config) => {
                setSuiteConfigs(prev => ({
                  ...prev,
                  [suiteId]: config
                }));
              }}
              dataStatus={{
                passages: uploadedArtifacts.includes('passages'),
                qaSet: uploadedArtifacts.includes('qaset'),
                attacks: uploadedArtifacts.includes('attacks')
              }}
              onShowRequirements={() => {
                // Scroll to test data panel
                const testDataPanel = document.querySelector('[data-testid="test-data-panel"]');
                if (testDataPanel) {
                  testDataPanel.scrollIntoView({ behavior: 'smooth' });
                }
              }}
            />
            
            {/* Suite-Specific Options - Appear right after suite selection */}
            {/* Resilience Options */}
          {suites.includes("resilience") && (
              <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
              <div 
                  className="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-900 dark:text-slate-100" 
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

            {/* Compliance Options */}
          {suites.includes("compliance_smoke") && (
              <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
              <div 
                  className="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-900 dark:text-slate-100" 
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

            {/* Bias Options */}
          {suites.includes("bias_smoke") && (
              <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
              <div 
                  className="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-900 dark:text-slate-100" 
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

            {/* Global Controls */}
            <div className="mt-6 border-t border-slate-200 dark:border-slate-700 pt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <label className="label">Test Profiles</label>
                <div className="flex gap-2">
                  <button 
                    className={`btn btn-sm ${runProfile === "smoke" ? "btn-primary" : "btn-ghost"}`}
                    onClick={()=>setProfile("smoke")}
                  >
                    Smoke
                  </button>
                  <button 
                    className={`btn btn-sm ${runProfile === "full" ? "btn-primary" : "btn-ghost"}`}
                    onClick={()=>setProfile("full")}
                  >
                    Full
                  </button>
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

            {/* Run Tests Button */}
            <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
              <div className="flex flex-wrap items-center gap-3">
                <button 
                  onClick={runTests} 
                  disabled={busy || !targetMode || (targetMode === "api" && (!apiBaseUrl || !provider)) || suites.length === 0} 
                  className="btn-primary flex items-center gap-2"
                >
                  {busy ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
                  {busy ? "Running Tests..." : "Run Tests"}
                </button>
                
                <button 
                  onClick={planTests} 
                  disabled={busy || !targetMode || (targetMode === "api" && (!apiBaseUrl || !provider)) || suites.length === 0}
                  className="btn btn-secondary flex items-center gap-2"
                >
                  <Settings2 size={16} />
                  Dry Run (Plan Only)
                </button>
                
                {busy && (
                  <button onClick={cancelTests} className="btn-danger flex items-center gap-2">
                    <XCircle size={16} />
                    Cancel
                  </button>
                )}

                {message && <span className="text-sm text-slate-600 dark:text-slate-300">{message}</span>}
                {testdataId.trim() && testdataValid === false && (
                  <span className="text-sm text-red-600 dark:text-red-400">
                    Invalid test data ID - please validate before running
                  </span>
                )}
              </div>
            </div>
            </div>
          </div>







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
                  const htmlUrl = (run?.artifacts as any)?.html_path?.startsWith("/") 
                    ? BACKEND_URL + (run?.artifacts as any).html_path
                    : (run?.artifacts as any)?.html_path || `${BACKEND_URL}/orchestrator/report/${run!.run_id}.html`;
                  window.open(htmlUrl, "_blank");
                }}
              >
                <Download size={16}/> Open HTML Report
              </button>
              <div className="ml-auto flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <Server size={16}/> Target: {targetMode === "api" ? apiBaseUrl : mcpFormState.endpoint} | Backend: {BACKEND_URL}
              </div>
            </div>
            {run?.summary && (
              <pre className="mt-4 text-sm bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl p-3 overflow-auto">{JSON.stringify(run.summary, null, 2)}</pre>
            )}
          </div>
        )}
      </div>

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
      
      {/* Sticky Footer CTA */}
      <div>
        <div className="fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 shadow-lg z-40">
          <div className="max-w-7xl mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="dry-run-toggle"
                    checked={isDryRun}
                    onChange={(e) => setIsDryRun(e.target.checked)}
                    className="checkbox"
                  />
                  <label htmlFor="dry-run-toggle" className="text-sm font-medium">
                    Dry Run (Plan Only)
                  </label>
                </div>
                {isDryRun && (
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    Preview configuration without executing tests
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-3">
                {/* Requirements status indicator */}
                {(() => {
                  const requiredFields = [];
                  if (llmModelType === "rag") {
                    if (hasGroundTruth && !uploadedArtifacts.includes('qaset')) {
                      requiredFields.push('QA Set (for Ground Truth evaluation)');
                    }
                    // Check if any context metrics are selected that require passages
                    const hasContextMetrics = selectedTests['rag_reliability_robustness']?.some(test => 
                      test.includes('context') || test.includes('precision') || test.includes('recall')
                    );
                    if (hasContextMetrics && !uploadedArtifacts.includes('passages')) {
                      requiredFields.push('Passages (for Context metrics)');
                    }
                  }
                  
                  const isDisabled = requiredFields.length > 0 || !targetMode || !provider || !model;
                  
                  return (
                    <>
                      {requiredFields.length > 0 && (
                        <div className="text-sm text-amber-600 dark:text-amber-400">
                          Missing: {requiredFields.join(', ')}
                        </div>
                      )}
                      <button
                        onClick={runTests}
                        disabled={isDisabled || busy}
                        className={`btn ${isDisabled ? 'btn-disabled' : 'btn-primary'} px-6`}
                        title={isDisabled ? `Missing required data: ${requiredFields.join(', ')}` : ''}
                      >
                        {busy ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                            Running...
                          </>
                        ) : (
                          <>
                            {isDryRun ? '🔍 Preview Configuration' : '🚀 Run Tests'}
                          </>
                        )}
                      </button>
                    </>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Add bottom padding to prevent content from being hidden behind sticky footer */}
      <div className="h-16" />
    </div>
  );
}