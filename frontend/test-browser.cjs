#!/usr/bin/env node
/**
 * Playwright 浏览器测试脚本
 *
 * 使用方法：
 *   node test-browser.js                    # 运行基础测试
 *   node test-browser.js --url <url>        # 测试指定 URL
 *   node test-browser.js --screenshot       # 保存截图
 *   node test-browser.js --login            # 自动登录
 */

const { chromium } = require('playwright');

// 配置
const CONFIG = {
    browserPath: '/Users/zqy/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
    frontendUrl: 'http://localhost:5175/',
    backendUrl: 'http://localhost:8001',
    userId: '1000000030973949',
    screenshotDir: '/tmp',
};

// 解析命令行参数
const args = process.argv.slice(2);
const options = {
    url: args.includes('--url') ? args[args.indexOf('--url') + 1] : CONFIG.frontendUrl,
    screenshot: args.includes('--screenshot'),
    login: args.includes('--login'),
    verbose: args.includes('--verbose'),
};

/**
 * 运行浏览器测试
 */
async function runTest(testFn) {
    const browser = await chromium.launch({
        headless: true,
        executablePath: CONFIG.browserPath,
    });

    const page = await browser.newPage();
    const errors = [];

    // 监听控制台错误
    page.on('console', msg => {
        if (msg.type() === 'error') {
            const text = msg.text();
            // 忽略常见的无害错误
            if (!text.includes('favicon') && !text.includes('hydration')) {
                errors.push(text);
                if (options.verbose) {
                    console.log('⚠️  控制台错误:', text);
                }
            }
        }
    });

    // 监听页面错误
    page.on('pageerror', error => {
        errors.push(error.message);
        console.log('❌ 页面错误:', error.message);
    });

    try {
        console.log('🚀 启动浏览器测试...\n');
        const result = await testFn(page, browser);

        if (errors.length > 0) {
            console.log(`\n⚠️  发现 ${errors.length} 个错误`);
        } else {
            console.log('\n✅ 测试通过，无错误');
        }

        return { success: true, errors };
    } catch (error) {
        console.error('\n❌ 测试失败:', error.message);
        return { success: false, errors: [...errors, error.message] };
    } finally {
        await browser.close();
    }
}

/**
 * 基础测试：检查页面加载
 */
async function basicTest(page) {
    console.log('📋 基础测试：页面加载');

    await page.goto(options.url);
    await page.waitForLoadState('networkidle');

    const title = await page.title();
    console.log(`   标题: ${title}`);

    const bodyText = await page.textContent('body');
    console.log(`   内容长度: ${bodyText.length} 字符`);

    if (options.screenshot) {
        const path = `${CONFIG.screenshotDir}/test-basic.png`;
        await page.screenshot({ path, fullPage: true });
        console.log(`   📸 截图: ${path}`);
    }

    return { title, contentLength: bodyText.length };
}

/**
 * 登录测试：自动填写服务器地址和用户名
 */
async function loginTest(page) {
    console.log('📋 登录测试：自动登录');

    await page.goto(options.url);
    await page.waitForLoadState('networkidle');

    // 填写服务器地址
    const serverInput = await page.locator('input[placeholder="https://..."]');
    if (await serverInput.count() > 0) {
        await serverInput.fill(CONFIG.backendUrl);
        console.log('   ✓ 填写服务器地址');
    }

    // 填写用户名
    const usernameInput = await page.locator('input[placeholder="请输入用户名"]');
    if (await usernameInput.count() > 0) {
        await usernameInput.fill(CONFIG.userId);
        console.log('   ✓ 填写用户名');
    }

    // 点击开始使用按钮
    const startButton = await page.locator('button:has-text("开始使用")');
    if (await startButton.count() > 0) {
        await startButton.click();
        await page.waitForTimeout(3000);
        console.log('   ✓ 点击开始使用');
    }

    const currentUrl = page.url();
    console.log(`   当前 URL: ${currentUrl}`);

    if (options.screenshot) {
        const path = `${CONFIG.screenshotDir}/test-login.png`;
        await page.screenshot({ path, fullPage: true });
        console.log(`   📸 截图: ${path}`);
    }

    return { url: currentUrl };
}

/**
 * 引用测试：检查 References 超链接
 */
async function citationTest(page) {
    console.log('📋 引用测试：检查 References 超链接');

    // 先登录
    await loginTest(page);

    // 检查 References
    const bodyText = await page.textContent('body');
    const hasReferences = bodyText.includes('References');
    console.log(`   包含 References: ${hasReferences}`);

    // 查找 .md 文件按钮
    const mdButtons = await page.locator('button:has-text(".md")').allTextContents();
    console.log(`   .md 文件按钮数量: ${mdButtons.length}`);

    if (mdButtons.length > 0) {
        console.log(`   第一个按钮: ${mdButtons[0]}`);

        // 点击第一个按钮
        const firstButton = await page.locator('button:has-text(".md")').first();
        await firstButton.click();
        await page.waitForTimeout(2000);

        // 检查是否出现 Modal
        const hasModal = await page.locator('[role="dialog"]').count();
        console.log(`   出现 Modal: ${hasModal > 0}`);

        if (hasModal > 0) {
            const modalText = await page.locator('[role="dialog"]').textContent();
            console.log(`   Modal 内容长度: ${modalText.length}`);
        }

        if (options.screenshot) {
            const path = `${CONFIG.screenshotDir}/test-citation.png`;
            await page.screenshot({ path, fullPage: true });
            console.log(`   📸 截图: ${path}`);
        }

        return { hasReferences, mdButtonCount: mdButtons.length, hasModal };
    }

    return { hasReferences, mdButtonCount: 0, hasModal: false };
}

// 主函数
async function main() {
    console.log('='.repeat(50));
    console.log('Playwright 浏览器测试');
    console.log('='.repeat(50));
    console.log(`URL: ${options.url}`);
    console.log(`截图: ${options.screenshot}`);
    console.log(`登录: ${options.login}`);
    console.log('='.repeat(50));
    console.log('');

    if (options.login) {
        await runTest(loginTest);
    } else {
        await runTest(basicTest);
    }
}

// 运行测试
if (require.main === module) {
    main().catch(console.error);
}

module.exports = { runTest, basicTest, loginTest, citationTest, CONFIG };
