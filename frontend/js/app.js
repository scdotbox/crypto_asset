/**
 * 兼容浏览器直接使用的版本
 */

// 全局应用实例
let app = null;

/**
 * 动态导入模块化版本并初始化应用
 */
async function initializeApp() {
    try {
        // 动态导入模块化应用
            const { default: CryptoAssetManagerModular } = await import('./app-modular.js');
    
    // 创建应用实例
    app = new CryptoAssetManagerModular();
        
        // 将应用实例设置为全局可访问
        window.app = app;
        
        // 异步初始化应用
        await app.initialize();
        
        console.log('✅ 加密货币资产管理程序已启动 (模块化版本)');
    } catch (error) {
        console.error('❌ 应用初始化失败:', error);
        
        // 如果模块化版本加载失败，显示错误信息
        const errorMessage = document.createElement('div');
        errorMessage.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #ff4757;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        errorMessage.innerHTML = `
            <strong>⚠️ 应用加载失败</strong><br>
            请检查浏览器是否支持 ES6 模块，或联系开发者。<br>
            <small>错误: ${error.message}</small>
        `;
        document.body.appendChild(errorMessage);
        
        // 5秒后自动隐藏错误信息
        setTimeout(() => {
            errorMessage.remove();
        }, 5000);
    }
}

/**
 * 等待 DOM 加载完成后初始化应用
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

/**
 * 导出全局函数（用于 HTML 中的事件处理）
 */
window.getApp = () => app;

// 全局错误处理
window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的 Promise 拒绝:', event.reason);
}); 