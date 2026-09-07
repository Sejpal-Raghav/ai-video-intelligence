import React from "react";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";
import { Button } from "./Button";

export type AsyncState = "idle" | "loading" | "success-empty" | "success-with-data" | "error";

interface StateWrapperProps {
  state: AsyncState;
  errorMessage?: string;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyMessage?: string;
  emptyAction?: React.ReactNode;
  children: React.ReactNode;
}

export function StateWrapper({
  state,
  errorMessage = "An unexpected error occurred while loading data.",
  onRetry,
  emptyTitle = "No data available",
  emptyMessage = "There are no records matching your query.",
  emptyAction,
  children,
}: StateWrapperProps) {
  if (state === "idle") {
    return <div className="py-12 text-center text-sm text-slate-500">Ready to load</div>;
  }

  if (state === "loading") {
    return (
      <div className="py-16 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="text-sm font-medium text-slate-400">Loading data...</span>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="p-6 rounded-xl border border-rose-900/50 bg-rose-950/20 text-center flex flex-col items-center gap-3 my-4">
        <AlertCircle className="w-8 h-8 text-rose-400" />
        <h4 className="text-base font-semibold text-rose-200">Unable to load data</h4>
        <p className="text-xs text-rose-300 max-w-md">{errorMessage}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry} className="mt-2">
            Try again
          </Button>
        )}
      </div>
    );
  }

  if (state === "success-empty") {
    return (
      <div className="py-16 rounded-xl border border-dashed border-slate-800 flex flex-col items-center justify-center gap-3 text-center">
        <Inbox className="w-10 h-10 text-slate-600" />
        <h4 className="text-base font-medium text-slate-300">{emptyTitle}</h4>
        <p className="text-xs text-slate-500 max-w-sm">{emptyMessage}</p>
        {emptyAction && <div className="mt-2">{emptyAction}</div>}
      </div>
    );
  }

  // success-with-data
  return <>{children}</>;
}
