import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rawTag = process.argv[2] || process.env.RELEASE_TAG || "";
const version = rawTag.replace(/^v/, "");

if (!/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`Invalid release tag version: ${rawTag}`);
}

const desktopRoot = dirname(dirname(fileURLToPath(import.meta.url)));

for (const relativePath of ["package.json", "src-tauri/tauri.conf.json"]) {
  const filePath = join(desktopRoot, relativePath);
  const data = JSON.parse(readFileSync(filePath, "utf8"));
  data.version = version;
  writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

const cargoPath = join(desktopRoot, "src-tauri/Cargo.toml");
const cargoToml = readFileSync(cargoPath, "utf8");
const updatedCargoToml = cargoToml.replace(
  /^(version = ")[^"]+(")$/m,
  `$1${version}$2`,
);

if (updatedCargoToml === cargoToml) {
  throw new Error("Unable to update package version in Cargo.toml");
}

writeFileSync(cargoPath, updatedCargoToml);
console.log(`Desktop release version set to ${version}`);
