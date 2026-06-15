import type { Recipe } from "../core/types";

export const RECIPES: Record<string, Recipe> = {
  potion: {
    id: "potion",
    name: "Moonpetal Tonic",
    desc: "Brew a calming tonic. Mira the healer will want these.",
    result: "potion",
    resultCount: 1,
    inputs: { herb: 2, water: 1 },
  },
  lantern: {
    id: "lantern",
    name: "Glimlantern",
    desc: "A lantern to light the darkest paths.",
    result: "lantern",
    resultCount: 1,
    inputs: { mushroom: 1, wood: 2 },
  },
  charm: {
    id: "charm",
    name: "Aether Charm",
    desc: "Bind a shard in silk to quiet the ruins.",
    result: "charm",
    resultCount: 1,
    inputs: { crystal: 1, string: 2 },
  },
  bridgeplank: {
    id: "bridgeplank",
    name: "Bound Planks",
    desc: "Lash heartwood with silk to mend the broken bridge.",
    result: "bridgeplank",
    resultCount: 1,
    inputs: { wood: 3, string: 1 },
  },
};

/** Recipes the player knows from the very start. */
export const STARTER_RECIPES = ["potion", "lantern"];
