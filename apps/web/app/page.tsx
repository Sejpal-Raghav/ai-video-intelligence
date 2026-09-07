"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  UploadCloud,
  Camera,
  PlayCircle,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Activity,
  ArrowRight,
  RefreshCw,
  Layers,
  AlertTriangle,
  Film,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { api, ProblemDetails } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Badge, RiskBadge, VerdictBadge } from "@/components/ui/Badge";
import { StateWrapper, AsyncState } from "@/components/ui/StateWrapper";
import type { components } from "@/lib/schema";

type AnalyticsSummary = components["schemas"]["AnalyticsSummary"];
type RunDetail = components["schemas"]["RunDetail"];

const TIER_CHART_COLORS: Record<string, string> = {
  CRITICAL: "#f43f5e",
  HIGH: "#f97316",
  MEDIUM: "#f59e0b",
  LOW: "#3b82f6",
};

const VERDICT_CHART_COLORS: Record<string, string> = {
  CONFIRMED_RISK: "#f43f5e",
  REJECTED: "#10b981",
  UNCERTAIN: "#8b5cf6",
  UNREVIEWED: "#64748b",
};

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [recentRuns, setRecentRuns] = useState<RunDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [summaryData, runsData] = await Promise.all([
        api.getAnalyticsSummary({}),
        api.getRuns(10),
      ]);
      setAnalytics(summaryData);
      setRecentRuns(runsData);
      setError(null);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  let state: AsyncState = "loading";
  if (!loading) {
    if (error && !analytics) {
      state = "error";
    } else {
      state = "success-with-data";
    }
  }

  // Format chart data
  const tierData = (analytics?.by_risk_tier || []).map((item) => ({
    name: item.key,
    count: item.count,
    color: TIER_CHART_COLORS[item.key] || "#94a3b8",
  }));

  const typeData = (analytics?.by_event_type || []).map((item) => ({
    name: item.key.replace(/_/g, " "),
    count: item.count,
  }));

  const verdictData = (analytics?.by_review_verdict || []).map((item) => ({
    name:
      item.key === "CONFIRMED_RISK"
        ? "Confirmed Risk"
        : item.key === "REJECTED"
        ? "Rejected"
        : item.key === "UNCERTAIN"
        ? "Uncertain"
        : item.key,
    count: item.count,
    color: VERDICT_CHART_COLORS[item.key] || "#94a3b8",
  }));

  const reviewRate =
    analytics && analytics.event_count > 0
      ? Math.round((analytics.reviewed_count / analytics.event_count) * 100)
      : 0;

  const totalMinutes = analytics ? Math.round(analytics.total_source_duration_ms / 60000) : 0;

  return (
    <StateWrapper state={state} errorMessage={error || ""} onRetry={fetchDashboardData}>
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
              <Activity className="w-7 h-7 text-blue-500" />
              Warehouse Video Intelligence Dashboard
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Surveillance quality assurance, automated physical risk detection, and audit review portal.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <Link href="/settings/camera">
              <Button variant="secondary" size="md" className="flex items-center gap-1.5">
                <Camera className="w-4 h-4" />
                Camera Setup
              </Button>
            </Link>
            <Link href="/upload">
              <Button variant="primary" size="md" className="flex items-center gap-1.5">
                <UploadCloud className="w-4 h-4" />
                Upload Video
              </Button>
            </Link>
            <Button
              variant="ghost"
              size="md"
              onClick={fetchDashboardData}
              className="p-2"
              title="Refresh Data"
            >
              <RefreshCw className="w-4 h-4 text-slate-400" />
            </Button>
          </div>
        </div>

        {/* Mandatory Operational Disclaimers (Blueprint §16.2) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/50 text-slate-300 flex items-center gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong className="text-slate-200">Mandatory Context: </strong>
              Risk event, not confirmed damage. All automated findings are subject to human verification.
            </span>
          </div>
          <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/50 text-slate-300 flex items-center gap-2.5">
            <Activity className="w-4 h-4 text-blue-400 shrink-0" />
            <span>
              <strong className="text-slate-200">Evidence Indicator: </strong>
              Evidence quality is not probability. Numerical scores reflect tracking and signal integrity.
            </span>
          </div>
        </div>

        {/* KPI Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2 uppercase">
              <span>Total Runs</span>
              <Film className="w-4 h-4 text-blue-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">{recentRuns.length}</div>
            <div className="text-[11px] text-slate-500 mt-1">Surveillance sessions</div>
          </Card>

          <Card>
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2 uppercase">
              <span>Detected Events</span>
              <AlertTriangle className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {analytics?.event_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Across all active runs</div>
          </Card>

          <Card>
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2 uppercase">
              <span>Human Reviewed</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {analytics?.reviewed_count ?? 0}{" "}
              <span className="text-xs font-normal text-slate-400">({reviewRate}%)</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Audit verification progress</div>
          </Card>

          <Card>
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2 uppercase">
              <span>Duration Analyzed</span>
              <Clock className="w-4 h-4 text-violet-500" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {totalMinutes} <span className="text-xs font-normal text-slate-400">min</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Total video footage ingested</div>
          </Card>
        </div>

        {/* Recharts Visual Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chart 1: Risk Tier Breakdown */}
          <Card>
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              Events by Risk Tier
            </h3>
            {tierData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-xs text-slate-500">
                No events recorded
              </div>
            ) : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tierData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        borderColor: "#334155",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {tierData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          {/* Chart 2: Event Type Distribution */}
          <Card>
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-400" />
              Events by Category
            </h3>
            {typeData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-xs text-slate-500">
                No events recorded
              </div>
            ) : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={typeData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis
                      dataKey="name"
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      interval={0}
                      angle={-15}
                      textAnchor="end"
                    />
                    <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        borderColor: "#334155",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          {/* Chart 3: Human Review Verdicts */}
          <Card>
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Review Audit Status
            </h3>
            {verdictData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-xs text-slate-500">
                No reviews recorded
              </div>
            ) : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={verdictData}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={4}
                    >
                      {verdictData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        borderColor: "#334155",
                        fontSize: 12,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>

        {/* Recent Runs Table */}
        <Card>
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div>
              <h3 className="text-base font-semibold text-slate-100">Recent Analysis Runs</h3>
              <p className="text-xs text-slate-400">
                Surveillance pipeline executions, background worker jobs, and evidence manifests.
              </p>
            </div>
            <Link href="/upload">
              <Button variant="secondary" size="sm" className="text-xs flex items-center gap-1">
                + New Analysis
              </Button>
            </Link>
          </div>

          {recentRuns.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
              No runs recorded in database. Upload a surveillance video to begin analysis.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px]">
                    <th className="pb-3 font-semibold">Run ID</th>
                    <th className="pb-3 font-semibold">Mode</th>
                    <th className="pb-3 font-semibold">Camera Profile</th>
                    <th className="pb-3 font-semibold">Status</th>
                    <th className="pb-3 font-semibold">Started At</th>
                    <th className="pb-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {recentRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 font-mono font-medium text-slate-200">
                        <Link href={`/runs/${r.id}`} className="hover:text-blue-400 transition-colors">
                          #{r.id.slice(0, 8)}
                        </Link>
                      </td>
                      <td className="py-3">
                        <Badge variant={r.mode === "LIVE" ? "success" : "warning"}>
                          {r.mode}
                        </Badge>
                      </td>
                      <td className="py-3 text-slate-300">
                        {r.camera_profile_id} (v{r.camera_profile_version})
                      </td>
                      <td className="py-3">
                        <Badge
                          variant={
                            r.status === "SUCCEEDED"
                              ? "success"
                              : r.status === "RUNNING"
                              ? "medium"
                              : r.status === "FAILED"
                              ? "critical"
                              : "neutral"
                          }
                        >
                          {r.status}
                        </Badge>
                      </td>
                      <td className="py-3 text-slate-400 font-mono text-[11px]">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 text-right">
                        <Link href={`/runs/${r.id}`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs text-blue-400 hover:text-blue-300 p-1 h-auto"
                          >
                            View Run <ArrowRight className="w-3.5 h-3.5 ml-1 inline" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </StateWrapper>
  );
}
