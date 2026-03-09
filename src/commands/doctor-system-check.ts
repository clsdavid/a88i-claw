import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { detectRuntime, isSupportedNodeVersion } from "../infra/runtime-guard.js";
import { note } from "../terminal/note.js";

const execFileAsync = promisify(execFile);

// Must match package.json engines.node
const MIN_NODE_Display = "22.12.0";

export function noteSystemPrerequisites() {
  const runtime = detectRuntime();
  const valid = isSupportedNodeVersion(runtime.version);

  if (!valid) {
    note(
      [
        `- Node.js version ${runtime.version} is not supported.`,
        `- Required: >=${MIN_NODE_Display}`,
        "- Please upgrade Node.js to ensure stability.",
      ].join("\n"),
      "System Requirements",
    );
  }
}

export async function noteConflictingBinaries() {
  const legacyBin = "openclaw";
  const conflicting = await commandExists(legacyBin);

  if (conflicting) {
    note(
      [
        `- Legacy binary detected: \`${legacyBin}\``,
        "- Having both `autocrab` and `openclaw` installed may cause confusion.",
        "- Recommended: Uninstall the legacy package:",
        "  npm uninstall -g openclaw",
      ].join("\n"),
      "Conflicting Installations",
    );
  }
}

async function commandExists(cmd: string): Promise<boolean> {
  try {
    const isWin = process.platform === "win32";
    // Using 'where' on Windows and 'which' on Unix as 'command -v' might be shell built-in not executable directly
    const command = isWin ? "where" : "which";
    const args = [cmd];

    await execFileAsync(command, args);
    return true;
  } catch {
    return false;
  }
}
