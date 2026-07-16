const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, "../..");
const appCoreRoot = path.resolve(monorepoRoot, "packages/app-core");

const config = getDefaultConfig(projectRoot);

// Include shared package outside apps/mobile (required for file: dependencies).
config.watchFolders = [monorepoRoot];

config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(monorepoRoot, "node_modules"),
];

// Windows junctions + monorepo: resolve @meal-agent/app-core to the real folder.
config.resolver.extraNodeModules = {
  "@meal-agent/app-core": appCoreRoot,
};

config.resolver.disableHierarchicalLookup = true;

module.exports = config;
