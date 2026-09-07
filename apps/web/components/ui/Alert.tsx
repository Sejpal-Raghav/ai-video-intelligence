import React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";

interface AlertProps {
  variant?: "info" | "warning" | "danger" | "success";
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function Alert({ variant = "info", title, children, className = "" }: AlertProps) {
  const styles = {
    info: {
      bg: "bg-blue-950/40 border-blue-800 text-blue-200",
      icon: <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />,
    },
    warning: {
      bg: "bg-amber-950/40 border-amber-800 text-amber-200",
      icon: <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />,
    },
    danger: {
      bg: "bg-rose-950/40 border-rose-800 text-rose-200",
      icon: <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />,
    },
    success: {
      bg: "bg-emerald-950/40 border-emerald-800 text-emerald-200",
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />,
    },
  };

  const current = styles[variant];

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 p-4 rounded-lg border text-sm ${current.bg} ${className}`}
    >
      {current.icon}
      <div>
        {title && <h5 className="font-semibold mb-1">{title}</h5>}
        <div className="text-xs leading-relaxed">{children}</div>
      </div>
    </div>
  );
}
