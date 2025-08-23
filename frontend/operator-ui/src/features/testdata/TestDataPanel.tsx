import React, { useState, useRef } from 'react';
import { Upload, Link, FileText, CheckCircle2, XCircle, Copy, RefreshCw, Clock } from 'lucide-react';
import clsx from 'clsx';
import type { ArtifactType, TestDataUploadResponse, TestDataMeta } from '../../types';
import { 
  postTestdataUpload, 
  postTestdataByUrl, 
  postTestdataPaste, 
  getTestdataMeta,
  ApiError 
} from '../../lib/api';

interface TestDataPanelProps {
  token?: string | null;
}

type TabType = 'upload' | 'url' | 'paste';

interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

export default function TestDataPanel({ token }: TestDataPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('upload');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestDataUploadResponse | null>(null);
  const [meta, setMeta] = useState<TestDataMeta | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  
  // Form state
  const [urls, setUrls] = useState<Record<ArtifactType, string>>({
    passages: '',
    qaset: '',
    attacks: '',
    schema: ''
  });
  
  const [pasteContent, setPasteContent] = useState<Record<ArtifactType, string>>({
    passages: '',
    qaset: '',
    attacks: '',
    schema: ''
  });
  
  const fileInputRefs = useRef<Record<ArtifactType, HTMLInputElement | null>>({
    passages: null,
    qaset: null,
    attacks: null,
    schema: null
  });

  // Toast management
  const addToast = (toast: Omit<ToastMessage, 'id'>) => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Persist testdata_id to localStorage
  const persistTestdataId = (testdataId: string) => {
    try {
      localStorage.setItem('aqk:last_testdata_id', testdataId);
    } catch (error) {
      console.warn('Failed to save testdata_id to localStorage:', error);
    }
  };

  // Copy to clipboard
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      addToast({ type: 'success', title: 'Copied to clipboard' });
    } catch (error) {
      addToast({ type: 'error', title: 'Failed to copy to clipboard' });
    }
  };

  // Handle upload
  const handleUpload = async () => {
    const formData = new FormData();
    let hasFiles = false;

    // Append files to form data
    Object.entries(fileInputRefs.current).forEach(([key, input]) => {
      if (input?.files?.[0]) {
        formData.append(key, input.files[0]);
        hasFiles = true;
      }
    });

    if (!hasFiles) {
      addToast({ type: 'error', title: 'No files selected', message: 'Please select at least one file to upload.' });
      return;
    }

    setLoading(true);
    try {
      const response = await postTestdataUpload(formData, token);
      setResult(response);
      setMeta(null);
      persistTestdataId(response.testdata_id);
      addToast({ type: 'success', title: 'Upload successful', message: `Created testdata_id: ${response.testdata_id}` });
    } catch (error) {
      console.error('Upload error:', error);
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          addToast({ 
            type: 'error', 
            title: 'Authentication required', 
            message: 'Please check your bearer token in the main form.' 
          });
        } else {
          addToast({ type: 'error', title: 'Upload failed', message: error.message });
        }
      } else {
        addToast({ type: 'error', title: 'Upload failed', message: String(error) });
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle URL ingestion
  const handleUrlIngestion = async () => {
    const urlEntries = Object.entries(urls).filter(([, url]) => url.trim());
    
    if (urlEntries.length === 0) {
      addToast({ type: 'error', title: 'No URLs provided', message: 'Please enter at least one URL.' });
      return;
    }

    const urlPayload: Record<ArtifactType, string> = {};
    urlEntries.forEach(([key, url]) => {
      urlPayload[key as ArtifactType] = url.trim();
    });

    setLoading(true);
    try {
      const response = await postTestdataByUrl({ urls: urlPayload }, token);
      setResult(response);
      setMeta(null);
      persistTestdataId(response.testdata_id);
      addToast({ type: 'success', title: 'URL ingestion successful', message: `Created testdata_id: ${response.testdata_id}` });
    } catch (error) {
      console.error('URL ingestion error:', error);
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          addToast({ 
            type: 'error', 
            title: 'Authentication required', 
            message: 'Please check your bearer token in the main form.' 
          });
        } else {
          addToast({ type: 'error', title: 'URL ingestion failed', message: error.message });
        }
      } else {
        addToast({ type: 'error', title: 'URL ingestion failed', message: String(error) });
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle paste ingestion
  const handlePasteIngestion = async () => {
    const contentEntries = Object.entries(pasteContent).filter(([, content]) => content.trim());
    
    if (contentEntries.length === 0) {
      addToast({ type: 'error', title: 'No content provided', message: 'Please paste at least one piece of content.' });
      return;
    }

    const pastePayload: Record<string, string> = {};
    contentEntries.forEach(([key, content]) => {
      pastePayload[key] = content.trim();
    });

    setLoading(true);
    try {
      const response = await postTestdataPaste(pastePayload, token);
      setResult(response);
      setMeta(null);
      persistTestdataId(response.testdata_id);
      addToast({ type: 'success', title: 'Paste ingestion successful', message: `Created testdata_id: ${response.testdata_id}` });
    } catch (error) {
      console.error('Paste ingestion error:', error);
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          addToast({ 
            type: 'error', 
            title: 'Authentication required', 
            message: 'Please check your bearer token in the main form.' 
          });
        } else {
          addToast({ type: 'error', title: 'Paste ingestion failed', message: error.message });
        }
      } else {
        addToast({ type: 'error', title: 'Paste ingestion failed', message: String(error) });
      }
    } finally {
      setLoading(false);
    }
  };

  // Validate testdata_id
  const validateTestdataId = async (testdataId: string) => {
    if (!testdataId.trim()) return;

    setLoading(true);
    try {
      const response = await getTestdataMeta(testdataId.trim(), token);
      setMeta(response);
      addToast({ type: 'success', title: 'Validation successful', message: 'Test data bundle is valid and accessible.' });
    } catch (error) {
      console.error('Validation error:', error);
      setMeta(null);
      if (error instanceof ApiError) {
        if (error.status === 404) {
          addToast({ type: 'error', title: 'Not found', message: 'Test data bundle not found.' });
        } else if (error.status === 410) {
          addToast({ type: 'error', title: 'Expired', message: 'Test data bundle has expired.' });
        } else if (error.status === 401 || error.status === 403) {
          addToast({ 
            type: 'error', 
            title: 'Authentication required', 
            message: 'Please check your bearer token in the main form.' 
          });
        } else {
          addToast({ type: 'error', title: 'Validation failed', message: error.message });
        }
      } else {
        addToast({ type: 'error', title: 'Validation failed', message: String(error) });
      }
    } finally {
      setLoading(false);
    }
  };

  const formatExpiryTime = (expiresAt: string) => {
    try {
      const expiry = new Date(expiresAt);
      const now = new Date();
      const diffMs = expiry.getTime() - now.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
      
      if (diffMs <= 0) return 'Expired';
      if (diffHours > 0) return `Expires in ${diffHours}h ${diffMinutes}m`;
      return `Expires in ${diffMinutes}m`;
    } catch {
      return 'Unknown expiry';
    }
  };

  return (
    <div className="card p-5">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <FileText size={20} className="text-brand-600" />
        <h2 className="text-lg font-semibold">Test Data Intake</h2>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl mb-4">
        {[
          { id: 'upload' as TabType, label: 'Upload', icon: Upload },
          { id: 'url' as TabType, label: 'URL', icon: Link },
          { id: 'paste' as TabType, label: 'Paste', icon: FileText }
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              'flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition',
              activeTab === id
                ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            )}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {/* Upload Tab */}
      {activeTab === 'upload' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {([
              { key: 'passages' as ArtifactType, label: 'Passages', accept: '.jsonl', description: 'JSONL format: {"id": "1", "text": "...", "meta": {...}}' },
              { key: 'qaset' as ArtifactType, label: 'QA Set', accept: '.jsonl', description: 'JSONL format: {"qid": "1", "question": "...", "expected_answer": "..."}' },
              { key: 'attacks' as ArtifactType, label: 'Attacks', accept: '.txt,.yaml,.yml', description: 'Text format (one per line) or YAML format' },
              { key: 'schema' as ArtifactType, label: 'Schema', accept: '.json', description: 'JSON Schema format (draft-07+)' }
            ]).map(({ key, label, accept, description }) => (
              <div key={key}>
                <label htmlFor={`file-${key}`} className="label">{label}</label>
                <input
                  id={`file-${key}`}
                  ref={(el) => { fileInputRefs.current[key] = el; }}
                  type="file"
                  accept={accept}
                  className="input file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 dark:file:bg-slate-700 dark:file:text-slate-200"
                />
                <small className="block text-slate-500 dark:text-slate-400 mt-1">{description}</small>
              </div>
            ))}
          </div>
          <button
            onClick={handleUpload}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Uploading...
              </>
            ) : (
              <>
                <Upload size={16} />
                Upload Files
              </>
            )}
          </button>
        </div>
      )}

      {/* URL Tab */}
      {activeTab === 'url' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {([
              { key: 'passages' as ArtifactType, label: 'Passages URL', placeholder: 'https://example.com/passages.jsonl' },
              { key: 'qaset' as ArtifactType, label: 'QA Set URL', placeholder: 'https://example.com/qaset.jsonl' },
              { key: 'attacks' as ArtifactType, label: 'Attacks URL', placeholder: 'https://example.com/attacks.txt' },
              { key: 'schema' as ArtifactType, label: 'Schema URL', placeholder: 'https://example.com/schema.json' }
            ]).map(({ key, label, placeholder }) => (
              <div key={key}>
                <label htmlFor={`url-${key}`} className="label">{label}</label>
                <input
                  id={`url-${key}`}
                  type="url"
                  className="input"
                  placeholder={placeholder}
                  value={urls[key]}
                  onChange={(e) => setUrls(prev => ({ ...prev, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <button
            onClick={handleUrlIngestion}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Ingesting...
              </>
            ) : (
              <>
                <Link size={16} />
                Ingest from URLs
              </>
            )}
          </button>
        </div>
      )}

      {/* Paste Tab */}
      {activeTab === 'paste' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {([
              { key: 'passages' as ArtifactType, label: 'Passages (JSONL)', placeholder: '{"id": "1", "text": "Sample passage"}\n{"id": "2", "text": "Another passage"}' },
              { key: 'qaset' as ArtifactType, label: 'QA Set (JSONL)', placeholder: '{"qid": "1", "question": "What is AI?", "expected_answer": "Artificial Intelligence"}' },
              { key: 'attacks' as ArtifactType, label: 'Attacks (Text/YAML)', placeholder: 'How to hack systems\nCreate malware\n\n# Or YAML format:\nattacks:\n  - "Attack 1"\n  - "Attack 2"' },
              { key: 'schema' as ArtifactType, label: 'Schema (JSON)', placeholder: '{\n  "$schema": "http://json-schema.org/draft-07/schema#",\n  "type": "object",\n  "properties": {\n    "name": {"type": "string"}\n  }\n}' }
            ]).map(({ key, label, placeholder }) => (
              <div key={key}>
                <label htmlFor={`paste-${key}`} className="label">{label}</label>
                <textarea
                  id={`paste-${key}`}
                  className="input min-h-[120px] font-mono text-sm"
                  placeholder={placeholder}
                  value={pasteContent[key]}
                  onChange={(e) => setPasteContent(prev => ({ ...prev, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <button
            onClick={handlePasteIngestion}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Processing...
              </>
            ) : (
              <>
                <FileText size={16} />
                Process Content
              </>
            )}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="mt-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={16} className="text-green-600" />
            <span className="font-semibold text-green-800 dark:text-green-200">Success</span>
          </div>
          
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Test Data ID:</span>
              <code className="px-2 py-1 bg-white dark:bg-slate-800 border rounded font-mono text-sm">
                {result.testdata_id}
              </code>
              <button
                onClick={() => copyToClipboard(result.testdata_id)}
                className="btn btn-ghost p-1"
                title="Copy to clipboard"
              >
                <Copy size={14} />
              </button>
            </div>
            
            <div>
              <span className="text-sm font-medium">Artifacts:</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {result.artifacts.map(artifact => (
                  <span key={artifact} className="pill text-xs">
                    {artifact} ({result.counts[artifact]} items)
                  </span>
                ))}
              </div>
            </div>
            
            <button
              onClick={() => validateTestdataId(result.testdata_id)}
              disabled={loading}
              className="btn btn-ghost"
            >
              {loading ? (
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
          </div>
        </div>
      )}

      {/* Meta Information */}
      {meta && (
        <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
          <div className="flex items-center gap-2 mb-3">
            <Clock size={16} className="text-blue-600" />
            <span className="font-semibold text-blue-800 dark:text-blue-200">Metadata</span>
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span>Created:</span>
              <span className="font-mono">{new Date(meta.created_at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>TTL:</span>
              <span className="font-mono text-orange-600 dark:text-orange-400">
                {formatExpiryTime(meta.expires_at)}
              </span>
            </div>
            <div>
              <span>Artifacts:</span>
              <div className="grid grid-cols-2 gap-2 mt-1">
                {Object.entries(meta.artifacts).map(([key, info]) => (
                  <div key={key} className="flex items-center gap-2">
                    {info.present ? (
                      <CheckCircle2 size={14} className="text-green-600" />
                    ) : (
                      <XCircle size={14} className="text-slate-400" />
                    )}
                    <span className={clsx(
                      'text-xs',
                      info.present ? 'text-slate-900 dark:text-slate-100' : 'text-slate-500'
                    )}>
                      {key} {info.present && info.count && `(${info.count})`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={clsx(
              'max-w-sm p-4 rounded-xl shadow-lg border',
              toast.type === 'success' && 'bg-green-50 border-green-200 text-green-800',
              toast.type === 'error' && 'bg-red-50 border-red-200 text-red-800',
              toast.type === 'info' && 'bg-blue-50 border-blue-200 text-blue-800'
            )}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold">{toast.title}</div>
                {toast.message && (
                  <div className="text-sm mt-1 opacity-90">{toast.message}</div>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="ml-3 text-current opacity-60 hover:opacity-100"
              >
                <XCircle size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
