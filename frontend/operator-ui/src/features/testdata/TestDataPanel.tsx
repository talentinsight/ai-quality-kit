import React, { useState, useRef } from 'react';
import { Upload, Link, FileText, CheckCircle2, XCircle, Copy, RefreshCw, Clock } from 'lucide-react';
import clsx from 'clsx';
import type { ArtifactType, TestDataUploadResponse, TestDataMeta, AttacksValidationResult, SafetyValidationResult, BiasValidationResult, PerfValidationResult } from '../../types';
import { 
  postTestdataUpload, 
  postTestdataByUrl, 
  postTestdataPaste, 
  getTestdataMeta,
  getBaseUrl,
  ApiError 
} from '../../lib/api';

interface TestDataPanelProps {
  token?: string | null;
  onTestDataUploaded?: (testdataId: string, artifacts: string[]) => void;
  onSafetyValidation?: (validation: SafetyValidationResult) => void;
  onAttacksValidation?: (validation: AttacksValidationResult) => void;
  onBiasValidation?: (validation: BiasValidationResult) => void;
  onPerfValidation?: (validation: PerfValidationResult) => void;
}

type TabType = 'upload' | 'url' | 'paste';

interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

export default function TestDataPanel({ 
  token, 
  onTestDataUploaded, 
  onSafetyValidation, 
  onAttacksValidation,
  onBiasValidation,
  onPerfValidation
}: TestDataPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('upload');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestDataUploadResponse | null>(null);
  const [meta, setMeta] = useState<TestDataMeta | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [attacksValidation, setAttacksValidation] = useState<AttacksValidationResult | null>(null);
  const [safetyValidation, setSafetyValidation] = useState<SafetyValidationResult | null>(null);
  const [biasValidation, setBiasValidation] = useState<BiasValidationResult | null>(null);
  const [perfValidation, setPerfValidation] = useState<PerfValidationResult | null>(null);
  const [fileValidations, setFileValidations] = useState<Record<ArtifactType, { valid: boolean; message: string; details?: any }>>({
    passages: { valid: true, message: '' },
    qaset: { valid: true, message: '' },
    attacks: { valid: true, message: '' },
    safety: { valid: true, message: '' },
    bias: { valid: true, message: '' },
    performance: { valid: true, message: '' },
    schema: { valid: true, message: '' }
  });
  
  // Form state
  const [urls, setUrls] = useState<Record<ArtifactType, string>>({
    passages: '',
    qaset: '',
    attacks: '',
    safety: '',
    bias: '',
    performance: '',
    schema: ''
  });
  
  const [pasteContent, setPasteContent] = useState<Record<ArtifactType, string>>({
    passages: '',
    qaset: '',
    attacks: '',
    safety: '',
    bias: '',
    performance: '',
    schema: ''
  });
  
  const fileInputRefs = useRef<Record<ArtifactType, HTMLInputElement | null>>({
    passages: null,
    qaset: null,
    attacks: null,
    safety: null,
    bias: null,
    performance: null,
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

  // Validate file based on type
  const validateFile = (file: File, fileType: ArtifactType): { valid: boolean; error?: string } => {
    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      return { valid: false, error: 'File size must be less than 10MB' };
    }

    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();

    switch (fileType) {
      case 'attacks':
        const attacksTypes = ['.yaml', '.yml', '.json', '.jsonl'];
        if (!attacksTypes.includes(fileExtension)) {
          return { valid: false, error: `Attacks file type ${fileExtension} not supported. Use .yaml, .yml, .json, or .jsonl` };
        }
        break;
      
      case 'safety':
        const safetyTypes = ['.yaml', '.yml', '.json', '.jsonl'];
        if (!safetyTypes.includes(fileExtension)) {
          return { valid: false, error: `Safety file type ${fileExtension} not supported. Use .yaml, .yml, .json, or .jsonl` };
        }
        break;
      
      case 'bias':
        const biasTypes = ['.yaml', '.yml', '.json', '.jsonl'];
        if (!biasTypes.includes(fileExtension)) {
          return { valid: false, error: `Bias file type ${fileExtension} not supported. Use .yaml, .yml, .json, or .jsonl` };
        }
        break;
      
      case 'performance':
        const perfTypes = ['.yaml', '.yml', '.json', '.jsonl'];
        if (!perfTypes.includes(fileExtension)) {
          return { valid: false, error: `Performance file type ${fileExtension} not supported. Use .yaml, .yml, .json, or .jsonl` };
        }
        break;
      
      case 'passages':
      case 'qaset':
        const dataTypes = ['.jsonl', '.xlsx', '.xls'];
        if (!dataTypes.includes(fileExtension)) {
          return { valid: false, error: `${fileType} file type ${fileExtension} not supported. Use .jsonl, .xlsx, or .xls` };
        }
        break;
      
      case 'schema':
        if (fileExtension !== '.json') {
          return { valid: false, error: `Schema file type ${fileExtension} not supported. Use .json` };
        }
        break;
      
      default:
        return { valid: false, error: `Unknown file type: ${fileType}` };
    }

    return { valid: true };
  };

  // Validate file content based on type
  const validateFileContent = async (file: File, fileType: ArtifactType): Promise<void> => {
    const reader = new FileReader();
    
    reader.onload = async (e) => {
      const content = e.target?.result as string;
      if (!content) return;

      try {
        switch (fileType) {
          case 'attacks':
            await validateDatasetContent(content);
            break;
          
          case 'safety':
            await validateSafetyContent(content);
            break;
          
          case 'bias':
            await validateBiasContent(content);
            break;
          
          case 'performance':
            await validatePerfContent(content);
            break;
          
          case 'passages':
            await validatePassagesContent(content, file.name);
            break;
          
          case 'qaset':
            await validateQASetContent(content, file.name);
            break;
          
          case 'schema':
            await validateSchemaContent(content);
            break;
        }
      } catch (error) {
        setFileValidations(prev => ({
          ...prev,
          [fileType]: {
            valid: false,
            message: `Content validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`
          }
        }));
      }
    };

    reader.readAsText(file);
  };

  // Validate passages content
  const validatePassagesContent = async (content: string, filename: string): Promise<void> => {
    const isExcel = filename.endsWith('.xlsx') || filename.endsWith('.xls');
    
    if (isExcel) {
      // For Excel files, we can't validate content here (binary format)
      setFileValidations(prev => ({
        ...prev,
        passages: { valid: true, message: 'Excel file selected - will be validated on server' }
      }));
      return;
    }

    // Validate JSONL format
    const lines = content.trim().split('\n').filter(line => line.trim());
    if (lines.length === 0) {
      throw new Error('File is empty');
    }

    let validCount = 0;
    const errors: string[] = [];

    for (let i = 0; i < Math.min(lines.length, 5); i++) { // Check first 5 lines
      try {
        const obj = JSON.parse(lines[i]);
        if (!obj.id || !obj.text) {
          errors.push(`Line ${i + 1}: Missing required fields 'id' or 'text'`);
        } else {
          validCount++;
        }
      } catch (e) {
        errors.push(`Line ${i + 1}: Invalid JSON format`);
      }
    }

    if (errors.length > 0 && validCount === 0) {
      throw new Error(`Invalid passages format: ${errors.join(', ')}`);
    }

    setFileValidations(prev => ({
      ...prev,
      passages: {
        valid: true,
        message: `Valid passages file: ${lines.length} entries found`,
        details: { totalLines: lines.length, validSample: validCount, errors: errors.length > 0 ? errors : undefined }
      }
    }));
  };

  // Validate QA Set content
  const validateQASetContent = async (content: string, filename: string): Promise<void> => {
    const isExcel = filename.endsWith('.xlsx') || filename.endsWith('.xls');
    
    if (isExcel) {
      setFileValidations(prev => ({
        ...prev,
        qaset: { valid: true, message: 'Excel file selected - will be validated on server' }
      }));
      return;
    }

    // Validate JSONL format
    const lines = content.trim().split('\n').filter(line => line.trim());
    if (lines.length === 0) {
      throw new Error('File is empty');
    }

    let validCount = 0;
    const errors: string[] = [];

    for (let i = 0; i < Math.min(lines.length, 5); i++) { // Check first 5 lines
      try {
        const obj = JSON.parse(lines[i]);
        if (!obj.qid || !obj.question || !obj.expected_answer) {
          errors.push(`Line ${i + 1}: Missing required fields 'qid', 'question', or 'expected_answer'`);
        } else {
          validCount++;
        }
      } catch (e) {
        errors.push(`Line ${i + 1}: Invalid JSON format`);
      }
    }

    if (errors.length > 0 && validCount === 0) {
      throw new Error(`Invalid QA set format: ${errors.join(', ')}`);
    }

    setFileValidations(prev => ({
      ...prev,
      qaset: {
        valid: true,
        message: `Valid QA set file: ${lines.length} entries found`,
        details: { totalLines: lines.length, validSample: validCount, errors: errors.length > 0 ? errors : undefined }
      }
    }));
  };

  // Validate schema content
  const validateSchemaContent = async (content: string): Promise<void> => {
    try {
      const schema = JSON.parse(content);
      
      // Basic JSON Schema validation
      if (typeof schema !== 'object' || schema === null) {
        throw new Error('Schema must be a JSON object');
      }

      // Check for common schema properties
      const hasSchemaProps = schema.$schema || schema.type || schema.properties;
      if (!hasSchemaProps) {
        throw new Error('Does not appear to be a valid JSON Schema (missing $schema, type, or properties)');
      }

      setFileValidations(prev => ({
        ...prev,
        schema: {
          valid: true,
          message: 'Valid JSON Schema format',
          details: { hasSchema: !!schema.$schema, type: schema.type, hasProperties: !!schema.properties }
        }
      }));
    } catch (e) {
      if (e instanceof SyntaxError) {
        throw new Error('Invalid JSON format');
      }
      throw e;
    }
  };

  // Validate bias content
  const validateBiasContent = async (content: string) => {
    try {
      const baseUrl = getBaseUrl();
      const response = await fetch(`${baseUrl}/datasets/bias/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error(`Bias validation failed: ${response.statusText}`);
      }

      const validation: BiasValidationResult = await response.json();
      setBiasValidation(validation);

      // Notify parent component
      if (onBiasValidation) {
        onBiasValidation(validation);
      }

      if (validation.valid) {
        const totalCases = Object.values(validation.counts_by_category).reduce((sum, count) => sum + count, 0);
        const categories = Object.keys(validation.counts_by_category).join(', ');
        const subtypes = Object.values(validation.taxonomy).flat().join(', ');
        
        addToast({
          type: 'success',
          title: 'Bias dataset validated',
          message: `Loaded ${totalCases} cases (${validation.required_count} required) • Categories: ${categories} • Subtypes: ${subtypes}`
        });
      } else {
        addToast({
          type: 'error',
          title: 'Bias validation failed',
          message: validation.errors.join('; ') || 'Unknown validation error'
        });
      }
      return validation;
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Bias validation error',
        message: error instanceof Error ? error.message : 'Unknown validation error'
      });
      return null;
    }
  };

  // Validate performance content
  const validatePerfContent = async (content: string) => {
    try {
      const baseUrl = getBaseUrl();
      const response = await fetch(`${baseUrl}/datasets/performance/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error(`Performance validation failed: ${response.statusText}`);
      }

      const validation: PerfValidationResult = await response.json();
      setPerfValidation(validation);

      // Notify parent component
      if (onPerfValidation) {
        onPerfValidation(validation);
      }

      if (validation.valid) {
        const totalScenarios = Object.values(validation.counts_by_category).reduce((sum, count) => sum + count, 0);
        const categories = Object.keys(validation.counts_by_category).join(', ');
        const subtypes = Object.values(validation.taxonomy).flat().join(', ');
        
        addToast({
          type: 'success',
          title: 'Performance dataset validated',
          message: `Loaded ${totalScenarios} scenarios (${validation.required_count} required) • Categories: ${categories} • Subtypes: ${subtypes}`
        });
      } else {
        addToast({
          type: 'error',
          title: 'Performance validation failed',
          message: validation.errors.join('; ') || 'Unknown validation error'
        });
      }
      return validation;
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Performance validation error',
        message: error instanceof Error ? error.message : 'Unknown validation error'
      });
      return null;
    }
  };

  // Validate safety content
  const validateSafetyContent = async (content: string) => {
    try {
      const baseUrl = getBaseUrl();
      const response = await fetch(`${baseUrl}/datasets/safety/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error(`Safety validation failed: ${response.statusText}`);
      }

      const validation: SafetyValidationResult = await response.json();
      setSafetyValidation(validation);

      // Notify parent component
      if (onSafetyValidation) {
        onSafetyValidation(validation);
      }

      if (validation.valid) {
        const totalCases = Object.values(validation.counts_by_category).reduce((sum, count) => sum + count, 0);
        const categories = Object.keys(validation.counts_by_category).join(', ');
        const subtypes = Object.values(validation.taxonomy).flat().join(', ');
        
        addToast({
          type: 'success',
          title: 'Safety dataset validated',
          message: `Loaded ${totalCases} cases (${validation.required_count} required) • Categories: ${categories} • Subtypes: ${subtypes}`
        });
      } else {
        addToast({
          type: 'error',
          title: 'Safety validation failed',
          message: validation.errors.join('; ') || 'Unknown validation error'
        });
      }
      return validation;
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Safety validation error',
        message: error instanceof Error ? error.message : 'Unknown validation error'
      });
      return null;
    }
  };

  // Validate dataset content
  const validateDatasetContent = async (content: string) => {
    try {
      const baseUrl = getBaseUrl();
      const response = await fetch(`${baseUrl}/datasets/red_team/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.statusText}`);
      }

      const validation: AttacksValidationResult = await response.json();
      setAttacksValidation(validation);

      // Notify parent component
      if (onAttacksValidation) {
        onAttacksValidation(validation);
      }

      if (validation.valid) {
        const totalAttacks = Object.values(validation.counts_by_category).reduce((sum, count) => sum + count, 0);
        const categories = Object.keys(validation.counts_by_category).join(', ');
        const subtypes = Object.values(validation.taxonomy).flat().join(', ');
        
        addToast({
          type: 'success',
          title: 'Dataset validated',
          message: `Loaded ${totalAttacks} attacks (${validation.required_count} required) • Categories: ${categories} • Subtypes: ${subtypes}`
        });
      } else {
        addToast({
          type: 'error',
          title: 'Dataset validation failed',
          message: validation.errors.join(', ')
        });
      }

      return validation;
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Validation error',
        message: error instanceof Error ? error.message : 'Unknown validation error'
      });
      return null;
    }
  };

  // Handle upload
  const handleUpload = async () => {
    const formData = new FormData();
    let hasFiles = false;

    // Reset validation states
    setFileValidations({
      passages: { valid: true, message: '' },
      qaset: { valid: true, message: '' },
      attacks: { valid: true, message: '' },
      safety: { valid: true, message: '' },
      bias: { valid: true, message: '' },
      performance: { valid: true, message: '' },
      schema: { valid: true, message: '' }
    });

    // Validate and append files to form data
    const validationErrors: string[] = [];
    
    Object.entries(fileInputRefs.current).forEach(([key, input]) => {
      if (input?.files?.[0]) {
        const file = input.files[0];
        const fileType = key as ArtifactType;
        
        // Validate file type and size
        const validationResult = validateFile(file, fileType);
        if (!validationResult.valid) {
          validationErrors.push(`${fileType}: ${validationResult.error}`);
          setFileValidations(prev => ({
            ...prev,
            [fileType]: { valid: false, message: validationResult.error || 'Validation failed' }
          }));
          return;
        }
        
        // Validate file content (async)
        validateFileContent(file, fileType);
        
        formData.append(key, file);
        hasFiles = true;
      }
    });

    // Show validation errors if any
    if (validationErrors.length > 0) {
      addToast({
        type: 'error',
        title: 'File validation failed',
        message: validationErrors.join('; ')
      });
      return;
    }

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
      
      // Notify parent component
      if (onTestDataUploaded) {
        onTestDataUploaded(response.testdata_id, response.artifacts);
      }
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

    const urlPayload: Partial<Record<ArtifactType, string>> = {};
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

  const downloadTemplate = async (templateType: string) => {
    try {
      const baseUrl = getBaseUrl();
      
      // Map template types to API endpoints
      const endpointMap: Record<string, string> = {
        'qa-excel': '/testdata/templates/qa-excel',
        'passages-excel': '/testdata/templates/passages-excel',
        'qa-jsonl': '/testdata/templates/qa-jsonl',
        'passages-jsonl': '/testdata/templates/passages-jsonl',
        'attacks-yaml': '/testdata/templates/attacks.yaml',
        'attacks-json': '/testdata/templates/attacks.json',
        'attacks-jsonl': '/testdata/templates/attacks.jsonl',
        'safety-yaml': '/testdata/templates/safety.yaml',
        'safety-json': '/testdata/templates/safety.json',
        'bias-yaml': '/datasets/bias/template/yaml',
        'bias-json': '/datasets/bias/template/json',
        'perf-yaml': '/datasets/performance/template/yaml',
        'perf-json': '/datasets/performance/template/json'
      };
      
      const endpoint = endpointMap[templateType] || `/testdata/templates/${templateType}`;
      const url = `${baseUrl}${endpoint}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });
      
      if (!response.ok) {
        throw new Error(`Failed to download template: ${response.status}`);
      }
      
      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${templateType.replace('-', '_')}_template`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/"/g, '');
        }
      } else {
        // Add appropriate extension
        if (templateType.includes('excel')) {
          filename += '.xlsx';
        } else if (templateType.includes('jsonl')) {
          filename += '.jsonl';
        } else if (templateType.includes('yaml')) {
          filename += '.yaml';
        } else if (templateType.includes('txt')) {
          filename += '.txt';
        }
      }
      
      // Create blob and download
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
      
      addToast({ 
        type: 'success', 
        title: 'Template downloaded', 
        message: `${filename} downloaded successfully` 
      });
      
    } catch (error) {
      console.error('Template download error:', error);
      addToast({ 
        type: 'error', 
        title: 'Download failed', 
        message: error instanceof Error ? error.message : 'Failed to download template' 
      });
    }
  };

  return (
    <div className="card p-5" data-testid="test-data-panel">
      {/* Template Downloads - Compact */}
      <div className="mb-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
        <h3 className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">📥 Templates</h3>
        
        {/* QA & Passages Templates */}
        <div className="mb-2">
          <div className="text-xs text-slate-500 mb-1">QA & Passages</div>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => downloadTemplate('qa-excel')} className="btn btn-ghost btn-xs text-xs">📊 QA Excel</button>
            <button onClick={() => downloadTemplate('passages-excel')} className="btn btn-ghost btn-xs text-xs">📊 Passages Excel</button>
            <button onClick={() => downloadTemplate('qa-jsonl')} className="btn btn-ghost btn-xs text-xs">📄 QA JSONL</button>
            <button onClick={() => downloadTemplate('passages-jsonl')} className="btn btn-ghost btn-xs text-xs">📄 Passages JSONL</button>
          </div>
        </div>

        {/* Attacks Templates */}
        <div className="mb-2">
          <div className="text-xs text-slate-500 mb-1">Red Team Attacks</div>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => downloadTemplate('attacks-yaml')} className="btn btn-ghost btn-xs text-xs bg-red-50 text-red-700">🔥 YAML</button>
            <button onClick={() => downloadTemplate('attacks-json')} className="btn btn-ghost btn-xs text-xs bg-red-50 text-red-700">🔥 JSON</button>
          </div>
        </div>

        {/* Safety Templates */}
        <div className="mb-2">
          <div className="text-xs text-slate-500 mb-1">Safety</div>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => downloadTemplate('safety-yaml')} className="btn btn-ghost btn-xs text-xs bg-blue-50 text-blue-700">🛡️ YAML</button>
            <button onClick={() => downloadTemplate('safety-json')} className="btn btn-ghost btn-xs text-xs bg-blue-50 text-blue-700">🛡️ JSON</button>
          </div>
        </div>

        {/* Bias Templates */}
        <div className="mb-2">
          <div className="text-xs text-slate-500 mb-1">Bias Detection</div>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => downloadTemplate('bias-yaml')} className="btn btn-ghost btn-xs text-xs bg-purple-50 text-purple-700">⚖️ YAML</button>
            <button onClick={() => downloadTemplate('bias-json')} className="btn btn-ghost btn-xs text-xs bg-purple-50 text-purple-700">⚖️ JSON</button>
          </div>
        </div>

        {/* Performance Templates */}
        <div>
          <div className="text-xs text-slate-500 mb-1">Performance Testing</div>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => downloadTemplate('perf-yaml')} className="btn btn-ghost btn-xs text-xs bg-orange-50 text-orange-700">⚡ YAML</button>
            <button onClick={() => downloadTemplate('perf-json')} className="btn btn-ghost btn-xs text-xs bg-orange-50 text-orange-700">⚡ JSON</button>
          </div>
        </div>
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
              { key: 'passages' as ArtifactType, label: 'Passages', accept: '.jsonl,.xlsx,.xls', description: 'JSONL format or Excel template: {"id": "1", "text": "...", "meta": {...}}' },
              { key: 'qaset' as ArtifactType, label: 'QA Set', accept: '.jsonl,.xlsx,.xls', description: 'JSONL format or Excel template: {"qid": "1", "question": "...", "expected_answer": "..."}' },
              { key: 'attacks' as ArtifactType, label: 'Attacks', accept: '.yaml,.yml,.json,.jsonl', description: 'YAML, JSON, or JSONL format. Same fields; subtests come from `subtype`.' },
              { key: 'safety' as ArtifactType, label: 'Safety', accept: '.yaml,.yml,.json,.jsonl', description: 'YAML, JSON, or JSONL format. Same fields; subtests come from `subtype`.' },
              { key: 'bias' as ArtifactType, label: 'Bias', accept: '.yaml,.yml,.json,.jsonl', description: 'YAML, JSON, or JSONL format. Same fields; subtests come from `subtype`.' },
              { key: 'performance' as ArtifactType, label: 'Performance', accept: '.yaml,.yml,.json,.jsonl', description: 'YAML, JSON, or JSONL format. Same fields; subtests come from `subtype`.' },
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

          {/* File Validation Results */}
          {Object.entries(fileValidations).some(([_, validation]) => validation.message) && (
            <div className="space-y-3">
              <h4 className="font-medium text-slate-700 dark:text-slate-300">File Validation Results</h4>
              {Object.entries(fileValidations).map(([fileType, validation]) => {
                if (!validation.message) return null;
                
                return (
                  <div
                    key={fileType}
                    className={`p-3 rounded-lg border ${
                      validation.valid
                        ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
                        : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {validation.valid ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                      )}
                      <span className={`font-medium text-sm capitalize ${
                        validation.valid 
                          ? 'text-green-800 dark:text-green-200' 
                          : 'text-red-800 dark:text-red-200'
                      }`}>
                        {fileType}
                      </span>
                    </div>
                    <p className={`text-xs ${
                      validation.valid 
                        ? 'text-green-700 dark:text-green-300' 
                        : 'text-red-700 dark:text-red-300'
                    }`}>
                      {validation.message}
                    </p>
                    {validation.details?.errors && (
                      <div className="mt-2 text-xs text-yellow-700 dark:text-yellow-300">
                        <p><strong>Warnings:</strong></p>
                        <ul className="list-disc list-inside ml-2">
                          {validation.details.errors.slice(0, 3).map((error: string, index: number) => (
                            <li key={index}>{error}</li>
                          ))}
                          {validation.details.errors.length > 3 && (
                            <li>... and {validation.details.errors.length - 3} more</li>
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Attacks Validation Results (detailed) */}
          {attacksValidation && (
            <div className={`p-4 rounded-lg ${attacksValidation.valid ? 'bg-blue-50 border border-blue-200 dark:bg-blue-900/20 dark:border-blue-800' : 'bg-red-50 border border-red-200 dark:bg-red-900/20 dark:border-red-800'}`}>
              <div className="flex items-center gap-2 mb-2">
                {attacksValidation.valid ? (
                  <CheckCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                )}
                <h4 className={`font-medium ${attacksValidation.valid ? 'text-blue-800 dark:text-blue-200' : 'text-red-800 dark:text-red-200'}`}>
                  Attacks Content Analysis
                </h4>
              </div>
              
              {attacksValidation.valid && (
                <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
                  <p><strong>Format:</strong> {attacksValidation.format.toUpperCase()}</p>
                  <p><strong>Total Attacks:</strong> {Object.values(attacksValidation.counts_by_category).reduce((sum, count) => sum + count, 0)}</p>
                  <p><strong>Required Attacks:</strong> {attacksValidation.required_count}</p>
                  <p><strong>Categories:</strong> {Object.keys(attacksValidation.counts_by_category).join(', ')}</p>
                  <p><strong>Subtypes:</strong> {Object.values(attacksValidation.taxonomy).flat().join(', ')}</p>
                </div>
              )}
              
              {attacksValidation.errors.length > 0 && (
                <div className="text-sm text-red-700 dark:text-red-300">
                  <p><strong>Errors:</strong></p>
                  <ul className="list-disc list-inside">
                    {attacksValidation.errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {attacksValidation.warnings.length > 0 && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300 mt-2">
                  <p><strong>Warnings:</strong></p>
                  <ul className="list-disc list-inside">
                    {attacksValidation.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Safety Content Analysis */}
          {safetyValidation && (
            <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
                <h4 className="font-medium text-green-900 dark:text-green-100">
                  Safety Content Analysis
                </h4>
              </div>
              
              {safetyValidation.valid && (
                <div className="text-sm text-green-700 dark:text-green-300 space-y-1">
                  <p><strong>Format:</strong> {safetyValidation.format.toUpperCase()}</p>
                  <p><strong>Total Cases:</strong> {Object.values(safetyValidation.counts_by_category).reduce((sum, count) => sum + count, 0)}</p>
                  <p><strong>Required Cases:</strong> {safetyValidation.required_count}</p>
                  <p><strong>Categories:</strong> {Object.keys(safetyValidation.counts_by_category).join(', ')}</p>
                  <p><strong>Subtypes:</strong> {Object.values(safetyValidation.taxonomy).flat().join(', ')}</p>
                </div>
              )}
              
              {safetyValidation.errors.length > 0 && (
                <div className="text-sm text-red-700 dark:text-red-300">
                  <p><strong>Errors:</strong></p>
                  <ul className="list-disc list-inside">
                    {safetyValidation.errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {safetyValidation.warnings.length > 0 && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300">
                  <p><strong>Warnings:</strong></p>
                  <ul className="list-disc list-inside">
                    {safetyValidation.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Bias Content Analysis */}
          {biasValidation && (
            <div className="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg border border-purple-200 dark:border-purple-800">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
                <h4 className="font-medium text-purple-900 dark:text-purple-100">
                  Bias Content Analysis
                </h4>
              </div>
              
              {biasValidation.valid && (
                <div className="text-sm text-purple-700 dark:text-purple-300 space-y-1">
                  <p><strong>Format:</strong> {biasValidation.format.toUpperCase()}</p>
                  <p><strong>Total Cases:</strong> {Object.values(biasValidation.counts_by_category).reduce((sum, count) => sum + count, 0)}</p>
                  <p><strong>Required Cases:</strong> {biasValidation.required_count}</p>
                  <p><strong>Categories:</strong> {Object.keys(biasValidation.counts_by_category).join(', ')}</p>
                  <p><strong>Subtypes:</strong> {Object.values(biasValidation.taxonomy).flat().join(', ')}</p>
                </div>
              )}
              
              {biasValidation.errors.length > 0 && (
                <div className="text-sm text-red-700 dark:text-red-300">
                  <p><strong>Errors:</strong></p>
                  <ul className="list-disc list-inside">
                    {biasValidation.errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {biasValidation.warnings.length > 0 && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300">
                  <p><strong>Warnings:</strong></p>
                  <ul className="list-disc list-inside">
                    {biasValidation.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Performance Content Analysis */}
          {perfValidation && (
            <div className="bg-orange-50 dark:bg-orange-900/20 p-4 rounded-lg border border-orange-200 dark:border-orange-800">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-5 h-5 rounded-full bg-orange-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
                <h4 className="font-medium text-orange-900 dark:text-orange-100">
                  Performance Content Analysis
                </h4>
              </div>
              
              {perfValidation.valid && (
                <div className="text-sm text-orange-700 dark:text-orange-300 space-y-1">
                  <p><strong>Format:</strong> {perfValidation.format.toUpperCase()}</p>
                  <p><strong>Total Scenarios:</strong> {Object.values(perfValidation.counts_by_category).reduce((sum, count) => sum + count, 0)}</p>
                  <p><strong>Required Scenarios:</strong> {perfValidation.required_count}</p>
                  <p><strong>Categories:</strong> {Object.keys(perfValidation.counts_by_category).join(', ')}</p>
                  <p><strong>Subtypes:</strong> {Object.values(perfValidation.taxonomy).flat().join(', ')}</p>
                </div>
              )}
              
              {perfValidation.errors.length > 0 && (
                <div className="text-sm text-red-700 dark:text-red-300">
                  <p><strong>Errors:</strong></p>
                  <ul className="list-disc list-inside">
                    {perfValidation.errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {perfValidation.warnings.length > 0 && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300">
                  <p><strong>Warnings:</strong></p>
                  <ul className="list-disc list-inside">
                    {perfValidation.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

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
              { key: 'attacks' as ArtifactType, label: 'Attacks URL', placeholder: 'https://example.com/attacks.yaml' },
              { key: 'safety' as ArtifactType, label: 'Safety URL', placeholder: 'https://example.com/safety.yaml' },
              { key: 'bias' as ArtifactType, label: 'Bias URL', placeholder: 'https://example.com/bias.yaml' },
              { key: 'performance' as ArtifactType, label: 'Performance URL', placeholder: 'https://example.com/perf.yaml' },
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
              { key: 'attacks' as ArtifactType, label: 'Attacks (YAML/JSON)', placeholder: 'cases:\n  - id: "attack1"\n    category: "toxicity"\n    subtype: "explicit"\n    description: "Test case"\n    required: true\n    inputs:\n      user: "Test input"\n    success:\n      must_flag_any: ["toxicity"]' },
              { key: 'safety' as ArtifactType, label: 'Safety (YAML/JSON)', placeholder: 'cases:\n  - id: "safety1"\n    category: "toxicity"\n    subtype: "explicit"\n    description: "Safety test case"\n    required: true\n    inputs:\n      user: "Test input"\n    success:\n      must_flag_any: ["toxicity"]' },
              { key: 'bias' as ArtifactType, label: 'Bias (YAML/JSON)', placeholder: 'cases:\n  - id: "bias1"\n    category: "refusal_rate"\n    subtype: "gender"\n    description: "Gender bias test"\n    required: true\n    prompt_template: "As ${persona}, help me with..."\n    groups:\n      - id: "baseline"\n        persona: "someone"\n      - id: "female"\n        persona: "a woman"' },
              { key: 'performance' as ArtifactType, label: 'Performance (YAML/JSON)', placeholder: 'scenarios:\n  - id: "perf1"\n    category: "cold_start"\n    subtype: "closed_loop"\n    description: "Cold start test"\n    required: true\n    request:\n      input_template: "What is AI?"\n    load:\n      mode: "closed_loop"\n      concurrency: 1\n      duration_sec: 30' },
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
            
            {/* Display warnings if present */}
            {result.warnings && result.warnings.length > 0 && (
              <div>
                <span className="text-sm font-medium">Warnings:</span>
                <div className="mt-1 space-y-1">
                  {result.warnings.map((warning, index) => (
                    <div key={index} className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 px-2 py-1 rounded">
                      {warning}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Display validation stats if present */}
            {result.stats && Object.keys(result.stats).length > 0 && (
              <div>
                <span className="text-sm font-medium">Validation Stats:</span>
                <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(result.stats).map(([key, value]) => (
                    <div key={key} className="flex justify-between bg-slate-50 dark:bg-slate-800 px-2 py-1 rounded">
                      <span className="capitalize">{key.replace(/_/g, ' ')}:</span>
                      <span className="font-mono">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
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
