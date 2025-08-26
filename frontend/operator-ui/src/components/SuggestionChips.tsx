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
  console.log('SuggestionChips rendered with suggestions:', suggestions, 'disabled:', disabled);
  
  if (suggestions.length === 0) {
    console.log('No suggestions, returning null');
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className={`inline-flex items-center rounded-full border px-3 py-1 text-sm mr-2 mb-2 transition-colors ${
            disabled
              ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400 cursor-pointer'
          }`}
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
};

export default SuggestionChips;
