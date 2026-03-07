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
        test: "vitest run",
      },
      dependencies: {},
      devDependencies: {
        autocrab: "workspace:*",
        typescript: "^5.0.0",
        vitest: "^1.0.0",
        "@types/node": "^20.0.0",
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

const TEMPLATE_INDEX_TS = (name: string) => `
import { defineExtension } from "autocrab/plugin-sdk";

export default defineExtension({
  name: "${name}",
  async setup(context) {
    context.log.info("Extension ${name} loaded");
    
    // Register your channel capability here
    // context.gateway.registerChannel(...)
  }
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
    await fs.mkdir(extensionDir);
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

  console.log(`Extension ${name} created at extensions/${name}`);
  console.log(`Don't forget to run 'pnpm install' to link dependencies.`);
}

main().catch(console.error);
