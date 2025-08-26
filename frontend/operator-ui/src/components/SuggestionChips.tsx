import React from 'react';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled?: boolean;
}

const SuggestionChips: React.FC<SuggestionChipsProps> = ({ 
  suggestions, 
  onSelect, 
  disabled = false 
}) => {
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className={`inline-flex items-center rounded-2xl border px-4 py-2 text-sm font-medium transition-all duration-200 ${
            disabled
              ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 cursor-pointer shadow-sm hover:shadow-md'
          }`}
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
};

export default SuggestionChips;
