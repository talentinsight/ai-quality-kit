import React, { useState, useRef } from 'react';
import { Upload, FileText, BarChart3, CheckCircle, AlertCircle, Info } from 'lucide-react';

interface GroundTruthEvaluationPanelProps {
  apiBaseUrl: string;
  token: string;
  onEvaluationComplete?: (results: EvaluationResults) => void;
}

interface EvaluationResults {
  run_id: string;
  metrics: {
    faithfulness: number;
    answer_relevancy: number;
    context_precision: number;
    context_recall: number;
    answer_correctness: number;
    answer_similarity: number;
  };
  total_samples: number;
  passed_samples: number;
  failed_samples: number;
}

interface GroundTruthData {
  question: string;
  answer: string;
  contexts: string[];
  ground_truth: string;
}

const METRIC_DESCRIPTIONS = {
  faithfulness: "Measures how grounded the answer is in the provided context",
  answer_relevancy: "Measures how relevant the answer is to the question",
  context_precision: "Measures how relevant the retrieved contexts are to the question",
  context_recall: "Measures how much of the ground truth is captured by the retrieved contexts",
  answer_correctness: "Measures the accuracy of the answer compared to ground truth",
  answer_similarity: "Measures semantic similarity between answer and ground truth"
};

const METRIC_THRESHOLDS = {
  faithfulness: 0.75,
  answer_relevancy: 0.70,
  context_precision: 0.80,
  context_recall: 0.80,
  answer_correctness: 0.75,
  answer_similarity: 0.70
};

