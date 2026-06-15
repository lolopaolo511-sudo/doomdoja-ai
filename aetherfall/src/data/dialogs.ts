import type { DialogTree, GameState } from "../core/types";
import { phaseOfState, isNight } from "../world/DayNight";

// --- small state-reading helpers -------------------------------------------
const has = (s: GameState, id: string, n = 1) => (s.inventory[id] ?? 0) >= n;
const qStatus = (s: GameState, id: string) => s.quests[id]?.status ?? "locked";
const qActive = (s: GameState, id: string) => qStatus(s, id) === "active";
const qDone = (s: GameState, id: string) => qStatus(s, id) === "complete";
const flag = (s: GameState, k: string) => s.flags[k];

// ---------------------------------------------------------------------------
// One dialog tree per NPC, keyed by npc id.
// ---------------------------------------------------------------------------
export const DIALOGS: Record<string, DialogTree> = {
  // ---- Mira, the healer (quest: tonics) -----------------------------------
  mira: {
    start: (s) => {
      if (qDone(s, "tonics")) return "done";
      if (qActive(s, "tonics")) return has(s, "potion", 2) ? "turnin" : "remind";
      return "offer";
    },
    nodes: {
      offer: {
        id: "offer",
        text: (s) =>
          isNight(s)
            ? "Oh — a traveller, out this late? I'm Mira. Truth be told, I could use a kind pair of hands."
            : "Welcome, traveller. I'm Mira, what passes for a healer in Wend. You look hale enough — good.",
        choices: [
          {
            text: "You look troubled. What's wrong?",
            next: "explain",
          },
          { text: "Just passing through. (Leave)", next: null },
        ],
      },
      explain: {
        id: "explain",
        text: "My shelves are bare of moonpetal tonic, and half the village has a cough. Moonpetal only glows after dark — gather some in the forest at night, brew it with springwater, and bring me two. I'll make it worth your while.",
        choices: [
          {
            text: "I'll help you, Mira.",
            effect: (c) => {
              c.startQuest("tonics");
              c.toast("Quest accepted: A Healer's Request");
            },
            next: "accepted",
          },
          { text: "Maybe later.", next: null },
        ],
      },
      accepted: {
        id: "accepted",
        text: "Bless you. Remember — moonpetal hides by day. Look for the pale glow once night falls. The well in the square gives clean springwater.",
        next: null,
      },
      remind: {
        id: "remind",
        text: (s) =>
          (flag(s, "crafted_potion") ?? 0)
            ? "Almost there? I need two tonics in hand before I can dose the village. Open your satchel's Crafting page — two moonpetal and a vial of springwater each."
            : "The moonpetal glows at night, remember. Gather a few, then brew them with springwater. Two tonics is all I ask.",
        choices: [{ text: "I'm on it.", next: null }],
      },
      turnin: {
        id: "turnin",
        text: "Is that— oh, you've done it! Two tonics, and finely brewed. Here, let me trade you fair.",
        choices: [
          {
            text: "Hand over the two tonics.",
            effect: (c) => {
              c.take("potion", 2);
              c.setFlag("tonics_delivered", true);
              c.completeQuest("tonics");
            },
            next: "thanks",
          },
        ],
      },
      thanks: {
        id: "thanks",
        text: "The whole village will breathe easier tonight. Take this aether shard — I found it years ago and never knew its use. And some springwater for the road.",
        next: null,
      },
      done: {
        id: "done",
        text: (s) =>
          isNight(s)
            ? "Resting easy tonight, thanks to you. The coughing's stopped on our street."
            : "The tonics worked wonders. If the forest ever frightens you, my door is open.",
        choices: [{ text: "Take care, Mira.", next: null }],
      },
    },
  },

  // ---- Bertram, the old widower (quest: locket) ---------------------------
  bertram: {
    start: (s) => {
      if (qDone(s, "locket")) return "done";
      if (qActive(s, "locket")) return has(s, "locket") ? "turnin" : "remind";
      return "offer";
    },
    nodes: {
      offer: {
        id: "offer",
        text: "These old eyes... forgive me. I'm Bertram. I've lost something dear — my late wife's silver locket. I think it slipped from my coat in the ancient forest, days ago.",
        choices: [
          {
            text: "I'll look for it.",
            effect: (c) => {
              c.startQuest("locket");
              c.toast("Quest accepted: The Lost Locket");
            },
            next: "accepted",
          },
          { text: "I'm sorry for your loss. (Leave)", next: null },
        ],
      },
      accepted: {
        id: "accepted",
        text: "Thank you, child. It's silver, with a pressed moonpetal inside. Somewhere among the roots, perhaps. My knees won't carry me there anymore.",
        next: null,
      },
      remind: {
        id: "remind",
        text: "Any sign of it? The forest is wide, I know. Look low — among the old roots, where a small thing might fall and hide.",
        choices: [{ text: "Still searching.", next: null }],
      },
      turnin: {
        id: "turnin",
        text: "You— is that...? Oh. Oh, it is. Forty years we were wed. Thank you. Truly.",
        choices: [
          {
            text: "Give Bertram the locket.",
            effect: (c) => {
              c.take("locket", 1);
              c.setFlag("locket_returned", true);
              c.completeQuest("locket");
            },
            next: "thanks",
          },
        ],
      },
      thanks: {
        id: "thanks",
        text: "Here — take this silk thread. My wife spun it; she'd want it used, not hoarded. You've a good heart, traveller.",
        next: null,
      },
      done: {
        id: "done",
        text: "I wear her locket every day now. Some nights I sit by the well and tell her of the strangers who pass. She'd have liked you.",
        choices: [{ text: "Good evening, Bertram.", next: null }],
      },
    },
  },

  // ---- Garrin, the carpenter (quests: bridge -> letter) -------------------
  garrin: {
    start: (s) => {
      if (qActive(s, "letter")) {
        if ((flag(s, "letter_delivered") ?? false) && !(flag(s, "letter_replied") ?? false))
          return "letter_turnin";
        return "letter_remind";
      }
      if (qDone(s, "letter")) return "all_done";
      if (qDone(s, "bridge")) return "offer_letter";
      if (qActive(s, "bridge")) return "bridge_remind";
      return "offer_bridge";
    },
    nodes: {
      offer_bridge: {
        id: "offer_bridge",
        text: "Garrin's the name, carpentry's the trade. Got a headache, though — the river bridge in the forest gave way. No crossing to the clearing till it's mended, and I can't leave the shop.",
        choices: [
          {
            text: "I could fix it for you.",
            next: "explain_bridge",
          },
          { text: "Sounds like your problem. (Leave)", next: null },
        ],
      },
      explain_bridge: {
        id: "explain_bridge",
        text: "Would you? You'll need bound planks — three good heartwood branches lashed with spider silk. Heartwood's on the forest floor; silk you'll find in the ruins north of it. Craft the planks, then mend the bridge where it broke.",
        choices: [
          {
            text: "Consider it done.",
            effect: (c) => {
              c.startQuest("bridge");
              c.toast("Quest accepted: The Broken Bridge");
            },
            next: null,
          },
          { text: "I'll think on it.", next: null },
        ],
      },
      bridge_remind: {
        id: "bridge_remind",
        text: (s) =>
          (flag(s, "crafted_bridgeplank") ?? 0)
            ? "You've planks already? Good — take them to the gap in the forest bridge and lay them across. The river's east, past the long path."
            : "Three heartwood, one length of silk — that's bound planks. Craft them in your satchel, then mend the gap in the forest.",
        choices: [{ text: "On my way.", next: null }],
      },
      offer_letter: {
        id: "offer_letter",
        text: "The bridge holds like new — I checked it myself. You've earned my trust. Could I ask one more thing? I've a letter for Caedry, the hermit across in the clearing. We don't speak much these days... it's overdue.",
        choices: [
          {
            text: "I'll carry it across.",
            effect: (c) => {
              c.startQuest("letter");
              c.give("letter", 1);
              c.toast("Quest accepted: A Letter for the Hermit");
            },
            next: "letter_given",
          },
          { text: "Not right now.", next: null },
        ],
      },
      letter_given: {
        id: "letter_given",
        text: "Here. Sealed with green wax. Caedry will know it's from me. And... bring back whatever they say. Even if it's nothing.",
        next: null,
      },
      letter_remind: {
        id: "letter_remind",
        text: "Caedry's hut is across the mended bridge, east through the forest. Give them the letter — and tell me their answer when you return.",
        choices: [{ text: "I'll be back.", next: null }],
      },
      letter_turnin: {
        id: "letter_turnin",
        text: "You spoke to Caedry? ...And? What did the old fool say?",
        choices: [
          {
            text: "“Tell Garrin the door was never locked.”",
            effect: (c) => {
              c.setFlag("letter_replied", true);
              c.completeQuest("letter");
            },
            next: "letter_thanks",
          },
        ],
      },
      letter_thanks: {
        id: "letter_thanks",
        text: "...The door was never locked. Hah. Of course. Stubborn as the day we quarrelled. Thank you, friend. I'll walk over myself, come morning. Take this — shards and a tonic for the road.",
        next: null,
      },
      all_done: {
        id: "all_done",
        text: "Bridge mended, words mended. Not a bad week's work, eh? Caedry and I had supper last night. First time in years.",
        choices: [{ text: "Glad to hear it.", next: null }],
      },
    },
  },

  // ---- Selene, the scholar (quest: ruins). Ruins by day, study by night. --
  selene: {
    start: (s) => {
      if (qDone(s, "ruins")) return "done";
      if (qActive(s, "ruins")) return (flag(s, "charmPlaced") ?? false) ? "done" : "remind";
      return "offer";
    },
    nodes: {
      offer: {
        id: "offer",
        text: (s) =>
          phaseOfState(s) === "night"
            ? "Working late — the glyphs read clearer by lamplight. I'm Selene. I study the stone ruins, when the echoes let me."
            : "Mind the loose stones. I'm Selene; I map these ruins for the village. There's history in the silence here — if only the echoes would let it speak.",
        choices: [
          { text: "What echoes?", next: "explain" },
          { text: "I'll leave you to it. (Leave)", next: null },
        ],
      },
      explain: {
        id: "explain",
        text: "When the sky-stone fell here long ago, it left a... restlessness. The shrine at the ruins' heart drowns my notes in whispers. An aether charm — a shard bound in silk — set in its hollow would quiet it. Shards and silk are both here, if you'll gather them.",
        choices: [
          {
            text: "I'll make the charm.",
            effect: (c) => {
              c.startQuest("ruins");
              c.toast("Quest accepted: Echoes in the Ruins");
            },
            next: "accepted",
          },
          { text: "Sounds dangerous. (Leave)", next: null },
        ],
      },
      accepted: {
        id: "accepted",
        text: "One aether shard, two lengths of silk — bind them and place the charm on the cracked shrine. Then, perhaps, we'll both hear what the stones remember.",
        next: null,
      },
      remind: {
        id: "remind",
        text: (s) =>
          (flag(s, "crafted_charm") ?? 0)
            ? "You've the charm? Set it in the hollow at the shrine's heart, here in the ruins. Go gently."
            : "Gather an aether shard and two lengths of silk from the ruins, then craft the charm in your satchel.",
        choices: [{ text: "Soon.", next: null }],
      },
      done: {
        id: "done",
        text: (s) =>
          (flag(s, "charmPlaced") ?? false)
            ? "Listen— the whispering's gone. For the first time the glyphs are plain: 'Where the sky fell, kindness was buried.' ...I'd never have read it without you. Take these shards, with my thanks."
            : "The ruins are quiet now. I've pages of new readings to make. Visit again — I'll have stories.",
        choices: [
          {
            text: "Anytime, Selene.",
            effect: (c) => {
              // Reward handed out once, when first reaching the 'done' state post-placement.
              if ((flag(c.state, "charmPlaced") ?? false) && qStatus(c.state, "ruins") === "active") {
                c.completeQuest("ruins");
              }
            },
            next: null,
          },
        ],
      },
    },
  },

  // ---- Caedry, the hermit (letter target) ---------------------------------
  caedry: {
    start: (s) => {
      if (qActive(s, "letter") && has(s, "letter")) return "receive";
      if (flag(s, "letter_delivered")) return "after";
      return "lore";
    },
    nodes: {
      lore: {
        id: "lore",
        text: "Few cross the bridge to find me. The mist keeps most away, and I keep myself. ...Say nothing of Wend to me. I left it for reasons.",
        choices: [
          { text: "Why did you leave?", next: "why" },
          { text: "Sorry to intrude. (Leave)", next: null },
        ],
      },
      why: {
        id: "why",
        text: "A quarrel with a stubborn carpenter, years past. Words said that can't be unsaid. So I keep the quiet of the clearing instead. It asks nothing of me.",
        choices: [{ text: "Perhaps it isn't too late. (Leave)", next: null }],
      },
      receive: {
        id: "receive",
        text: "...A letter? Green wax. So it's from Garrin. After all this time, he writes. ...Give it here.",
        choices: [
          {
            text: "Hand Caedry the letter.",
            effect: (c) => {
              c.take("letter", 1);
              c.setFlag("letter_delivered", true);
              c.toast("Caedry reads the letter in silence.");
            },
            next: "read",
          },
        ],
      },
      read: {
        id: "read",
        text: "(Caedry reads it twice, then folds it carefully away.) ...Tell him this, word for word: the door was never locked. He'll understand. Go on, now — before I change my mind about being glad you came.",
        next: null,
      },
      after: {
        id: "after",
        text: "Still here? ...Tell Garrin what I said. And — thank you, traveller. The mist feels lighter today. Can't think why.",
        choices: [{ text: "I'll tell him.", next: null }],
      },
    },
  },

  // ---- Pip, the village child (flavor + hints) ----------------------------
  pip: {
    start: (s) => (isNight(s) ? "night" : "day"),
    nodes: {
      day: {
        id: "day",
        text: "Are you a real adventurer?? Did you see the glowy flowers in the forest? They ONLY glow at night. Nan says it's aether. I say it's fairies.",
        choices: [
          { text: "Maybe it's both.", next: "both" },
          { text: "Definitely fairies.", next: "fairies" },
          { text: "(Leave)", next: null },
        ],
      },
      both: {
        id: "both",
        text: "That's what I said! Sort of. Hey — if you find a shiny shard, those are from the SKY. Selene studies them up in the ruins. Don't tell her I touched her notes.",
        next: null,
      },
      fairies: {
        id: "fairies",
        text: "I KNEW it. Don't tell Nan, she'll do the eyebrow thing. ...You should go at night and look. The whole forest lights up!",
        next: null,
      },
      night: {
        id: "night",
        text: "(whispering) I'm not supposed to be up. But look — you can see the forest glowing from here! Tonight's a good night to gather moonpetal, if you're brave.",
        choices: [{ text: "Off to bed, Pip.", next: null }],
      },
    },
  },

  // ---- Nan, the elder (lore by the well; gone at night) -------------------
  nan: {
    start: () => "greet",
    nodes: {
      greet: {
        id: "greet",
        text: "Sit a moment, traveller. I'm Nan, oldest soul in Wend. I remember when the sky fell — a streak of light, and then the ruins were... awake. We don't go there after dark.",
        choices: [
          { text: "What fell from the sky?", next: "lore" },
          { text: "Tell me about the village.", next: "village" },
          { text: "(Leave)", next: null },
        ],
      },
      lore: {
        id: "lore",
        text: "Aether, the scholars call it now. Sky-stone. It hums, it glows, it remembers. The forest drank it and grew strange; the ruins kept it and grew loud. Mind you treat it with respect.",
        next: null,
      },
      village: {
        id: "village",
        text: "Small but kind, our Wend. Mira mends our coughs, Garrin our roofs, Bertram our spirits — though he grieves still. Be good to them and they'll be good to you. That's the whole of it.",
        next: null,
      },
    },
  },

  // ---- Tomas, the farmer (hints) ------------------------------------------
  tomas: {
    start: (s) => (isNight(s) ? "night" : "day"),
    nodes: {
      day: {
        id: "day",
        text: "Morning! Tomas, I work the village plots. Heard you're helping folk out — good. If you're after heartwood, the forest floor's littered with fallen branches. Saves chopping.",
        choices: [
          { text: "Thanks for the tip.", next: null },
          { text: "Seen anything strange lately?", next: "strange" },
        ],
      },
      strange: {
        id: "strange",
        text: "Strange? Ha. The mist past the river's thicker each year. And the ruins glow some nights. I keep my fences mended and my head down, myself.",
        next: null,
      },
      night: {
        id: "night",
        text: "Late for wandering. I only step out to check the plots. ...You headed to the forest? Bring a lantern — the dark out there isn't friendly.",
        choices: [{ text: "Good night, Tomas.", next: null }],
      },
    },
  },

  // ---- Wrenna, the herbalist (roams the forest) ---------------------------
  wrenna: {
    start: (s) => (isNight(s) ? "night" : "day"),
    nodes: {
      day: {
        id: "day",
        text: "Hush — you'll scare the glimcaps. I'm Wrenna, I gather what the forest offers. Mushrooms by the roots, moonpetal by night. The forest gives freely, if you ask gently.",
        choices: [
          { text: "Where's the best moonpetal?", next: "moonpetal" },
          { text: "(Leave)", next: null },
        ],
      },
      moonpetal: {
        id: "moonpetal",
        text: "Everywhere, come nightfall — but you won't see it by day. Wait for dark and the whole floor blushes pale silver. Glimcaps you can pluck any time; they like the deep roots.",
        next: null,
      },
      night: {
        id: "night",
        text: "Ah — now you see why I love this place. Look at it glow. Gather all the moonpetal you like; just leave the roots be. The forest remembers a kindness.",
        choices: [{ text: "It's beautiful.", next: null }],
      },
    },
  },
};
