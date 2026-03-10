// Defaults for agent metadata when upstream does not supply them.
// Model id uses pi-ai's built-in Anthropic catalog.
export const DEFAULT_PROVIDER = process.env.AUTOCRAB_MODEL_PROVIDER || "anthropic";
export const DEFAULT_MODEL = process.env.AUTOCRAB_MODEL_ID || "claude-opus-4-6";
// Conservative fallback used when model metadata is unavailable.
export const DEFAULT_CONTEXT_TOKENS = 200_000;

// Default history limit for embedded runner sessions (DMs, Groups, Channels)
// to prevent infinite context growth when not explicitly configured.
export const DEFAULT_HISTORY_LIMIT = 50;
