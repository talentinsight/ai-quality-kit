import React from 'react';
import { RequirementRow, SuiteStatus } from '../lib/requirementStatus';
import { Upload } from 'lucide-react';

interface RequirementsMatrixProps {
  rows: RequirementRow[];
  onUploadClick?: (kind: string) => void;
  compact?: boolean;
}

const getStatusBadge = (status: SuiteStatus, blocking: boolean) => {
  const baseClasses = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium";
  
  switch (status) {
    case 'provided':
      return `${baseClasses} bg-green-50 text-green-700 border-green-200`;
    case 'using_defaults':
      return `${baseClasses} bg-gray-50 text-gray-700 border-gray-200`;
    case 'missing':
      return `${baseClasses} bg-red-50 text-red-700 border-red-200 ${blocking ? 'ring-1 ring-red-300' : ''}`;
    case 'not_used':
      return `${baseClasses} bg-slate-50 text-slate-500 border-slate-200`;
    default:
      return `${baseClasses} bg-gray-50 text-gray-700 border-gray-200`;
  }
};

const getStatusText = (status: SuiteStatus, blocking: boolean) => {
  switch (status) {
    case 'provided':
      return 'Provided';
    case 'using_defaults':
      return 'Using defaults';
    case 'missing':
      return blocking ? 'Missing (Blocking)' : 'Missing';
    case 'not_used':
      return 'Not used';
    default:
      return status;
  }
};

const RequirementsMatrix: React.FC<RequirementsMatrixProps> = ({ 
  rows, 
  onUploadClick,
  compact = false 
}) => {
  if (rows.length === 0) {
    return (
      <div className="text-sm text-gray-500 text-center py-4">
        No test suites selected
      </div>
    );
  }

  if (compact) {
    // Compact view for config panel
    return (
      <div className="space-y-2">
        <div className="space-y-1">
          {rows.map((row, index) => (
            <div key={`${row.suite}-${row.kind}-${index}`} className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 min-w-0 flex-1">
                <span className="text-gray-600 truncate">{row.suite}</span>
                <span className="text-gray-400">→</span>
                <span className="text-gray-700 font-medium">{row.kind}</span>
              </div>
              <div className="flex items-center space-x-1 flex-shrink-0">
                <span className={getStatusBadge(row.status, row.blocking)}>
                  {row.status === 'provided' ? '✓' : 
                   row.status === 'missing' ? '✗' :
                   row.status === 'using_defaults' ? '○' : '—'}
                </span>
                {row.status === 'missing' && onUploadClick && (
                  <button
                    onClick={() => onUploadClick(row.kind)}
                    className="p-1 text-blue-500 hover:text-blue-700 rounded"
                    title="Upload now"
                  >
                    <Upload size={12} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        {rows.some(r => r.blocking) && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
            ⚠ Missing required data. Enable defaults or upload files.
          </div>
        )}
      </div>
    );
  }

  // Full table view for modal
  return (
    <div className="rounded-2xl border bg-white shadow-sm p-3">
      <div className="mb-3">
        <h3 className="text-lg font-semibold text-gray-900">Test Data Requirements Matrix</h3>
        <p className="text-sm text-gray-600 mt-1">
          Required data for selected test suites. Missing required items will block execution unless defaults are enabled.
        </p>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-50 border-b">
            <tr>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Suite</th>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Data Kind</th>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Level</th>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Status</th>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Details</th>
              <th className="text-left py-2 px-3 font-medium text-gray-900">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {rows.map((row, index) => (
              <tr key={`${row.suite}-${row.kind}-${index}`} className="hover:bg-gray-50">
                <td className="py-2 px-3 font-medium text-gray-900">{row.suite}</td>
                <td className="py-2 px-3 text-gray-700">{row.kind}</td>
                <td className="py-2 px-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                    row.level === 'required' 
                      ? 'bg-orange-100 text-orange-800' 
                      : row.level === 'optional'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {row.level}
                  </span>
                </td>
                <td className="py-2 px-3">
                  <span className={getStatusBadge(row.status, row.blocking)}>
                    {getStatusText(row.status, row.blocking)}
                  </span>
                </td>
                <td className="py-2 px-3 text-gray-600">
                  {row.details || '-'}
                </td>
                <td className="py-2 px-3">
                  {row.status === 'missing' && onUploadClick && (
                    <button
                      onClick={() => onUploadClick(row.kind)}
                      className="inline-flex items-center space-x-1 text-xs text-blue-600 hover:text-blue-800"
                    >
                      <Upload size={14} />
                      <span>Upload now</span>
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {rows.some(r => r.blocking) && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start space-x-2">
            <div className="w-2 h-2 bg-red-500 rounded-full mt-1.5"></div>
            <div className="text-sm text-red-700">
              <strong>Execution blocked:</strong> Missing required data for selected suite(s). 
              Upload the items marked Missing or enable 'Allow default datasets'.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RequirementsMatrix;
