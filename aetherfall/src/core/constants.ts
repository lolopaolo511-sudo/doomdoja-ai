export const TILE = 32;

/** Player movement speed in pixels/second. */
export const PLAYER_SPEED = 132;

/** Player collision box (smaller than a tile so corners feel forgiving). */
export const PLAYER_W = 18;
export const PLAYER_H = 16;

/** Interaction reach in pixels. */
export const INTERACT_RANGE = 46;

// --- World clock -----------------------------------------------------------
/** Real seconds per in-game minute. */
export const SECONDS_PER_MINUTE = 0.5;
/** In-game minutes in a full day. */
export const MINUTES_PER_DAY = 24 * 60;

export const SAVE_KEY = "aetherfall.save.v1";
export const SETTINGS_KEY = "aetherfall.settings.v1";
export const SAVE_VERSION = 1;
