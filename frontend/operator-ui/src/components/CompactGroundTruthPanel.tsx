import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Info } from 'lucide-react';

interface CompactGroundTruthPanelProps {
  apiBaseUrl: string;
  token: string;
  onDataLoaded?: (dataCount: number) => void;
}

interface GroundTruthData {
  question: string;
  answer: string;
  contexts: string[];
  ground_truth: string;
}

const CompactGroundTruthPanel: React.FC<CompactGroundTruthPanelProps> = ({
  apiBaseUrl,
  token,
  onDataLoaded
}) => {
  const [activeTab, setActiveTab] = useState<'upload' | 'paste'>('upload');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [groundTruthData, setGroundTruthData] = useState<GroundTruthData[]>([]);
  const [testdataId, setTestdataId] = useState<string>('');
  
  // File upload state
  const [groundTruthFile, setGroundTruthFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Text paste state
  const [groundTruthText, setGroundTruthText] = useState('');

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

  const uploadToBackend = async (data: GroundTruthData[]) => {
    try {
      // Create test data bundle
      const formData = new FormData();
      const qasetContent = data.map(item => ({
        question: item.question,
        answer: item.ground_truth,
        contexts: item.contexts
      })).map(item => JSON.stringify(item)).join('\n');
      
      const qasetBlob = new Blob([qasetContent], { type: 'application/jsonl' });
      formData.append('qaset', qasetBlob, 'ground_truth_qaset.jsonl');

      const response = await fetch(`${apiBaseUrl}/orchestrator/testdata/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        throw new Error('Failed to upload ground truth data');
      }

      const result = await response.json();
      setTestdataId(result.testdata_id);
      return result.testdata_id;
    } catch (err) {
      throw new Error('Failed to upload data: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
  };

  const handleFileUpload = async () => {
    if (!groundTruthFile) {
      setError('Please select a ground truth file');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const content = await groundTruthFile.text();
      const data = parseGroundTruthData(content);
      
      if (data.length === 0) {
        setError('No valid ground truth data found in file');
        return;
      }
      
      await uploadToBackend(data);
      setGroundTruthData(data);
      
      if (onDataLoaded) {
        onDataLoaded(data.length);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextPaste = async () => {
    if (!groundTruthText.trim()) {
      setError('Please provide ground truth data');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = parseGroundTruthData(groundTruthText);
      
      if (data.length === 0) {
        setError('No valid ground truth data found');
        return;
      }
      
      await uploadToBackend(data);
      setGroundTruthData(data);
      
      if (onDataLoaded) {
        onDataLoaded(data.length);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const clearData = () => {
    setGroundTruthData([]);
    setGroundTruthFile(null);
    setGroundTruthText('');
    setTestdataId('');
    setError(null);
    if (onDataLoaded) {
      onDataLoaded(0);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-sm text-slate-600 dark:text-slate-400">
        Upload ground truth data to enable comprehensive evaluation with 6 Ragas metrics:
        <span className="font-medium"> faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness, answer_similarity</span>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-1 border-b border-slate-200 dark:border-slate-700">
        {[
          { id: 'upload', label: 'Upload File', icon: Upload },
          { id: 'paste', label: 'Paste Data', icon: FileText }
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as 'upload' | 'paste')}
            className={`flex items-center space-x-2 px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === id
                ? 'text-blue-700 dark:text-blue-300 border-b-2 border-blue-500'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <Icon size={14} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Upload Tab */}
      {activeTab === 'upload' && (
        <div className="space-y-3">
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".jsonl,.json"
              onChange={(e) => setGroundTruthFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/20 dark:file:text-blue-300"
            />
            <small className="block text-slate-500 dark:text-slate-400 mt-1">
              JSONL format: {"{"}"question": "...", "answer": "...", "contexts": [...], "ground_truth": "..."{"}"}
            </small>
          </div>
          <button
            onClick={handleFileUpload}
            disabled={!groundTruthFile || isLoading}
            className="btn btn-secondary btn-sm"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                Loading...
              </>
            ) : (
              <>
                <Upload size={14} />
                Load Data
              </>
            )}
          </button>
        </div>
      )}

      {/* Paste Tab */}
      {activeTab === 'paste' && (
        <div className="space-y-3">
          <div>
            <textarea
              value={groundTruthText}
              onChange={(e) => setGroundTruthText(e.target.value)}
              rows={4}
              className="w-full text-sm font-mono border border-slate-200 dark:border-slate-700 rounded-lg p-3 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
              placeholder={`{"question": "What is AI?", "answer": "Generated answer", "contexts": ["Context 1"], "ground_truth": "Expected answer"}
{"question": "How does ML work?", "answer": "Generated answer", "contexts": ["Context 2"], "ground_truth": "Expected answer"}`}
            />
            <small className="block text-slate-500 dark:text-slate-400 mt-1">
              One JSON object per line with question, answer, contexts, and ground_truth fields
            </small>
          </div>
          <button
            onClick={handleTextPaste}
            disabled={!groundTruthText.trim() || isLoading}
            className="btn btn-secondary btn-sm"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
                Loading...
              </>
            ) : (
              <>
                <FileText size={14} />
                Load Data
              </>
            )}
          </button>
        </div>
      )}

      {/* Success State */}
      {groundTruthData.length > 0 && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle size={16} className="text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-800 dark:text-green-200">
                Ground Truth Data Loaded
              </span>
            </div>
            <button
              onClick={clearData}
              className="text-sm text-green-700 dark:text-green-300 hover:text-green-900 dark:hover:text-green-100"
            >
              Clear
            </button>
          </div>
          <p className="text-sm text-green-700 dark:text-green-300 mt-1">
            {groundTruthData.length} samples ready for 6-metric evaluation
          </p>
          {testdataId && (
            <p className="text-xs text-green-600 dark:text-green-400 mt-1 font-mono">
              Test Data ID: {testdataId}
            </p>
          )}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
          <div className="flex items-center space-x-2">
            <AlertCircle size={16} className="text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-red-800 dark:text-red-200">Error</span>
          </div>
          <p className="text-sm text-red-700 dark:text-red-300 mt-1">{error}</p>
        </div>
      )}

      {/* Info */}
      <div className="flex items-start space-x-2 text-xs text-slate-500 dark:text-slate-400">
        <Info size={12} className="mt-0.5 flex-shrink-0" />
        <p>
          When ground truth evaluation is enabled, the system will use your uploaded data to compute 
          comprehensive quality metrics. This provides deeper insights into RAG system performance 
          compared to standard evaluation.
        </p>
      </div>
    </div>
  );
};

export default CompactGroundTruthPanel;
