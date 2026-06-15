import type { ItemDef } from "../core/types";

export const ITEMS: Record<string, ItemDef> = {
  herb: {
    id: "herb",
    name: "Moonpetal Herb",
    desc: "A pale herb that only glows after dark. Smells faintly of rain.",
    glyph: "🌿",
    color: "#7fe3a0",
    stackable: true,
  },
  mushroom: {
    id: "mushroom",
    name: "Glimcap Mushroom",
    desc: "A bioluminescent cap found among old roots.",
    glyph: "🍄",
    color: "#e08bb0",
    stackable: true,
  },
  crystal: {
    id: "crystal",
    name: "Aether Shard",
    desc: "A humming fragment of fallen sky-stone. Warm to the touch.",
    glyph: "💎",
    color: "#8ad8ff",
    stackable: true,
  },
  wood: {
    id: "wood",
    name: "Heartwood Branch",
    desc: "A sturdy branch from the ancient forest.",
    glyph: "🪵",
    color: "#c79a64",
    stackable: true,
  },
  water: {
    id: "water",
    name: "Vial of Springwater",
    desc: "Clear water drawn from the village well.",
    glyph: "💧",
    color: "#7ec8ff",
    stackable: true,
  },
  string: {
    id: "string",
    name: "Spider Silk",
    desc: "Strong, gossamer thread gathered in the ruins.",
    glyph: "🧵",
    color: "#dfe2f0",
    stackable: true,
  },
  // Crafted / quest items
  potion: {
    id: "potion",
    name: "Moonpetal Tonic",
    desc: "A soothing tonic brewed from moonpetal and springwater.",
    glyph: "🧪",
    color: "#a6f0c0",
    stackable: true,
  },
  lantern: {
    id: "lantern",
    name: "Glimlantern",
    desc: "A small lantern lit by a glimcap. Pushes back the night.",
    glyph: "🏮",
    color: "#ffcf6b",
    stackable: false,
  },
  charm: {
    id: "charm",
    name: "Aether Charm",
    desc: "A shard bound in silk. The ruins' echoes quiet around it.",
    glyph: "🔮",
    color: "#b59bff",
    stackable: false,
  },
  bridgeplank: {
    id: "bridgeplank",
    name: "Bound Planks",
    desc: "Heartwood lashed with silk — enough to mend a broken bridge.",
    glyph: "🪜",
    color: "#caa06a",
    stackable: false,
  },
  locket: {
    id: "locket",
    name: "Silver Locket",
    desc: "A tarnished locket. Someone in the village is missing it.",
    glyph: "📿",
    color: "#d8d8e0",
    stackable: false,
  },
  letter: {
    id: "letter",
    name: "Sealed Letter",
    desc: "A letter for the hermit, sealed with green wax.",
    glyph: "✉️",
    color: "#e8d9a0",
    stackable: false,
  },
};

export function itemDef(id: string): ItemDef {
  const d = ITEMS[id];
  if (!d) throw new Error(`Unknown item: ${id}`);
  return d;
}
