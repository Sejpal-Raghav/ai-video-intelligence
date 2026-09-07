import React from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  const baseStyles =
    "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer";

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-2.5 text-base",
  };

  const variantStyles = {
    primary: "bg-blue-600 hover:bg-blue-500 text-white focus-visible:outline-blue-500 shadow-sm",
    secondary: "bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 focus-visible:outline-slate-400",
    danger: "bg-rose-600 hover:bg-rose-500 text-white focus-visible:outline-rose-500 shadow-sm",
    ghost: "bg-transparent hover:bg-slate-800 text-slate-300 hover:text-white focus-visible:outline-slate-400",
  };

  return (
    <button
      disabled={disabled || loading}
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
      {children}
    </button>
  );
}
