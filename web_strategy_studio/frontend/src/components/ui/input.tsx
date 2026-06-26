/**
 * Input — shadcn/ui-style text input.
 */
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          [
            "flex h-9 w-full rounded-md",
            "border border-border bg-background",
            "px-3 py-1 text-sm",
            "text-text-primary placeholder:text-text-muted",
            "transition-colors",
            "file:border-0 file:bg-transparent file:text-sm file:font-medium",
            "focus-visible:outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg",
            "disabled:cursor-not-allowed disabled:opacity-50",
          ].join(" "),
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
