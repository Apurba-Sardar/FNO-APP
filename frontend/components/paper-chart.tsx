"use client";

import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

export function PaperChart({ points, field, color = "#22d3ee" }: { points: Array<{ timestamp: string; [key: string]: string | number }>; field: string; color?: string }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !points.length) return;
    const chart = createChart(container.current, { height: 220, width: container.current.clientWidth, layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#94a3b8" }, grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } }, timeScale: { timeVisible: true } });
    const series = chart.addSeries(LineSeries, { color, lineWidth: 2, title: field });
    series.setData(points.map((point) => ({ time: Math.floor(new Date(point.timestamp).getTime() / 1000) as UTCTimestamp, value: Number(point[field] ?? 0) })));
    chart.timeScale().fitContent();
    const resize = () => container.current && chart.applyOptions({ width: container.current.clientWidth });
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.remove(); };
  }, [points, field, color]);
  return <div ref={container} className="w-full" />;
}
