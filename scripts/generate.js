const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

// ============ 可配置参数 ============
const CUSTOM_TEXT = "曲奇"; // 左下角自定义文字

// 图片尺寸预设（基于小红书推荐尺寸）
const RATIO_PRESETS = {
  "9:16": { width: 600, height: 1067, scale: 2 }, // 全屏图，输出 1200x2134
  "3:4": { width: 720, height: 960, scale: 2 }, // 标准图，输出 1440x1920
};
const TOP_PADDING = 60; // 顶部留白
const BOTTOM_PADDING = 60; // 底部留白
// ===================================

async function generateImages(ratio = "9:16") {
  console.log("🚀 脚本开始执行...");
  console.log(`📐 使用比例: ${ratio}`);

  // 获取尺寸预设
  const preset = RATIO_PRESETS[ratio];
  if (!preset) {
    console.error(
      `❌ 不支持的比例: ${ratio}，支持的比例: ${Object.keys(RATIO_PRESETS).join(", ")}`,
    );
    process.exit(1);
  }
  const PAGE_WIDTH = preset.width;
  const PAGE_HEIGHT = preset.height;
  const SCALE_FACTOR = preset.scale;

  const outDir = path.resolve("./assets/_attachments");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
    console.log("📁 创建了 _attachments 文件夹");
  }

  // 清理旧的图片文件，避免残留
  const oldFiles = fs
    .readdirSync(outDir)
    .filter((f) => f.match(/^xhs-(light|dark)-\d+\.png$/));
  if (oldFiles.length > 0) {
    oldFiles.forEach((f) => {
      const filePath = path.join(outDir, f);
      fs.unlinkSync(filePath);
    });
    console.log(`🗑️ 已清理 ${oldFiles.length} 个旧图片文件`);
  }

  console.log("⏳ 正在启动浏览器...");
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "/usr/bin/chromium",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  console.log("✅ 浏览器启动成功");

  const page = await browser.newPage();
  // 如果有临时 HTML 文件，使用它；否则使用默认模板
  const htmlPath = process.env.XHS_HTML_PATH
    ? "file://" + path.resolve(process.env.XHS_HTML_PATH)
    : "file://" + path.resolve("./assets/xhs-preview.html");

  // 使用 deviceScaleFactor 实现高清输出
  await page.setViewport({
    width: 1200,
    height: 900,
    deviceScaleFactor: SCALE_FACTOR,
  });

  console.log(`🌐 正在打开页面: ${htmlPath}`);
  await page.goto(htmlPath, { waitUntil: "networkidle0", timeout: 60000 });
  console.log("✅ 页面加载完成，等待字体...");

  // 等待所有字体加载完成
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  console.log("✅ 字体加载完成");

  // 额外等待确保渲染
  await new Promise((r) => setTimeout(r, 500));

  // 先调整 HTML 容器宽度匹配页面宽度
  await page.evaluate((width) => {
    const container = document.querySelector(".container");
    if (container) {
      container.style.width = width + "px";
    }
  }, PAGE_WIDTH);
  console.log(`📐 已调整容器宽度为 ${PAGE_WIDTH}px`);

  const pageWidth = PAGE_WIDTH;
  const pageHeight = PAGE_HEIGHT;
  const topPadding = TOP_PADDING;
  const bottomPadding = BOTTOM_PADDING;
  const contentHeight = pageHeight - topPadding - bottomPadding; // 每页内容高度

  // 获取所有内容元素的边界信息
  const elementsInfo = await page.evaluate(() => {
    const container = document.querySelector(".container");
    if (!container) return null;

    container.style.height = "auto";
    container.style.overflow = "visible";

    const containerRect = container.getBoundingClientRect();
    const elements = container.querySelectorAll(
      "h1, h2, h3, p, ul, ol, blockquote, table, .data-box, .insight, .quote, hr",
    );

    const items = [];
    elements.forEach((el, index) => {
      // 跳过 data-box, blockquote, insight 内部的子元素（避免重复）
      const parent = el.closest(".data-box, blockquote, .insight");
      if (parent && parent !== el) {
        return; // 跳过嵌套的子元素
      }

      const rect = el.getBoundingClientRect();
      items.push({
        index,
        tagName: el.tagName,
        top: Math.round(rect.top - containerRect.top), // 相对于容器顶部的位置
        bottom: Math.round(rect.bottom - containerRect.top),
        height: Math.round(rect.height),
        text:
          el.textContent.substring(0, 50) +
          (el.textContent.length > 50 ? "..." : ""),
      });
    });

    return {
      containerX: Math.round(containerRect.x),
      containerY: Math.round(containerRect.y),
      containerWidth: Math.round(containerRect.width),
      containerHeight: Math.round(containerRect.height),
      elements: items,
    };
  });

  if (!elementsInfo) {
    throw new Error("❌ 未找到 .container 元素！");
  }

  console.log("📦 容器高度:", elementsInfo.containerHeight);
  console.log("📄 内容元素数量:", elementsInfo.elements.length);
  console.log("📏 每页内容高度:", contentHeight, "px");
  console.log("📋 元素详情:");
  elementsInfo.elements.forEach((el, i) => {
    console.log(
      `  [${i}] ${el.tagName}: top=${el.top}, bottom=${el.bottom}, height=${el.height} | "${el.text}"`,
    );
  });

  // 计算分页点：基于元素边界，确保不丢失内容
  function calculatePageBreaks(elements, contentHeight) {
    const pages = [];
    let currentPageStart = elements.length > 0 ? elements[0].top : 0;
    let currentElements = [];

    for (let i = 0; i < elements.length; i++) {
      const el = elements[i];

      // 计算当前页结束位置
      const pageEnd = currentPageStart + contentHeight;

      // 如果元素底部超出当前页
      if (el.bottom > pageEnd) {
        // 先保存当前页（如果有内容）
        if (currentElements.length > 0) {
          pages.push({
            startTop: currentElements[0].top,
            endBottom: currentElements[currentElements.length - 1].bottom,
            elements: [...currentElements],
          });
          currentElements = [];
        }
        // 当前元素作为新页的起始
        currentPageStart = el.top;
      }

      // 无论是否换页，都要把当前元素加入
      currentElements.push(el);
    }

    // 保存最后一页
    if (currentElements.length > 0) {
      pages.push({
        startTop: currentElements[0].top,
        endBottom: currentElements[currentElements.length - 1].bottom,
        elements: [...currentElements],
      });
    }

    return pages;
  }

  const pages = calculatePageBreaks(elementsInfo.elements, contentHeight);
  console.log(`📑 分页结果: ${pages.length} 页`);
  pages.forEach((p, i) => {
    console.log(
      `  第${i + 1}页: 元素 ${p.elements[0].index} - ${p.elements[p.elements.length - 1].index}, 高度: ${p.endBottom - p.startTop}px`,
    );
  });

  // 截图并裁剪
  console.log("\n📸 生成浅色主题图片...");
  const fullBuffer = await page.screenshot({ fullPage: true });
  const fullMeta = await sharp(fullBuffer).metadata();
  console.log(`📐 完整截图尺寸: ${fullMeta.width} x ${fullMeta.height}`);

  const lightBg = { r: 249, g: 248, b: 244 }; // 与 HTML --card-bg 一致
  const darkBg = { r: 7, g: 6, b: 5 }; // 与 HTML --card-bg 一致

  // 创建文字覆盖层（左下角自定义文字 + 右下角页码）
  // 文字与正文对齐：正文区域 padding 为 55px
  async function createTextOverlay(
    pageIndex,
    totalPages,
    bgColor,
    textColor,
    scaledWidth,
    scaledBottomPadding,
    scaleFactor,
  ) {
    const contentPadding = 55 * scaleFactor; // 与 HTML .content 的 padding 一致
    const textMargin = 5 * scaleFactor; // 文字额外边距
    const textLeft = contentPadding + textMargin;
    const textRight = scaledWidth - contentPadding - textMargin;
    const fontSize = 14 * scaleFactor;
    // 使用 SVG 创建文字
    const svg = `
      <svg width="${scaledWidth}" height="${scaledBottomPadding}">
        <style>
          .text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: ${fontSize}px; fill: ${textColor}; opacity: 0.5; }
        </style>
        <text x="${textLeft}" y="${scaledBottomPadding * 0.6}" class="text">${CUSTOM_TEXT}</text>
        <text x="${textRight}" y="${scaledBottomPadding * 0.6}" class="text" text-anchor="end">${pageIndex + 1}/${totalPages}</text>
      </svg>
    `;
    return Buffer.from(svg);
  }

  async function generatePage(
    buffer,
    pageIndex,
    totalPages,
    startTop,
    endBottom,
    bgColor,
    textColor,
    themeName,
  ) {
    const containerY = elementsInfo.containerY;
    const containerX = elementsInfo.containerX;
    const containerWidth = elementsInfo.containerWidth;

    // 计算实际需要截取的高度
    const extractHeight = endBottom - startTop;

    // 缩放后的尺寸
    const scaledWidth = pageWidth * SCALE_FACTOR;
    const scaledHeight = pageHeight * SCALE_FACTOR;
    const scaledTopPadding = topPadding * SCALE_FACTOR;
    const scaledBottomPadding = bottomPadding * SCALE_FACTOR;
    const scaledContainerX = containerX * SCALE_FACTOR;
    const scaledContainerY = containerY * SCALE_FACTOR;
    const scaledContainerWidth = containerWidth * SCALE_FACTOR;
    const scaledStartTop = startTop * SCALE_FACTOR;
    const scaledExtractHeight = extractHeight * SCALE_FACTOR;

    // 截取内容区域
    const contentBuffer = await sharp(buffer)
      .extract({
        left: scaledContainerX,
        top: scaledContainerY + scaledStartTop,
        width: scaledContainerWidth,
        height: scaledExtractHeight,
      })
      .toBuffer();

    // 创建文字覆盖层（已缩放）
    const textOverlay = await createTextOverlay(
      pageIndex,
      totalPages,
      bgColor,
      textColor,
      scaledWidth,
      scaledBottomPadding,
      SCALE_FACTOR,
    );

    // 创建带留白的完整图片
    const fileName =
      "assets/_attachments/xhs-" +
      themeName +
      "-" +
      String(pageIndex + 1).padStart(2, "0") +
      ".png";

    await sharp({
      create: {
        width: scaledWidth,
        height: scaledHeight,
        channels: 3,
        background: bgColor,
      },
    })
      .composite([
        { input: contentBuffer, top: scaledTopPadding, left: 0 },
        {
          input: textOverlay,
          top: scaledHeight - scaledBottomPadding,
          left: 0,
        },
      ])
      .png()
      .toFile(fileName);

    console.log(`✓ ${fileName} (${scaledWidth}x${scaledHeight})`);
  }

  // 生成浅色主题图片
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    await generatePage(
      fullBuffer,
      i,
      pages.length,
      p.startTop,
      p.endBottom,
      lightBg,
      "#888888",
      "light",
    );
  }

  // 切换到深色主题
  console.log("\n切换到深色主题...");
  await page.evaluate(() => {
    document.documentElement.setAttribute("data-theme", "dark");
  });
  await new Promise((r) => setTimeout(r, 300));

  const darkBuffer = await page.screenshot({ fullPage: true });
  console.log("✅ 深色全屏截图完成，开始裁剪...");

  // 生成深色主题图片
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    await generatePage(
      darkBuffer,
      i,
      pages.length,
      p.startTop,
      p.endBottom,
      darkBg,
      "#8a8275",
      "dark",
    );
  }

  await browser.close();
  console.log("\n🎉 全部完成！");
}

// 解析命令行参数
function parseArgs() {
  const args = process.argv.slice(2);
  let ratio = "3:4"; // 默认使用 3:4 标准比例

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--ratio" && args[i + 1]) {
      ratio = args[i + 1];
      i++;
    }
  }

  return { ratio };
}

const { ratio } = parseArgs();

// 主流程
generateImages(ratio).catch((err) => {
  console.error("\n❌ 运行中出现错误:");
  console.error(err);
  process.exit(1);
});
