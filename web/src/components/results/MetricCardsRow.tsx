import { Gauge, MoveDownRight, RotateCw, Wind, Zap } from "lucide-react";
import type { ResultsResponse } from "../../types/api";

interface MetricCardsRowProps {
  results?: ResultsResponse;
}

export default function MetricCardsRow({ results }: MetricCardsRowProps) {
  const metrics = results?.metrics ?? {};
  const cards = [
    {
      label: "Efficiency",
      value: formatPercent(metrics.efficiency),
      tone: efficiencyTone(metrics.efficiency),
      icon: Gauge
    },
    {
      label: "Pressure rise",
      value: formatNumber(metrics.pressure_rise_pa, "Pa"),
      tone: "teal",
      icon: MoveDownRight
    },
    {
      label: "Flow rate",
      value: formatNumber(metrics.flow_rate_m3_s, "m^3/s"),
      tone: "blue",
      icon: Wind
    },
    {
      label: "Power",
      value: formatNumber(metrics.shaft_power_w, "W"),
      tone: "amber",
      icon: Zap
    },
    {
      label: "Torque",
      value: formatNumber(metrics.torque_nm, "N*m"),
      tone: "red",
      icon: RotateCw
    }
  ];

  return (
    <div className="metric-row">
      {cards.map((card) => (
        <article key={card.label} className={`metric-card ${card.tone}`}>
          <card.icon size={18} />
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
    </div>
  );
}

function formatNumber(value: unknown, suffix: string) {
  return typeof value === "number" ? `${value.toPrecision(4)} ${suffix}` : "No data";
}

function formatPercent(value: unknown) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "No data";
}

function efficiencyTone(value: unknown) {
  if (typeof value !== "number") {
    return "neutral";
  }
  if (value >= 0.5) {
    return "teal";
  }
  if (value >= 0.3) {
    return "amber";
  }
  return "red";
}
