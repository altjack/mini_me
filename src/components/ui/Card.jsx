import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility function to merge class names
 */
function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Card component - replacement for @tremor/react Card
 * Supports decoration prop for top border color
 */
export const Card = React.forwardRef(({
  children,
  className,
  decoration,
  decorationColor,
  ...props
}, ref) => {
  // Map decoration colors to Tailwind classes
  const colorMap = {
    blue: 'border-t-blue-500',
    emerald: 'border-t-emerald-500',
    green: 'border-t-green-500',
    violet: 'border-t-violet-500',
    purple: 'border-t-purple-500',
    red: 'border-t-red-500',
    amber: 'border-t-amber-500',
    orange: 'border-t-orange-500',
    gray: 'border-t-gray-500',
  };

  const decorationClass = decoration === 'top' && decorationColor
    ? `border-t-4 ${colorMap[decorationColor] || 'border-t-blue-500'}`
    : '';

  return (
    <div
      ref={ref}
      className={cn(
        'bg-white rounded-xl shadow-sm border border-gray-100 p-6',
        decorationClass,
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

/**
 * Title component - replacement for @tremor/react Title
 * Renders as h3 by default with appropriate styling
 */
export const Title = React.forwardRef(({
  children,
  className,
  as: Component = 'h3',
  ...props
}, ref) => {
  return (
    <Component
      ref={ref}
      className={cn(
        'text-lg font-semibold text-gray-900',
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
});

Title.displayName = 'Title';

/**
 * Text component - replacement for @tremor/react Text
 * Renders as p by default with muted styling
 */
export const Text = React.forwardRef(({
  children,
  className,
  as: Component = 'p',
  ...props
}, ref) => {
  return (
    <Component
      ref={ref}
      className={cn(
        'text-sm text-gray-500',
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
});

Text.displayName = 'Text';

export default Card;

