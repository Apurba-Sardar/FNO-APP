"use client";

import { ColorType, createChart, LineSeries, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

type Point = { timestamp: string; equity: number; drawdown: number };

export function BacktestChart({ points, field }: { points: Point[]; field: "equity" | "drawdown" }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !points.length) return;
    const chart: IChartApi = createChart(container.current, {
      height: 280,
      width: container.current.clientWidth,
      layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } },
      timeScale: { timeVisible: true },
    });
    const series = chart.addSeries(LineSeries, {
      color: field === "equity" ? "#22d3ee" : "#fb7185",
      lineWidth: 2,
      title: field === "equity" ? "Equity" : "Drawdown",
    });
    series.setData(points.map((point) => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1000) as UTCTimestamp,
      value: point[field],
    })));
    chart.timeScale().fitContent();
    const resize = () => container.current && chart.applyOptions({ width: container.current.clientWidth });
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.remove(); };
  }, [points, field]);
  return <div className="w-full" ref={container} />;
}
