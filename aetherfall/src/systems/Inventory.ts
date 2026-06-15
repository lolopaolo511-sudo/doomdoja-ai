import type { GameState } from "../core/types";

export const Inventory = {
  count(s: GameState, id: string): number {
    return s.inventory[id] ?? 0;
  },

  has(s: GameState, id: string, n = 1): boolean {
    return this.count(s, id) >= n;
  },

  add(s: GameState, id: string, n = 1): void {
    s.inventory[id] = this.count(s, id) + n;
    // Track lifetime gather/acquire counters for quest objectives.
    s.flags[`got_${id}`] = ((s.flags[`got_${id}`] as number) ?? 0) + n;
  },

  /** Remove up to n; returns true only if there was enough. */
  remove(s: GameState, id: string, n = 1): boolean {
    const have = this.count(s, id);
    if (have < n) return false;
    const left = have - n;
    if (left <= 0) delete s.inventory[id];
    else s.inventory[id] = left;
    return true;
  },

  /** Total number of distinct item stacks. */
  size(s: GameState): number {
    return Object.keys(s.inventory).length;
  },

  entries(s: GameState): Array<[string, number]> {
    return Object.entries(s.inventory).filter(([, n]) => n > 0);
  },
};
