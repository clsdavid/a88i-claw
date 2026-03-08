import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";

const TEMPLATE_PACKAGE_JSON = (name: string) =>
  JSON.stringify(
    {
      name: `@autocrab/${name}`,
      version: "0.0.0",
      private: true,
      description: `AutoCrab ${name} channel plugin`,
      type: "module",
      scripts: {
        build: "tsc",
        check: "tsc --noEmit",
        test: "vitest run",
      },
      dependencies: {},
      devDependencies: {
        autocrab: "workspace:*",
        typescript: "^5.3.3",
        vitest: "^1.2.0",
        "@types/node": "^22.0.0",
      },
      autocrab: {
        extensions: ["./index.ts"],
        channel: {
          id: name,
          label: name.charAt(0).toUpperCase() + name.slice(1),
          description: `Support for ${name} messaging`,
        },
      },
    },
    null,
    2,
  );

const TEMPLATE_TSCONFIG = JSON.stringify(
  {
    extends: "../../tsconfig.json",
    compilerOptions: {
      outDir: "dist",
      rootDir: ".",
    },
    include: ["./**/*.ts"],
  },
  null,
  2,
);

const TEMPLATE_README_MD = (name: string) => `# AutoCrab Extension: ${name}

This extension provides integration with ${name} for AutoCrab.

## Security Guidelines

1.  **Input Validation**: Ensure all external data is validated against a schema (e.g. Zod) before use.
2.  **Secret Management**: Never commit secrets to git. Use \`process.env\` or AutoCrab's configuration system.
3.  **Least Privilege**: Avoid requesting permissions or importing modules that are not strictly necessary.

## Development

- \`pnpm check\`: Run type checking
- \`pnpm test\`: Run unit tests
`;

const TEMPLATE_INDEX_TS = (name: string) =>
  `import { defineExtension } from "autocrab/plugin-sdk";

export default defineExtension({
  name: "${name}",
  async setup(context) {
    context.log.info("Extension ${name} loaded");
    
    // SECURITY NOTICE:
    // Always validate inputs from external sources (webhooks, API responses) before processing.
    // Avoid executing arbitrary code or shell commands with untrusted input.
    
    // Register your channel capability here
    // context.gateway.registerChannel(...)
  }
});
`;

const TEMPLATE_INDEX_TEST_TS = (name: string) =>
  `import { describe, it, expect } from "vitest";

// Note: In a real test, you might import the extension definition to test its logic.

describe("Extension ${name}", () => {
  it("should have a valid test environment", () => {
    expect(true).toBe(true);
  });
});
`;

async function main() {
  const { positionals } = parseArgs({
    allowPositionals: true,
  });

  const name = positionals[0];
  if (!name) {
    console.error("Usage: node scripts/create-extension.ts <extension-name>");
    process.exit(1);
  }

  const extensionDir = path.join(process.cwd(), "extensions", name);

  try {
    await fs.mkdir(extensionDir, { recursive: true });
  } catch (err) {
    if (
      (err instanceof Error || typeof err === "object") &&
      (err as { code?: string })?.code === "EEXIST"
    ) {
      console.error(`Extension directory already exists: ${extensionDir}`);
      process.exit(1);
    }
    throw err;
  }

  await fs.writeFile(path.join(extensionDir, "package.json"), TEMPLATE_PACKAGE_JSON(name));
  await fs.writeFile(path.join(extensionDir, "tsconfig.json"), TEMPLATE_TSCONFIG);
  await fs.writeFile(path.join(extensionDir, "index.ts"), TEMPLATE_INDEX_TS(name));
  await fs.writeFile(path.join(extensionDir, "index.test.ts"), TEMPLATE_INDEX_TEST_TS(name));
  await fs.writeFile(path.join(extensionDir, "README.md"), TEMPLATE_README_MD(name));

  console.log(`Extension ${name} created at extensions/${name}`);
  console.log(`Don't forget to run 'pnpm install' to link dependencies.`);
}

main().catch(console.error);
