// Fait signer la version « release » avec la clé de Sheenu au lieu de la clé de test.
// Le projet android/ est généré par `expo prebuild` : on ajoute une signature « release »
// lue dans gradle.properties (SHEENU_*) et on l'utilise pour la compilation release.
// Usage : node release-signing.js android/app/build.gradle

const fs = require("fs");

const file = process.argv[2];
let gradle = fs.readFileSync(file, "utf8");

const release = `
        release {
            storeFile file(SHEENU_STORE_FILE)
            storePassword SHEENU_STORE_PASSWORD
            keyAlias SHEENU_KEY_ALIAS
            keyPassword SHEENU_KEY_PASSWORD
        }`;

gradle = gradle.replace(/signingConfigs\s*\{/, (m) => m + release);
// Dans buildTypes.release, la ligne générée est « signingConfig signingConfigs.debug »
const at = gradle.indexOf("release {", gradle.indexOf("buildTypes"));
const line = gradle.indexOf("signingConfig signingConfigs.debug", at);
if (at < 0 || line < 0) throw new Error("build.gradle inattendu : signature release introuvable");
gradle = gradle.slice(0, line) + "signingConfig signingConfigs.release" + gradle.slice(line + "signingConfig signingConfigs.debug".length);

fs.writeFileSync(file, gradle);
console.log("Signature release configurée.");
