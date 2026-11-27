import React, { useId } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  leftIcon,
  rightIcon,
  className = '',
  id,
  ...props
}) => {
  const generatedId = useId();
  const inputId = id || props.name || generatedId;

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-ink-primary">
          {label}
        </label>
      )}
      <div className="relative rounded-[10px]">
        {leftIcon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-secondary">
            {leftIcon}
          </div>
        )}
        <input
          id={inputId}
          className={`lf-control block w-full py-2.5 text-sm ${
            error
              ? 'border-status-danger-solid focus:border-status-danger-solid'
              : ''
          } ${leftIcon ? 'pl-10' : 'pl-3.5'} ${rightIcon ? 'pr-10' : 'pr-3.5'} ${className}`}
          {...props}
        />
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center text-ink-secondary">
            {rightIcon}
          </div>
        )}
      </div>
      {error && <p className="text-xs text-status-danger-text">{error}</p>}
      {helperText && !error && <p className="text-xs text-ink-secondary">{helperText}</p>}
    </div>
  );
};
