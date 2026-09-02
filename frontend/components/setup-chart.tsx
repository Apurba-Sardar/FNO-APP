"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

type Point = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  ema20: number | null;
  ema50: number | null;
  vwap: number | null;
};
type Levels = {
  entryLow?: number | null;
  entryHigh?: number | null;
  trigger?: number | null;
  stop?: number | null;
  target?: number | null;
  support: number[];
  resistance: number[];
};

export function SetupChart({ points, levels }: { points: Point[]; levels: Levels }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !points.length) return;
    const chart: IChartApi = createChart(container.current, {
      height: 440,
      width: container.current.clientWidth,
      layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#f43f5e",
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
      borderVisible: false,
    });
    const time = (value: string) => Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
    candle.setData(points.map((point) => ({ ...point, time: time(point.timestamp) })));
    (["ema20", "ema50", "vwap"] as const).forEach((field, index) => {
      const line = chart.addSeries(LineSeries, {
        color: ["#22d3ee", "#a78bfa", "#fbbf24"][index],
        lineWidth: 1,
        title: field.toUpperCase(),
      });
      line.setData(
        points
          .filter((point) => point[field] != null)
          .map((point) => ({ time: time(point.timestamp), value: point[field] as number })),
      );
    });
    const priceLines: Array<[number | null | undefined, string, string]> = [
      [levels.entryLow, "Entry low", "#38bdf8"],
      [levels.entryHigh, "Entry high", "#38bdf8"],
      [levels.trigger, "Trigger", "#facc15"],
      [levels.stop, "Stop (hypothetical)", "#fb7185"],
      [levels.target, "Target (hypothetical)", "#34d399"],
      ...levels.support.map((value): [number, string, string] => [value, "Potential support", "#0f766e"]),
      ...levels.resistance.map((value): [number, string, string] => [value, "Potential resistance", "#7c3aed"]),
    ];
    priceLines.forEach(([price, title, color]) => {
      if (price != null) candle.createPriceLine({ price, title, color, lineWidth: 1, axisLabelVisible: true });
    });
    chart.timeScale().fitContent();
    const resize = () => container.current && chart.applyOptions({ width: container.current.clientWidth });
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [points, levels]);
  return <div className="w-full" ref={container} />;
}
