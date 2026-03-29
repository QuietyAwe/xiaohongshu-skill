const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");

// --- 配置参数 ---
const CUSTOM_TEXT = "曲奇"; // 默认底部文本

// 预设比例与尺寸
const RATIO_PRESETS = {
  "9:16": { width: 675, height: 1200 },
  "3:4": { width: 810, height: 1080 },
};

function formatDate() {
  const now = new Date();
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
}

function extractTitle(mdPath) {
  const content = fs.readFileSync(mdPath, "utf-8");
  const match = content.split("\n").find((line) => line.startsWith("# "));
  return match ? match.slice(2).trim() : "无标题";
}

async function generateCover(
  title,
  customText,
  dateText,
  showSwipeHint = false,
  ratio = "9:16",
) {
  console.log("🚀 封面生成脚本开始执行...");
  console.log(`📐 使用比例: ${ratio}`);

  const preset = RATIO_PRESETS[ratio];
  if (!preset) {
    console.error(`❌ 不支持的比例: ${ratio}`);
    process.exit(1);
  }

  const { width: COVER_WIDTH, height: COVER_HEIGHT } = preset;
  const outDir = path.resolve("./assets/_attachments");

  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  console.log("⏳ 正在启动浏览器...");
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: "/usr/bin/chromium",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--font-render-hinting=none", // 禁用渲染微调
      "--disable-web-security", // 允许本地跨域加载字体
    ],
  });

  const page = await browser.newPage();
  const htmlPath = "file://" + path.resolve("./assets/cover-template.html");

  // 设置视口并开启高清渲染 (deviceScaleFactor: 2)
  await page.setViewport({
    width: COVER_WIDTH,
    height: COVER_HEIGHT,
    deviceScaleFactor: 2,
  });

  console.log(`🌐 正在打开页面: ${htmlPath}`);
  await page.goto(htmlPath, { waitUntil: "domcontentloaded", timeout: 30000 });

  // 注入全局CSS，隐藏滚动条以防右侧留白
  await page.addStyleTag({
    content: `
      html, body {
        width: 100vw !important;
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important; 
      }
    `,
  });

  // 注入文本与UI状态
  await page.evaluate(
    (t, c, d, showSwipe) => {
      document.getElementById("title").textContent = t;
      document.getElementById("customText").textContent = c;
      document.getElementById("dateText").textContent = d;
      if (showSwipe) {
        document.getElementById("swipeHint").classList.add("visible");
      }
    },
    title,
    customText,
    dateText,
    showSwipeHint,
  );

  // 动态调整标题字号 - 支持多行
  await page.evaluate((currentRatio) => {
    const titleEl = document.getElementById("title");
    const container = document.querySelector(".title-container");
    if (!titleEl || !container) return;

    titleEl.style.fontWeight = "900";

    let fontSize = currentRatio === "3:4" ? 115 : 100;
    const minFontSize = currentRatio === "3:4" ? 72 : 64;

    titleEl.style.fontSize = fontSize + "px";
    titleEl.style.lineHeight = "1.25";

    // 允许标题换行，限制最大宽度
    titleEl.style.display = "inline";
    titleEl.style.whiteSpace = "normal";
    titleEl.style.wordBreak = "break-word";
    container.style.maxWidth = "100%";

    // 检查是否需要缩小字号
    const checkLines = () => {
      let lineHeight = parseFloat(getComputedStyle(titleEl).lineHeight);
      if (isNaN(lineHeight)) lineHeight = fontSize * 1.25;

      const actualHeight = titleEl.offsetHeight;
      return actualHeight / lineHeight;
    };

    // 等待渲染后检查，字数真的太多（超过3行半）才开始动态缩小
    setTimeout(() => {
      let lines = checkLines();
      while (lines > 3.5 && fontSize > minFontSize) {
        fontSize -= 4;
        titleEl.style.fontSize = fontSize + "px";
        lines = checkLines();
      }
    }, 100);
  }, ratio);

  // 确保字体加载完毕并强制触发重排 (Reflow)
  await page.evaluate(async () => {
    await document.fonts.ready;
    document.body.offsetHeight;
  });

  await new Promise((r) => setTimeout(r, 1000));

  // 截取浅色主题
  console.log("\n📸 生成浅色主题封面...");
  const lightPath = path.join(outDir, "cover-light.png");
  fs.writeFileSync(lightPath, await page.screenshot({ type: "png" }));
  console.log(`✓ ${lightPath}`);

  // 切换深色主题并等待过渡动画
  console.log("\n切换到深色主题...");
  await page.evaluate(() =>
    document.documentElement.setAttribute("data-theme", "dark"),
  );
  await new Promise((r) => setTimeout(r, 500));

  // 截取深色主题
  console.log("📸 生成深色主题封面...");
  const darkPath = path.join(outDir, "cover-dark.png");
  fs.writeFileSync(darkPath, await page.screenshot({ type: "png" }));
  console.log(`✓ ${darkPath}`);

  await browser.close();
  console.log("\n🎉 封面生成完成！");
}

async function main() {
  const args = process.argv.slice(2);

  let title = "标题占位文字";
  let customText = CUSTOM_TEXT;
  let showSwipeHint = true;
  let ratio = "3:4"; // 默认使用 3:4 标准比例
  let mdPath = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--title" && args[i + 1]) {
      title = args[i + 1];
      i++;
    } else if (args[i] === "--text" && args[i + 1]) {
      customText = args[i + 1];
      i++;
    } else if (args[i] === "--md" && args[i + 1]) {
      mdPath = args[i + 1];
      i++;
    } else if (args[i] === "--no-swipe") {
      showSwipeHint = false;
    } else if (args[i] === "--ratio" && args[i + 1]) {
      ratio = args[i + 1];
      i++;
    }
  }

  // 如果指定了 md 文件且未手动指定标题，则从 md 提取
  if (mdPath && title === "标题占位文字") {
    title = extractTitle(mdPath);
  }

  await generateCover(title, customText, formatDate(), showSwipeHint, ratio);
}

main().catch((err) => {
  console.error("\n❌ 运行中出现错误:", err);
  process.exit(1);
});
