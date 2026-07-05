import { cn } from "@/lib/utils";
import { forwardRef, InputHTMLAttributes, SelectHTMLAttributes } from "react";

const baseCls =
  "w-full rounded-[4px] border border-hairline dark:border-hairline-dark bg-white dark:bg-ink " +
  "px-3 py-2 text-sm text-ink dark:text-bone placeholder:text-steel/60 " +
  "focus:outline-none focus:ring-1 focus:ring-signal disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(baseCls, className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn(baseCls, "cursor-pointer", className)} {...props}>
      {children}
    </select>
  ),
);
Select.displayName = "Select";
