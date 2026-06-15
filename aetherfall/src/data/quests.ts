import type { QuestDef } from "../core/types";

export const QUESTS: Record<string, QuestDef> = {
  tonics: {
    id: "tonics",
    title: "A Healer's Request",
    giver: "Mira",
    summary:
      "Mira the healer is out of moonpetal tonic. Gather moonpetal herbs from the forest at night, brew tonic, and bring her two.",
    objectives: [
      { id: "gather", text: "Gather 4 Moonpetal Herbs (they glow at night)" },
      { id: "brew", text: "Brew 2 Moonpetal Tonics (open Crafting)" },
      { id: "deliver", text: "Bring 2 tonics to Mira in the village" },
    ],
    reward: { crystal: 1, water: 2 },
  },

  locket: {
    id: "locket",
    title: "The Lost Locket",
    giver: "Old Bertram",
    summary:
      "Bertram lost his late wife's silver locket somewhere in the ancient forest. Find it and bring it back to him.",
    objectives: [
      { id: "find", text: "Search the ancient forest for the silver locket" },
      { id: "return", text: "Return the locket to Bertram" },
    ],
    reward: { string: 3 },
  },

  bridge: {
    id: "bridge",
    title: "The Broken Bridge",
    giver: "Garrin",
    summary:
      "The bridge to the misty clearing collapsed. Garrin the carpenter needs bound planks to mend it. Craft them and repair the bridge in the forest.",
    objectives: [
      { id: "craft", text: "Craft Bound Planks (3 Heartwood + 1 Spider Silk)" },
      { id: "repair", text: "Repair the broken bridge in the forest" },
    ],
    reward: { crystal: 1, wood: 2 },
    unlocks: "letter",
  },

  ruins: {
    id: "ruins",
    title: "Echoes in the Ruins",
    giver: "Selene",
    summary:
      "Selene the scholar studies the old stone ruins, but restless echoes drown out their voice. Craft an Aether Charm and place it on the ruined shrine to quiet them.",
    objectives: [
      { id: "shards", text: "Find an Aether Shard in the ruins" },
      { id: "silk", text: "Gather Spider Silk in the ruins" },
      { id: "charm", text: "Craft an Aether Charm (1 Shard + 2 Silk)" },
      { id: "place", text: "Place the charm on the shrine in the ruins" },
    ],
    reward: { crystal: 2 },
  },

  letter: {
    id: "letter",
    title: "A Letter for the Hermit",
    giver: "Garrin",
    summary:
      "With the bridge mended, Garrin asks you to carry a sealed letter to the hermit who lives in the misty clearing.",
    objectives: [
      { id: "deliver", text: "Deliver the sealed letter to the hermit Caedry" },
      { id: "reply", text: "Return Caedry's answer to Garrin" },
    ],
    reward: { crystal: 2, potion: 1 },
  },
};
