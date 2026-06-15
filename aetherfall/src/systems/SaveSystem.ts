import type { GameState } from "../core/types";
import { SAVE_KEY, SAVE_VERSION } from "../core/constants";

export const SaveSystem = {
  hasSave(): boolean {
    try {
      return localStorage.getItem(SAVE_KEY) != null;
    } catch {
      return false;
    }
  },

  save(state: GameState): boolean {
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify(state));
      return true;
    } catch (e) {
      console.warn("Aetherfall: failed to save", e);
      return false;
    }
  },

  load(): GameState | null {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw) as GameState;
      if (typeof data.version !== "number" || data.version > SAVE_VERSION) {
        console.warn("Aetherfall: incompatible save version");
        return null;
      }
      return data;
    } catch (e) {
      console.warn("Aetherfall: failed to load", e);
      return null;
    }
  },

  clear(): void {
    try {
      localStorage.removeItem(SAVE_KEY);
    } catch {
      /* ignore */
    }
  },
};
