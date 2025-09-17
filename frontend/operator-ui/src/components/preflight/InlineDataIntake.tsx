/**
 * Inline Test Data Intake Component
 * Embedded within suite cards for direct data upload/URL/paste
 */

import React, { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Upload, Link, FileText, Download, Check, X, Eye, AlertCircle,
  ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle
} from 'lucide-react';
import clsx from 'clsx';

export interface TestDataArtifact {
  type: string;
  name: string;
  description: string;
  templateUrl: string;
  required: boolean;
}

export interface ValidationResult {
  success: boolean;
  testdata_id?: string;
  counts?: Record<string, number>;
  meta?: Record<string, any>;
  errors?: string[];
  sample?: any[];
}

export interface InlineDataIntakeProps {
  suiteId: string;
  artifacts: TestDataArtifact[];
  onValidationComplete: (artifactType: string, result: ValidationResult) => void;
  onClear: (artifactType: string) => void;
  validatedArtifacts: Record<string, ValidationResult>;
  className?: string;
}

type IntakeMode = 'upload' | 'url' | 'paste';

export default function InlineDataIntake({
  suiteId,
  artifacts,
  onValidationComplete,
  onClear,
  validatedArtifacts,
  className
}: InlineDataIntakeProps) {
  const [expandedArtifact, setExpandedArtifact] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<IntakeMode>('upload');
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [urlInputs, setUrlInputs] = useState<Record<string, string>>({});
  const [pasteInputs, setPasteInputs] = useState<Record<string, string>>({});
  const [dragOver, setDragOver] = useState<string | null>(null);
  
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // Handle file upload
  const handleFileUpload = useCallback(async (artifactType: string, files: FileList) => {
    if (files.length === 0) return;
    
    const file = files[0];
    setLoading(prev => ({ ...prev, [artifactType]: true }));
    
    try {
      // Client-side pre-validation
      const maxSize = 50 * 1024 * 1024; // 50MB
      if (file.size > maxSize) {
        throw new Error(`File too large. Maximum size is ${maxSize / 1024 / 1024}MB`);
      }
      
      // Check file extension
      const allowedExtensions = getAllowedExtensions(artifactType);
      const fileExt = file.name.split('.').pop()?.toLowerCase();
      if (fileExt && !allowedExtensions.includes(fileExt)) {
        throw new Error(`Invalid file type. Allowed: ${allowedExtensions.join(', ')}`);
      }
      
      // Upload to server
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', artifactType);
      formData.append('suite_id', suiteId);
      
      const response = await fetch('/testdata/upload', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Upload failed: ${response.status}`);
      }
      
      const result: ValidationResult = await response.json();
      onValidationComplete(artifactType, result);
      
    } catch (error) {
      const errorResult: ValidationResult = {
        success: false,
        errors: [error instanceof Error ? error.message : String(error)]
      };
      onValidationComplete(artifactType, errorResult);
    } finally {
      setLoading(prev => ({ ...prev, [artifactType]: false }));
    }
  }, [suiteId, onValidationComplete]);

  // Handle URL fetch
  const handleUrlFetch = useCallback(async (artifactType: string) => {
    const url = urlInputs[artifactType]?.trim();
    if (!url) return;
    
    setLoading(prev => ({ ...prev, [artifactType]: true }));
    
    try {
      const response = await fetch('/testdata/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, type: artifactType, suite_id: suiteId })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `URL fetch failed: ${response.status}`);
      }
      
      const result: ValidationResult = await response.json();
      onValidationComplete(artifactType, result);
      
      // Clear URL input on success
      if (result.success) {
        setUrlInputs(prev => ({ ...prev, [artifactType]: '' }));
      }
      
    } catch (error) {
      const errorResult: ValidationResult = {
        success: false,
        errors: [error instanceof Error ? error.message : String(error)]
      };
      onValidationComplete(artifactType, errorResult);
    } finally {
      setLoading(prev => ({ ...prev, [artifactType]: false }));
    }
  }, [urlInputs, suiteId, onValidationComplete]);

  // Handle paste content
  const handlePasteContent = useCallback(async (artifactType: string) => {
    const content = pasteInputs[artifactType]?.trim();
    if (!content) return;
    
    setLoading(prev => ({ ...prev, [artifactType]: true }));
    
    try {
      const response = await fetch('/testdata/paste', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, type: artifactType, suite_id: suiteId })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Content validation failed: ${response.status}`);
      }
      
      const result: ValidationResult = await response.json();
      onValidationComplete(artifactType, result);
      
      // Clear paste input on success
      if (result.success) {
        setPasteInputs(prev => ({ ...prev, [artifactType]: '' }));
      }
      
    } catch (error) {
      const errorResult: ValidationResult = {
        success: false,
        errors: [error instanceof Error ? error.message : String(error)]
      };
      onValidationComplete(artifactType, errorResult);
    } finally {
      setLoading(prev => ({ ...prev, [artifactType]: false }));
    }
  }, [pasteInputs, suiteId, onValidationComplete]);

  // Drag and drop handlers
  const handleDragOver = useCallback((e: React.DragEvent, artifactType: string) => {
    e.preventDefault();
    setDragOver(artifactType);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, artifactType: string) => {
    e.preventDefault();
    setDragOver(null);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(artifactType, files);
    }
  }, [handleFileUpload]);

  // Get allowed file extensions for artifact type
  const getAllowedExtensions = (artifactType: string): string[] => {
    switch (artifactType) {
      case 'passages':
      case 'qaset':
        return ['jsonl', 'json', 'xlsx', 'xls']; // Added Excel support for RAG
      case 'attacks':
        return ['txt', 'yaml', 'yml'];
      case 'safety':
      case 'bias':
      case 'scenarios':
      case 'schema':
        return ['json', 'yaml', 'yml'];
      default:
        return ['json', 'jsonl', 'yaml', 'yml', 'txt'];
    }
  };

  // Download template with specific format
  const downloadTemplate = useCallback(async (artifact: TestDataArtifact, format?: string) => {
    try {
      const selectedFormat = format || getDefaultFormat(artifact.type);
      const response = await fetch(`/testdata/template?type=${artifact.type}&format=${selectedFormat}`);
      if (!response.ok) throw new Error('Template download failed');
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${artifact.type}_template.${selectedFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Template download failed:', error);
    }
  }, []);

  // Get available formats for each artifact type
  const getAvailableFormats = (type: string): string[] => {
    switch (type) {
      case 'passages':
      case 'qaset':
        return ['jsonl', 'xlsx'];
      case 'attacks':
      case 'safety':
      case 'bias':
      case 'scenarios':
        return ['json', 'yaml'];
      case 'schema':
        return ['json'];
      default:
        return ['json'];
    }
  };

  const getDefaultFormat = (type: string): string => {
    switch (type) {
      case 'passages':
      case 'qaset':
        return 'jsonl';
      case 'attacks':
        return 'yaml';
      default:
        return 'json';
    }
  };

  // Toggle artifact panel
  const toggleArtifact = (artifactType: string) => {
    setExpandedArtifact(expandedArtifact === artifactType ? null : artifactType);
  };

  // Render validation status
  const renderValidationStatus = (artifactType: string) => {
    const result = validatedArtifacts[artifactType];
    
    if (!result) {
      return (
        <button
          onClick={() => toggleArtifact(artifactType)}
          className="px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm rounded-lg hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
          aria-expanded={expandedArtifact === artifactType}
          aria-controls={`intake-panel-${artifactType}`}
        >
          Missing: {artifactType}
        </button>
      );
    }
    
    if (result.success) {
      return (
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-sm rounded-lg">
            <CheckCircle2 size={14} />
            <span>{artifactType}</span>
            {result.counts && (
              <span className="ml-1 text-xs opacity-75">
                ({Object.values(result.counts).reduce((a, b) => a + b, 0)} items)
              </span>
            )}
          </div>
          
          {/* View sample button */}
          {result.sample && (
            <button
              className="p-1 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/30 rounded transition-colors"
              title="View sample"
            >
              <Eye size={14} />
            </button>
          )}
          
          {/* Clear button */}
          <button
            onClick={() => onClear(artifactType)}
            className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
            title="Clear data"
          >
            <X size={14} />
          </button>
        </div>
      );
    }
    
    // Error state
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => toggleArtifact(artifactType)}
          className="flex items-center gap-1 px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
          aria-expanded={expandedArtifact === artifactType}
          aria-controls={`intake-panel-${artifactType}`}
        >
          <XCircle size={14} />
          <span>{artifactType} (Error)</span>
        </button>
      </div>
    );
  };

  return (
    <div className={clsx("space-y-3", className)}>
      {artifacts.map(artifact => (
        <div key={artifact.type} className="space-y-2">
          {/* Artifact status badge */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {renderValidationStatus(artifact.type)}
              
              {/* Download template button(s) */}
              {getAvailableFormats(artifact.type).length === 1 ? (
                <button
                  onClick={() => downloadTemplate(artifact, getAvailableFormats(artifact.type)[0])}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-700 rounded transition-colors"
                  title={`Download ${artifact.type} template (${getAvailableFormats(artifact.type)[0]})`}
                >
                  <Download size={12} />
                  Template
                </button>
              ) : (
                <div className="relative">
                  <div className="flex items-center gap-1">
                    {getAvailableFormats(artifact.type).map(format => (
                      <button
                        key={format}
                        onClick={() => downloadTemplate(artifact, format)}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-700 rounded transition-colors"
                        title={`Download ${artifact.type} template (${format.toUpperCase()})`}
                      >
                        <Download size={12} />
                        {format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            {/* Loading indicator */}
            {loading[artifact.type] && (
              <Loader2 size={16} className="animate-spin text-blue-500" />
            )}
          </div>
          
          {/* Intake panel */}
          <AnimatePresence>
            {expandedArtifact === artifact.type && (
              <motion.div
                id={`intake-panel-${artifact.type}`}
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800/50"
              >
                <div className="p-4 space-y-4">
                  {/* Mode tabs */}
                  <div className="flex border-b border-slate-200 dark:border-slate-700">
                    {(['upload', 'url', 'paste'] as IntakeMode[]).map(mode => (
                      <button
                        key={mode}
                        onClick={() => setActiveMode(mode)}
                        className={clsx(
                          "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                          activeMode === mode
                            ? "text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400"
                            : "text-slate-600 dark:text-slate-400 border-transparent hover:text-slate-900 dark:hover:text-slate-100"
                        )}
                      >
                        {mode === 'upload' && <Upload size={16} />}
                        {mode === 'url' && <Link size={16} />}
                        {mode === 'paste' && <FileText size={16} />}
                        {mode.charAt(0).toUpperCase() + mode.slice(1)}
                      </button>
                    ))}
                  </div>
                  
                  {/* Mode content */}
                  <div className="min-h-[120px]">
                    {activeMode === 'upload' && (
                      <div
                        className={clsx(
                          "border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer",
                          dragOver === artifact.type
                            ? "border-blue-400 bg-blue-50 dark:bg-blue-900/20"
                            : "border-slate-300 dark:border-slate-600 hover:border-slate-400 dark:hover:border-slate-500"
                        )}
                        onDragOver={(e) => handleDragOver(e, artifact.type)}
                        onDragLeave={handleDragLeave}
                        onDrop={(e) => handleDrop(e, artifact.type)}
                        onClick={() => fileInputRefs.current[artifact.type]?.click()}
                      >
                        <Upload size={32} className="mx-auto mb-2 text-slate-400" />
                        <p className="text-sm text-slate-600 dark:text-slate-400 mb-1">
                          Drop your {artifact.type} file here or click to browse
                        </p>
                        <p className="text-xs text-slate-500">
                          Supported: {getAllowedExtensions(artifact.type).join(', ')} (max 50MB)
                        </p>
                        
                        <input
                          ref={el => fileInputRefs.current[artifact.type] = el}
                          type="file"
                          accept={getAllowedExtensions(artifact.type).map(ext => `.${ext}`).join(',')}
                          onChange={(e) => e.target.files && handleFileUpload(artifact.type, e.target.files)}
                          className="hidden"
                          disabled={loading[artifact.type]}
                        />
                      </div>
                    )}
                    
                    {activeMode === 'url' && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                            URL to {artifact.type} file
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="url"
                              value={urlInputs[artifact.type] || ''}
                              onChange={(e) => setUrlInputs(prev => ({ ...prev, [artifact.type]: e.target.value }))}
                              placeholder={`https://example.com/${artifact.type}.json`}
                              className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100"
                              disabled={loading[artifact.type]}
                            />
                            <button
                              onClick={() => handleUrlFetch(artifact.type)}
                              disabled={!urlInputs[artifact.type]?.trim() || loading[artifact.type]}
                              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                            >
                              Fetch
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-slate-500">
                          URL must be publicly accessible and return the file content
                        </p>
                      </div>
                    )}
                    
                    {activeMode === 'paste' && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                            Paste {artifact.type} content
                          </label>
                          <textarea
                            value={pasteInputs[artifact.type] || ''}
                            onChange={(e) => setPasteInputs(prev => ({ ...prev, [artifact.type]: e.target.value }))}
                            placeholder={`Paste your ${artifact.type} content here...`}
                            rows={6}
                            className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-100 font-mono text-sm"
                            disabled={loading[artifact.type]}
                          />
                          <div className="flex justify-between items-center mt-2">
                            <p className="text-xs text-slate-500">
                              Paste JSON, JSONL, YAML, or text content
                            </p>
                            <button
                              onClick={() => handlePasteContent(artifact.type)}
                              disabled={!pasteInputs[artifact.type]?.trim() || loading[artifact.type]}
                              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm"
                            >
                              Validate
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Error display */}
                  {validatedArtifacts[artifact.type]?.errors && (
                    <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                        <div className="space-y-1">
                          {validatedArtifacts[artifact.type]!.errors!.map((error, idx) => (
                            <p key={idx} className="text-sm text-red-700 dark:text-red-300">
                              {error}
                            </p>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Close button */}
                  <div className="flex justify-end pt-2 border-t border-slate-200 dark:border-slate-700">
                    <button
                      onClick={() => setExpandedArtifact(null)}
                      className="flex items-center gap-1 px-3 py-1 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                    >
                      <ChevronUp size={16} />
                      Close
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
