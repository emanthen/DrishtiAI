import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

const VARIANTS = {
  primary: "bg-signal text-white hover:bg-signal/90 border border-transparent",
  ghost:   "bg-transparent text-steel hover:text-ink dark:hover:text-bone border border-hairline dark:border-hairline-dark",
  danger:  "bg-alert text-white hover:bg-alert/90 border border-transparent",
  outline: "bg-transparent text-ink dark:text-bone border border-hairline dark:border-hairline-dark hover:bg-hairline dark:hover:bg-hairline-dark",
} as const;

const SIZES = {
  sm: "px-3 py-1.5 text-xs rounded",
  md: "px-4 py-2 text-sm rounded",
} as const;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center font-medium transition-colors",
        "disabled:opacity-50 disabled:pointer-events-none",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  ),
);
Button.displayName = "Button";
