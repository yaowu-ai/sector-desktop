const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const here = __dirname;
const desktopRoot = path.resolve(here, "..");
const srcRoot = path.join(desktopRoot, "src");

function read(relativePath) {
  return fs.readFileSync(path.join(srcRoot, relativePath), "utf8");
}

function assertFile(relativePath) {
  assert.ok(
    fs.existsSync(path.join(srcRoot, relativePath)),
    `missing ${relativePath}`,
  );
}

const platformIndex = read("platforms/index.ts");
const registry = read("platforms/registry.ts");
const routePermissions = read("app/routePermissions.ts");
const routes = read("app/routes.tsx");
const appShell = read("components/AppShell.tsx");
const tiktokServices = read("platforms/tiktok/services/index.ts");
const tiktokHomePage = read("platforms/tiktok/pages/HomePage.tsx");
const tiktokRecordsPage = read("platforms/tiktok/pages/ExecutionRecordPage.tsx");
const tiktokStatsPage = read("platforms/tiktok/pages/StatsPage.tsx");
const tiktokSessionsPage = read("platforms/tiktok/pages/SessionLogPage.tsx");
const diagnosticPage = read("pages/DiagnosticPage.tsx");

assert.match(
  platformIndex,
  /export\s*\{[^}]*PLATFORM_MODULES[^}]*\}\s*from ['"]\.\/registry['"]/s,
  "platform barrel should expose module registry",
);
assert.match(
  platformIndex,
  /PlatformModuleManifest/,
  "platform barrel should expose module manifest type",
);
assert.match(
  registry,
  /tiktokModule|instagramModule|whatsappModule|douyinModule/,
  "registry should be assembled from platform modules",
);
assert.match(
  registry,
  /PLATFORM_MODULES/,
  "registry should retain a module-level registry",
);

for (const platform of ["tiktok", "instagram", "whatsapp", "douyin"]) {
  assertFile(`platforms/${platform}/pages/index.ts`);
  assertFile(`platforms/${platform}/services/index.ts`);
  assertFile(`platforms/${platform}/index.ts`);
}
for (const platform of ["instagram", "whatsapp", "douyin"]) {
  assertFile(`platforms/${platform}/config.ts`);
}

assert.match(
  read("platforms/common/reservedModule.ts"),
  /implementation:\s*['"]reserved['"]/,
  "reserved platforms must use the reserved module factory",
);
for (const platform of ["instagram", "whatsapp", "douyin"]) {
  assert.match(
    read(`platforms/${platform}/index.ts`),
    /createReservedPlatformModule/,
    `${platform} should remain a reserved module`,
  );
}

assert.match(
  routes,
  /from ['"]\.\.\/platforms\/tiktok\/pages['"]/,
  "business routes should enter through the TikTok page module",
);
assert.doesNotMatch(
  routes,
  /from ['"]\.\.\/pages\/(?:Account|BrowserProfile|CommentPool|ExecutionRecord|GmailSetup|ProfileStats|Scheduler|SessionLog|Stats|TargetEngagement|Task)Page['"]/,
  "routes should not directly import TikTok business page implementations",
);

for (const key of [
  "profile",
  "plans",
  "license-devices",
  "contact",
  "notifications",
  "about",
  "settings",
]) {
  assert.match(
    routePermissions,
    new RegExp(`['"]${key}['"]`),
    `${key} should remain a system-level route`,
  );
}
assert.match(
  routePermissions,
  /platform\.status === ['"]supported['"] && platform\.automaticExecutionSupported/,
  "platform menu filtering should require executable support",
);
assert.match(
  routePermissions,
  /SYSTEM_MENU_ROUTE_KEYS/,
  "platform menu filtering should preserve only system-level routes",
);
assert.match(
  appShell,
  /filterRoutesByPlatformAvailability/,
  "AppShell should apply platform menu filtering",
);
assert.match(
  appShell,
  /availableAppRoutes/,
  "AppShell should constrain active app routes after filtering",
);

for (const [name, source] of [
  ["TikTok home", tiktokHomePage],
  ["TikTok execution records", tiktokRecordsPage],
  ["TikTok stats", tiktokStatsPage],
  ["TikTok session logs", tiktokSessionsPage],
]) {
  assert.doesNotMatch(
    source,
    /PlatformScopeFilter|PlatformFilterValue|platformFilter/,
    `${name} should not expose a cross-platform filter`,
  );
  assert.match(
    source,
    /currentPlatform/,
    `${name} should be scoped by the current platform`,
  );
}
assert.doesNotMatch(
  diagnosticPage,
  /selectedPlatform|<Select<Platform>|PLATFORMS\.map/,
  "diagnostic tool should not expose an independent platform selector",
);
assert.match(
  diagnosticPage,
  /usePlatformContext/,
  "diagnostic tool should use the global platform context",
);
assert.match(
  read("services/api.ts"),
  /getHomeSummary\(platform: Platform = ['"]tiktok['"]\)/,
  "home summary API should accept the current platform",
);

for (const service of [
  "runTikTokRegister",
  "runPlatformTask",
  "saveFypSettings",
  "getCurrentRunStatus",
]) {
  assert.match(
    tiktokServices,
    new RegExp(`\\b${service}\\b`),
    `TikTok service facade should expose ${service}`,
  );
}

console.log("platform boundary checks passed");
