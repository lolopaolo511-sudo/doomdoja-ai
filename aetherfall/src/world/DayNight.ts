import type { Phase, GameState } from "../core/types";
import { MINUTES_PER_DAY } from "../core/constants";

/** Phase boundaries in minutes-since-midnight (clock is offset so 0 == 06:00). */
export function phaseOf(clock: number): Phase {
  const m = ((clock % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY;
  const hour = m / 60;
  if (hour >= 5 && hour < 8) return "dawn";
  if (hour >= 8 && hour < 18) return "day";
  if (hour >= 18 && hour < 21) return "dusk";
  return "night";
}

export function phaseOfState(s: GameState): Phase {
  return phaseOf(s.clock);
}

export function isNight(s: GameState): boolean {
  return phaseOfState(s) === "night";
}

export function isDark(s: GameState): boolean {
  const p = phaseOfState(s);
  return p === "night" || p === "dusk";
}

/** Format the clock as HH:MM. */
export function formatClock(clock: number): string {
  const m = Math.floor(((clock % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY);
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh.toString().padStart(2, "0")}:${mm.toString().padStart(2, "0")}`;
}

const PHASE_LABEL: Record<Phase, string> = {
  dawn: "Dawn",
  day: "Day",
  dusk: "Dusk",
  night: "Night",
};

export function phaseLabel(p: Phase): string {
  return PHASE_LABEL[p];
}

/**
 * Returns a 0..1 darkness factor and an overlay color for the lighting pass.
 * 0 = full daylight, ~0.62 = deep night.
 */
export function lightingFor(clock: number): { darkness: number; tint: string } {
  const m = ((clock % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY;
  const hour = m / 60;

  // Smooth piecewise curve over the day.
  let darkness: number;
  let tint: string;
  if (hour < 5) {
    darkness = 0.6;
    tint = "#0a1230";
  } else if (hour < 8) {
    // dawn: 5->8 brighten, warm tint
    const t = (hour - 5) / 3;
    darkness = 0.6 - 0.6 * t;
    tint = "#ff9d5c";
  } else if (hour < 17) {
    darkness = 0;
    tint = "#fff4d6";
  } else if (hour < 18) {
    darkness = 0.05;
    tint = "#ffd28a";
  } else if (hour < 21) {
    // dusk: 18->21 darken, warm->cool
    const t = (hour - 18) / 3;
    darkness = 0.05 + 0.55 * t;
    tint = "#a14e6e";
  } else {
    darkness = 0.6;
    tint = "#0a1230";
  }
  return { darkness, tint };
}
