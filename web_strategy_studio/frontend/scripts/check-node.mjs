#!/usr/bin/env node
const major = Number.parseInt(process.version.slice(1).split(".")[0], 10);
if (Number.isNaN(major) || major < 18) {
  console.error(
    `[eq-studio-web] 当前 Node 为 ${process.version}，需要 Node 18 及以上（推荐 20 LTS）。\n` +
      "否则 Vite 会报错：crypto.getRandomValues is not a function\n" +
      "示例：nvm install 20 && nvm use 20   或   brew install node@20"
  );
  process.exit(1);
}