const GroundTruthEvaluationPanel: React.FC<GroundTruthEvaluationPanelProps> = ({
  apiBaseUrl,
  token,
  onEvaluationComplete
}) => {
  const [activeTab, setActiveTab] = useState<'upload' | 'paste'>('upload');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationResults, setEvaluationResults] = useState<EvaluationResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [groundTruthData, setGroundTruthData] = useState<GroundTruthData[]>([]);
  
  // File upload state
  const [groundTruthFile, setGroundTruthFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Text paste state
  const [groundTruthText, setGroundTruthText] = useState('');

  const clearState = () => {
    setEvaluationResults(null);
    setError(null);
    setGroundTruthFile(null);
    setGroundTruthText('');
    setGroundTruthData([]);
  };

  const parseGroundTruthData = (content: string): GroundTruthData[] => {
    const lines = content.trim().split('\n');
    const data: GroundTruthData[] = [];
    
    for (const line of lines) {
      if (line.trim()) {
        try {
          const parsed = JSON.parse(line);
          if (parsed.question && parsed.answer && parsed.contexts && parsed.ground_truth) {
            data.push({
              question: parsed.question,
              answer: parsed.answer,
              contexts: Array.isArray(parsed.contexts) ? parsed.contexts : [parsed.contexts],
              ground_truth: parsed.ground_truth
            });
          }
        } catch (e) {
          console.warn('Failed to parse line:', line);
        }
      }
    }
    
    return data;
  };

  const handleFileUpload = async () => {
    if (!groundTruthFile) {
      setError('Please select a ground truth file');
      return;
    }

    try {
      const content = await groundTruthFile.text();
      const data = parseGroundTruthData(content);
      
      if (data.length === 0) {
        setError('No valid ground truth data found in file');
        return;
      }
      
      setGroundTruthData(data);
      setError(null);
    } catch (err) {
      setError('Failed to read file: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
  };

  const handleTextPaste = () => {
    if (!groundTruthText.trim()) {
      setError('Please provide ground truth data');
      return;
    }

    try {
      const data = parseGroundTruthData(groundTruthText);
      
      if (data.length === 0) {
        setError('No valid ground truth data found');
        return;
      }
      
      setGroundTruthData(data);
      setError(null);
    } catch (err) {
      setError('Failed to parse data: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
  };

  const runEvaluation = async () => {
    if (groundTruthData.length === 0) {
      setError('Please upload ground truth data first');
      return;
    }

    setIsEvaluating(true);
    setError(null);

    try {
      // First, upload the ground truth data as a test data bundle
      const formData = new FormData();
      const qasetContent = groundTruthData.map(item => ({
        question: item.question,
        answer: item.ground_truth,
        contexts: item.contexts
      })).map(item => JSON.stringify(item)).join('\n');
      
      const qasetBlob = new Blob([qasetContent], { type: 'application/jsonl' });
      formData.append('qaset', qasetBlob, 'ground_truth_qaset.jsonl');

      const uploadResponse = await fetch(`${apiBaseUrl}/orchestrator/testdata/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!uploadResponse.ok) {
        throw new Error('Failed to upload ground truth data');
      }

      const uploadResult = await uploadResponse.json();
      const testdataId = uploadResult.testdata_id;

      // Now run the evaluation with all 8 metrics
      const evaluationRequest = {
        target_mode: "api",
        api_base_url: apiBaseUrl,
        api_bearer_token: token,
        provider: "openai",
        model: "gpt-4o-mini",
        suites: ["rag_quality"],
        testdata_id: testdataId,
        use_ragas: true,
        thresholds: METRIC_THRESHOLDS
      };

      const evaluationResponse = await fetch(`${apiBaseUrl}/orchestrator/run_tests`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(evaluationRequest)
      });

      if (!evaluationResponse.ok) {
        throw new Error('Evaluation failed');
      }

      const evaluationResult = await evaluationResponse.json();
      
      // Extract metrics from the result
      const metrics = evaluationResult.summary?.ragas || {};
      const totalSamples = groundTruthData.length;
      const passedSamples = Object.values(metrics).filter((score: any) => 
        typeof score === 'number' && score >= 0.7
      ).length;
      
      const results: EvaluationResults = {
        run_id: evaluationResult.run_id,
        metrics,
        total_samples: totalSamples,
        passed_samples: passedSamples,
        failed_samples: totalSamples - passedSamples
      };

      setEvaluationResults(results);
      
      if (onEvaluationComplete) {
        onEvaluationComplete(results);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed');
    } finally {
      setIsEvaluating(false);
    }
  };

  const getMetricColor = (score: number, threshold: number) => {
    if (score >= threshold) return 'text-green-600 dark:text-green-400';
    if (score >= threshold * 0.8) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getMetricIcon = (score: number, threshold: number) => {
    if (score >= threshold) return <CheckCircle size={16} className="text-green-600 dark:text-green-400" />;
    return <AlertCircle size={16} className="text-red-600 dark:text-red-400" />;
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 dark:border-slate-700">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
          Ground Truth Evaluation - 6 Metrics Analysis
        </h3>
        
        {/* Tab Navigation */}
        <div className="flex space-x-1 mb-4">
          {[
            { id: 'upload', label: 'Upload File', icon: Upload },
            { id: 'paste', label: 'Paste Data', icon: FileText }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id as 'upload' | 'paste')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-t-lg font-medium transition-colors ${
                activeTab === id
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border-b-2 border-blue-500'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Upload Tab */}
      {activeTab === 'upload' && (
        <div className="space-y-4">
          <div>
            <label htmlFor="ground-truth-file" className="label">
              Ground Truth Data File (JSONL)
            </label>
            <input
              id="ground-truth-file"
              ref={fileInputRef}
              type="file"
              accept=".jsonl,.json"
              onChange={(e) => setGroundTruthFile(e.target.files?.[0] || null)}
              className="input file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 dark:file:bg-slate-700 dark:file:text-slate-200"
            />
            <small className="block text-slate-500 dark:text-slate-400 mt-1">
              JSONL format: {"{"}"question": "...", "answer": "...", "contexts": [...], "ground_truth": "..."{"}"}
            </small>
          </div>
          <button
            onClick={handleFileUpload}
            disabled={!groundTruthFile}
            className="btn btn-secondary"
          >
            <Upload size={16} />
            Load Ground Truth Data
          </button>
        </div>
      )}

      {/* Paste Tab */}
      {activeTab === 'paste' && (
        <div className="space-y-4">
          <div>
            <label htmlFor="ground-truth-text" className="label">
              Ground Truth Data (JSONL)
            </label>
            <textarea
              id="ground-truth-text"
              value={groundTruthText}
              onChange={(e) => setGroundTruthText(e.target.value)}
              rows={8}
              className="input font-mono text-sm"
              placeholder={`{"question": "What is AI?", "answer": "Generated answer", "contexts": ["Context 1"], "ground_truth": "Expected answer"}
{"question": "How does ML work?", "answer": "Generated answer", "contexts": ["Context 2"], "ground_truth": "Expected answer"}`}
            />
            <small className="block text-slate-500 dark:text-slate-400 mt-1">
              One JSON object per line with question, answer, contexts, and ground_truth fields
            </small>
          </div>
          <button
            onClick={handleTextPaste}
            disabled={!groundTruthText.trim()}
            className="btn btn-secondary"
          >
            <FileText size={16} />
            Load Ground Truth Data
          </button>
        </div>
      )}

      {/* Data Summary */}
      {groundTruthData.length > 0 && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <CheckCircle size={16} className="text-green-600 dark:text-green-400" />
            <span className="font-medium text-green-800 dark:text-green-200">
              Ground Truth Data Loaded
            </span>
          </div>
          <p className="text-green-700 dark:text-green-300 mt-1">
            {groundTruthData.length} samples ready for evaluation
          </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle size={16} className="text-red-600 dark:text-red-400" />
            <span className="font-medium text-red-800 dark:text-red-200">Error</span>
          </div>
          <p className="text-red-700 dark:text-red-300 mt-1">{error}</p>
        </div>
      )}

      {/* Run Evaluation Button */}
      <div className="flex justify-center">
        <button
          onClick={runEvaluation}
          disabled={groundTruthData.length === 0 || isEvaluating}
          className="btn btn-primary px-8 py-3 text-lg"
        >
          {isEvaluating ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
              Running 6-Metric Evaluation...
            </>
          ) : (
            <>
              <BarChart3 size={20} />
              Run 6-Metric Evaluation
            </>
          )}
        </button>
      </div>

      {/* Evaluation Results */}
      {evaluationResults && (
        <div className="space-y-6">
          <div className="border-t border-slate-200 dark:border-slate-700 pt-6">
            <h4 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Evaluation Results - 6 Metrics Analysis
            </h4>
            
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {evaluationResults.total_samples}
                </div>
                <div className="text-slate-600 dark:text-slate-400">Total Samples</div>
              </div>
              <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {evaluationResults.passed_samples}
                </div>
                <div className="text-green-700 dark:text-green-300">Passed Metrics</div>
              </div>
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4">
                <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {evaluationResults.failed_samples}
                </div>
                <div className="text-red-700 dark:text-red-300">Failed Metrics</div>
              </div>
            </div>

            {/* Detailed Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(evaluationResults.metrics).map(([metric, score]) => {
                const threshold = METRIC_THRESHOLDS[metric as keyof typeof METRIC_THRESHOLDS];
                const description = METRIC_DESCRIPTIONS[metric as keyof typeof METRIC_DESCRIPTIONS];
                
                return (
                  <div key={metric} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        {getMetricIcon(score, threshold)}
                        <span className="font-medium text-slate-900 dark:text-slate-100 capitalize">
                          {metric.replace('_', ' ')}
                        </span>
                      </div>
                      <span className={`text-lg font-bold ${getMetricColor(score, threshold)}`}>
                        {(score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 mb-2">
                      <div className="flex-1 bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-300 ${
                            score >= threshold ? 'bg-green-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(score * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm text-slate-500 dark:text-slate-400">
                        Threshold: {(threshold * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-start space-x-2">
                      <Info size={14} className="text-slate-400 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        {description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Clear Results Button */}
      {(groundTruthData.length > 0 || evaluationResults) && (
        <div className="flex justify-center pt-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={clearState}
            className="btn btn-secondary"
          >
            Clear All Data
          </button>
        </div>
      )}
    </div>
  );
};

export default GroundTruthEvaluationPanel;
