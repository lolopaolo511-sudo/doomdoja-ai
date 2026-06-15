import type { GameState, Recipe } from "../core/types";
import { RECIPES } from "../data/recipes";
import { Inventory } from "./Inventory";

export const Crafting = {
  knownRecipes(s: GameState): Recipe[] {
    return s.knownRecipes.map((id) => RECIPES[id]).filter(Boolean);
  },

  canCraft(s: GameState, recipeId: string): boolean {
    const r = RECIPES[recipeId];
    if (!r) return false;
    return Object.entries(r.inputs).every(([id, n]) => Inventory.has(s, id, n));
  },

  /** Consumes inputs, adds the result, and records a lifetime craft counter. */
  craft(s: GameState, recipeId: string): boolean {
    const r = RECIPES[recipeId];
    if (!r || !this.canCraft(s, recipeId)) return false;
    for (const [id, n] of Object.entries(r.inputs)) Inventory.remove(s, id, n);
    Inventory.add(s, r.result, r.resultCount);
    s.flags[`crafted_${r.result}`] =
      ((s.flags[`crafted_${r.result}`] as number) ?? 0) + r.resultCount;
    return true;
  },

  learn(s: GameState, recipeId: string): void {
    if (!s.knownRecipes.includes(recipeId)) s.knownRecipes.push(recipeId);
  },
};
