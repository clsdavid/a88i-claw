import {
  inspectDiscordAccount,
  type InspectedDiscordAccount,
} from "@autocrab/discord/account-inspect.js";
import {
  inspectSlackAccount,
  type InspectedSlackAccount,
} from "@autocrab/slack/account-inspect.js";
import {
  inspectTelegramAccount,
  type InspectedTelegramAccount,
} from "@autocrab/telegram/account-inspect.js";
import type { AutoCrabConfig } from "../config/config.js";
import type { ChannelId } from "./plugins/types.js";

export type ReadOnlyInspectedAccount =
  | InspectedDiscordAccount
  | InspectedSlackAccount
  | InspectedTelegramAccount;

export function inspectReadOnlyChannelAccount(params: {
  channelId: ChannelId;
  cfg: AutoCrabConfig;
  accountId?: string | null;
}): ReadOnlyInspectedAccount | null {
  if (params.channelId === "discord") {
    return inspectDiscordAccount({
      cfg: params.cfg,
      accountId: params.accountId,
    });
  }
  if (params.channelId === "slack") {
    return inspectSlackAccount({
      cfg: params.cfg,
      accountId: params.accountId,
    });
  }
  if (params.channelId === "telegram") {
    return inspectTelegramAccount({
      cfg: params.cfg,
      accountId: params.accountId,
    });
  }
  return null;
}
