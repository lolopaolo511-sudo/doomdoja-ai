# Aetherfall

A small **living fantasy world** you can explore in the browser. Built with
**Vite + TypeScript** and pure **HTML5 Canvas** (no game engine), with
**Tailwind CSS** for the menus and UI.

You arrive in Wend, a quiet village beneath a sky that once fell. Wander the
village, the ancient forest, the stone ruins, and a misty clearing across a
broken bridge. Talk to the folk who live there, help them with their troubles,
gather and craft, and watch the world shift from day to night.

## Run it

```bash
cd aetherfall
npm install
npm run dev
```

Then open the URL Vite prints (default http://localhost:5173).

To build a production bundle:

```bash
npm run build      # type-checks then bundles to dist/
npm run preview    # serve the built bundle
```

## How to play

| Action | Keys |
| --- | --- |
| Move | `W A S D` / arrow keys, or **click** a spot |
| Interact / talk / gather | `E` or `Space`, or **click** a nearby person/object |
| Inventory | `I` |
| Crafting | `C` |
| Quest log | `J` |
| Menu / pause | `Esc` |
| Dialog choices | click, or number keys `1`–`9` |

Villagers with a golden **!** have a quest to offer; a blue **?** means a quest
is ready to turn in. Your current objective is always shown along the bottom.

## What's in the world

- **Day/night cycle** — the clock advances as you play. Moonpetal herbs only
  glow (and can only be gathered) after dark; lanterns, campfires and shards
  light the night. Some villagers move or go home as the day turns — Selene the
  scholar works the ruins by day and her study by night; Nan sleeps after dark.
  Rest at a **campfire** to pass the time.
- **9 NPCs** with their own roles, lines, and small stories — Mira, Bertram,
  Garrin, Selene, Caedry, Pip, Nan, Tomas and Wrenna. Their dialogue reacts to
  the time of day and your progress.
- **5 quests**, including a chained story (mend the bridge, then carry a letter
  that quietly reconciles two old friends).
- **Inventory & crafting** — gather herbs, heartwood, shards and silk; brew
  tonics, bind charms, lash planks, and light a glimlantern.
- **Save/load** via `localStorage` — the game autosaves as you play, on every
  area change, and from the pause menu. Pick **Continue** on the title screen.

## Project structure

```
aetherfall/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js / postcss.config.js
├── tsconfig.json
└── src/
    ├── main.ts                # entry point
    ├── style.css              # Tailwind + theme
    ├── core/
    │   ├── Game.ts            # orchestrator: loop, interaction, dialog, save
    │   ├── Input.ts           # keyboard + pointer
    │   ├── Camera.ts          # smooth follow camera
    │   ├── constants.ts
    │   ├── state.ts           # new-game factory
    │   └── types.ts           # shared types
    ├── world/
    │   ├── maps.ts            # the four hand-built locations
    │   ├── MapBuilder.ts      # tiny tilemap layout helper
    │   ├── tiles.ts           # tile colors + solidity
    │   ├── collision.ts       # tile / box collision
    │   └── DayNight.ts        # clock, phases, lighting curve
    ├── entities/
    │   ├── Player.ts          # movement, collision, animation
    │   └── npcs.ts            # NPC definitions + day/night schedules
    ├── systems/
    │   ├── Inventory.ts
    │   ├── Crafting.ts
    │   ├── QuestSystem.ts
    │   ├── SaveSystem.ts
    │   └── pathfind.ts        # A* for click-to-move
    ├── render/
    │   ├── Renderer.ts        # painterly canvas renderer + lighting
    │   └── sprites.ts         # low-level draw helpers
    ├── data/
    │   ├── items.ts
    │   ├── recipes.ts
    │   ├── quests.ts
    │   └── dialogs.ts         # every NPC's branching dialogue
    └── ui/
        └── UI.ts              # Tailwind overlays: menu, HUD, dialog, panels
```

Everything is plain TypeScript modules; the only runtime is the browser.
