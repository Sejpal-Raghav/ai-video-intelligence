import React from "react";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "low" | "medium" | "high" | "critical" | "neutral" | "success" | "warning";
  size?: "sm" | "md";
}

export function Badge({ children, variant = "neutral", size = "sm" }: BadgeProps) {
  const sizeStyles = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-sm",
  };

  const variantStyles = {
    low: "bg-blue-950/80 text-blue-300 border border-blue-800",
    medium: "bg-amber-950/80 text-amber-300 border border-amber-800",
    high: "bg-orange-950/80 text-orange-300 border border-orange-800",
    critical: "bg-rose-950/80 text-rose-300 border border-rose-800 animate-pulse",
    neutral: "bg-slate-800 text-slate-300 border border-slate-700",
    success: "bg-emerald-950/80 text-emerald-300 border border-emerald-800",
    warning: "bg-yellow-950/80 text-yellow-300 border border-yellow-800",
  };

  return (
    <span
      className={`inline-flex items-center font-semibold rounded-md uppercase tracking-wider ${sizeStyles[size]} ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
}

export function RiskBadge({ tier }: { tier: string }) {
  const mapping: Record<string, "low" | "medium" | "high" | "critical"> = {
    LOW: "low",
    MEDIUM: "medium",
    HIGH: "high",
    CRITICAL: "critical",
  };
  const variant = mapping[tier.toUpperCase()] || "neutral";
  return <Badge variant={variant}>Risk: {tier}</Badge>;
}

export function VerdictBadge({ verdict }: { verdict: string }) {
  if (verdict === "CONFIRMED_RISK") {
    return <Badge variant="warning">Human-Confirmed Risk</Badge>;
  }
  if (verdict === "REJECTED") {
    return <Badge variant="neutral">Rejected</Badge>;
  }
  if (verdict === "UNCERTAIN") {
    return <Badge variant="low">Uncertain</Badge>;
  }
  return <Badge variant="neutral">{verdict}</Badge>;
}
