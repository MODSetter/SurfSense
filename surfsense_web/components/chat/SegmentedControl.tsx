import React from 'react';

type SegmentedControlProps<T extends string> = {
  value: T;
  onChange: (value: T) => void;
  options: Array<{
    value: T;
    label: string;
    icon: React.ReactNode;
  }>;
};

/**
 * A segmented control component for selecting between different options
 */
function SegmentedControl<T extends string>({ value, onChange, options }: SegmentedControlProps<T>) {
  return (
    <div className="flex rounded-md border border-border overflow-hidden scale-90 origin-left">
      {options.map((option) => (
        <button
          key={option.value}
          className={`flex items-center gap-1 px-2 py-1 text-xs transition-colors ${
            value === option.value 
              ? 'bg-primary text-primary-foreground' 
              : 'hover:bg-muted'
          }`}
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
        >
          {option.icon}
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}

export default SegmentedControl; 