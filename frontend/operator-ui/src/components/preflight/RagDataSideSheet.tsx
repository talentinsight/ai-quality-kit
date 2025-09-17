import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, Upload, Link, FileText, CheckCircle2, AlertCircle, 
  Database, FileCheck, Trash2, Eye
} from 'lucide-react';

interface RagDataSideSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

interface UploadedFile {
  id: string;
  name: string;
  type: 'passages' | 'qaset' | 'schema';
  size: number;
  status: 'uploading' | 'success' | 'error';
  count?: number;
  preview?: string;
}

export default function RagDataSideSheet({ isOpen, onClose }: RagDataSideSheetProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'url' | 'paste'>('upload');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  
  // URL form state
  const [urlData, setUrlData] = useState({
    passages: '',
    qaset: '',
    schema: ''
  });
  
  // Paste form state
  const [pasteData, setPasteData] = useState({
    passages: '',
    qaset: '',
    schema: ''
  });

  const handleFileUpload = (files: FileList | null) => {
    if (!files) return;
    
    Array.from(files).forEach((file) => {
      const fileType = file.name.includes('passage') ? 'passages' 
                     : file.name.includes('qa') ? 'qaset' 
                     : 'schema';
      
      const uploadedFile: UploadedFile = {
        id: Math.random().toString(36).substr(2, 9),
        name: file.name,
        type: fileType,
        size: file.size,
        status: 'uploading'
      };
      
      setUploadedFiles(prev => [...prev, uploadedFile]);
      
      // Simulate upload
      setTimeout(() => {
        setUploadedFiles(prev => prev.map(f => 
          f.id === uploadedFile.id 
            ? { 
                ...f, 
                status: Math.random() > 0.1 ? 'success' : 'error',
                count: Math.floor(Math.random() * 100) + 10,
                preview: `${Math.floor(Math.random() * 100) + 10} items loaded`
              }
            : f
        ));
      }, 1500);
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const removeFile = (fileId: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'passages': return Database;
      case 'qaset': return FileCheck;
      case 'schema': return FileText;
      default: return FileText;
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          />
          
          {/* Side Sheet */}
          <motion.div
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 h-full w-96 bg-[#0B0D12] border-l border-gray-700 z-50 overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <h2 className="text-xl font-bold text-white">RAG Test Data</h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors duration-200"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-700">
              {[
                { id: 'upload', label: 'Upload', icon: Upload },
                { id: 'url', label: 'URL', icon: Link },
                { id: 'paste', label: 'Paste', icon: FileText }
              ].map(tab => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`
                      flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors duration-200
                      ${activeTab === tab.id 
                        ? 'text-purple-300 border-b-2 border-purple-500' 
                        : 'text-gray-400 hover:text-white'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {/* Upload Tab */}
              {activeTab === 'upload' && (
                <div className="p-6 space-y-6">
                  {/* Drop Zone */}
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`
                      border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200
                      ${isDragging 
                        ? 'border-purple-500 bg-purple-500/10' 
                        : 'border-gray-600 hover:border-gray-500'
                      }
                    `}
                  >
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-white mb-2">
                      Drop files here
                    </h3>
                    <p className="text-gray-400 mb-4">
                      or click to browse
                    </p>
                    <input
                      type="file"
                      multiple
                      accept=".json,.jsonl,.xlsx,.csv"
                      onChange={(e) => handleFileUpload(e.target.files)}
                      className="hidden"
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg cursor-pointer transition-colors duration-200"
                    >
                      <Upload className="w-4 h-4" />
                      Choose Files
                    </label>
                    <p className="text-xs text-gray-500 mt-3">
                      Supports JSON, JSONL, Excel, CSV
                    </p>
                  </div>

                  {/* Uploaded Files */}
                  {uploadedFiles.length > 0 && (
                    <div className="space-y-3">
                      <h3 className="text-sm font-medium text-white">Uploaded Files</h3>
                      {uploadedFiles.map((file) => {
                        const Icon = getFileIcon(file.type);
                        return (
                          <div
                            key={file.id}
                            className="flex items-center gap-3 p-3 bg-gray-800/50 border border-gray-700 rounded-lg"
                          >
                            <div className="p-2 bg-blue-500/20 rounded">
                              <Icon className="w-4 h-4 text-blue-400" />
                            </div>
                            
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-white truncate">
                                  {file.name}
                                </span>
                                {file.status === 'success' && (
                                  <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                                )}
                                {file.status === 'error' && (
                                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                                )}
                              </div>
                              
                              <div className="flex items-center gap-2 text-xs text-gray-400">
                                <span>{formatFileSize(file.size)}</span>
                                <span>•</span>
                                <span className="capitalize">{file.type}</span>
                                {file.count && (
                                  <>
                                    <span>•</span>
                                    <span>{file.count} items</span>
                                  </>
                                )}
                              </div>
                              
                              {file.status === 'uploading' && (
                                <div className="w-full bg-gray-700 rounded-full h-1 mt-2">
                                  <div className="bg-purple-600 h-1 rounded-full animate-pulse w-2/3"></div>
                                </div>
                              )}
                              
                              {file.preview && (
                                <p className="text-xs text-green-400 mt-1">{file.preview}</p>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-1">
                              {file.status === 'success' && (
                                <button className="p-1 text-gray-400 hover:text-white transition-colors duration-200">
                                  <Eye className="w-4 h-4" />
                                </button>
                              )}
                              <button
                                onClick={() => removeFile(file.id)}
                                className="p-1 text-gray-400 hover:text-red-400 transition-colors duration-200"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* URL Tab */}
              {activeTab === 'url' && (
                <div className="p-6 space-y-6">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Passages URL
                      </label>
                      <input
                        type="url"
                        value={urlData.passages}
                        onChange={(e) => setUrlData(prev => ({ ...prev, passages: e.target.value }))}
                        placeholder="https://example.com/passages.jsonl"
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        QA Set URL
                      </label>
                      <input
                        type="url"
                        value={urlData.qaset}
                        onChange={(e) => setUrlData(prev => ({ ...prev, qaset: e.target.value }))}
                        placeholder="https://example.com/qaset.jsonl"
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Schema URL (Optional)
                      </label>
                      <input
                        type="url"
                        value={urlData.schema}
                        onChange={(e) => setUrlData(prev => ({ ...prev, schema: e.target.value }))}
                        placeholder="https://example.com/schema.json"
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
                      />
                    </div>
                  </div>
                  
                  <button className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors duration-200">
                    Load from URLs
                  </button>
                </div>
              )}

              {/* Paste Tab */}
              {activeTab === 'paste' && (
                <div className="p-6 space-y-6">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Passages (JSONL)
                      </label>
                      <textarea
                        value={pasteData.passages}
                        onChange={(e) => setPasteData(prev => ({ ...prev, passages: e.target.value }))}
                        placeholder='{"text": "Sample passage content..."}'
                        rows={4}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200 resize-none font-mono text-sm"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        QA Set (JSONL)
                      </label>
                      <textarea
                        value={pasteData.qaset}
                        onChange={(e) => setPasteData(prev => ({ ...prev, qaset: e.target.value }))}
                        placeholder='{"question": "What is...", "answer": "The answer is..."}'
                        rows={4}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200 resize-none font-mono text-sm"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Schema (JSON, Optional)
                      </label>
                      <textarea
                        value={pasteData.schema}
                        onChange={(e) => setPasteData(prev => ({ ...prev, schema: e.target.value }))}
                        placeholder='{"type": "object", "properties": {...}}'
                        rows={3}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200 resize-none font-mono text-sm"
                      />
                    </div>
                  </div>
                  
                  <button className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors duration-200">
                    Process Data
                  </button>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-gray-700 bg-gray-800/30">
              <div className="text-xs text-gray-400 space-y-1">
                <p>• Passages: Knowledge base documents for retrieval</p>
                <p>• QA Set: Question-answer pairs for evaluation</p>
                <p>• Schema: Optional response structure validation</p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
