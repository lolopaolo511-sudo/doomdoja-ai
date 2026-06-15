import type { GameState, QuestDef } from "../core/types";
import { QUESTS } from "../data/quests";
import { Inventory } from "./Inventory";

const num = (s: GameState, k: string) => (s.flags[k] as number) ?? 0;
const bool = (s: GameState, k: string) => Boolean(s.flags[k]);

/** Rules that decide when each objective is satisfied. */
const OBJECTIVE_RULES: Record<string, (s: GameState) => boolean> = {
  "tonics.gather": (s) => num(s, "got_herb") >= 4,
  "tonics.brew": (s) => num(s, "crafted_potion") >= 2,
  "tonics.deliver": (s) => bool(s, "tonics_delivered"),

  "locket.find": (s) => Inventory.has(s, "locket") || bool(s, "locket_returned"),
  "locket.return": (s) => bool(s, "locket_returned"),

  "bridge.craft": (s) => num(s, "crafted_bridgeplank") >= 1 || bool(s, "bridgeRepaired"),
  "bridge.repair": (s) => bool(s, "bridgeRepaired"),

  "ruins.shards": (s) => num(s, "got_crystal") >= 1,
  "ruins.silk": (s) => num(s, "got_string") >= 1,
  "ruins.charm": (s) => num(s, "crafted_charm") >= 1 || bool(s, "charmPlaced"),
  "ruins.place": (s) => bool(s, "charmPlaced"),

  "letter.deliver": (s) => bool(s, "letter_delivered"),
  "letter.reply": (s) => bool(s, "letter_replied"),
};

export const QuestSystem = {
  start(s: GameState, id: string): boolean {
    const q = s.quests[id];
    if (!q || q.status === "active" || q.status === "complete") return false;
    q.status = "active";
    return true;
  },

  /** Recompute objective completion for every active quest. */
  refresh(s: GameState): void {
    for (const id of Object.keys(s.quests)) {
      const q = s.quests[id];
      if (q.status !== "active") continue;
      const def = QUESTS[id];
      for (const obj of def.objectives) {
        const rule = OBJECTIVE_RULES[`${id}.${obj.id}`];
        if (rule && rule(s)) q.done[obj.id] = true;
      }
    }
  },

  allObjectivesDone(s: GameState, id: string): boolean {
    const def = QUESTS[id];
    return def.objectives.every((o) => s.quests[id]?.done[o.id]);
  },

  /** Mark complete, grant rewards once, and unlock any follow-up quest. */
  complete(s: GameState, id: string): QuestDef | null {
    const q = s.quests[id];
    if (!q || q.status === "complete") return null;
    const def = QUESTS[id];
    // Ensure objectives read as done in the log.
    for (const o of def.objectives) q.done[o.id] = true;
    q.status = "complete";
    for (const [item, n] of Object.entries(def.reward)) Inventory.add(s, item, n);
    if (def.unlocks && s.quests[def.unlocks] && s.quests[def.unlocks].status === "locked") {
      s.quests[def.unlocks].status = "available";
    }
    return def;
  },

  active(s: GameState): QuestDef[] {
    return Object.keys(s.quests)
      .filter((id) => s.quests[id].status === "active")
      .map((id) => QUESTS[id]);
  },

  completed(s: GameState): QuestDef[] {
    return Object.keys(s.quests)
      .filter((id) => s.quests[id].status === "complete")
      .map((id) => QUESTS[id]);
  },
};
