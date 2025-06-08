/**
 * 切换到模块化版本的脚本
 * 
 * 此脚本用于备份原有文件并启用新的模块化版本
 */

(function() {
    'use strict';
    
    console.log('🔧 准备切换到模块化版本...');
    
    // 检查是否已经是模块化版本
    if (window.location.search.includes('modular=true')) {
        console.log('✅ 已经是模块化版本');
        return;
    }
    
    // 显示切换提示
    const shouldSwitch = confirm(
        '是否切换到模块化版本？\n\n' +
        '模块化版本特性：\n' +
        '• 更好的代码组织结构\n' +
        '• 独立的功能模块\n' +
        '• 更易维护和扩展\n' +
        '• 更快的加载速度\n\n' +
        '点击"确定"切换到模块化版本\n' +
        '点击"取消"继续使用当前版本'
    );
    
    if (shouldSwitch) {
        // 重定向到模块化版本
        const newUrl = window.location.href + (window.location.search ? '&' : '?') + 'modular=true';
        window.location.href = newUrl;
    }
})();

// 如果是模块化版本，加载对应的脚本
if (window.location.search.includes('modular=true')) {
    // 动态加载模块化版本的主文件
    const script = document.createElement('script');
    script.type = 'module';
    script.src = './js/app-modular.js';
    script.onload = function() {
        console.log('✅ 模块化版本加载成功');
    };
    script.onerror = function() {
        console.error('❌ 模块化版本加载失败，回退到原版本');
        // 可以在这里添加回退逻辑
    };
    document.head.appendChild(script);
}

// 在页面上添加版本切换按钮
document.addEventListener('DOMContentLoaded', function() {
    const isModular = window.location.search.includes('modular=true');
    
    // 创建版本切换按钮
    const switchBtn = document.createElement('button');
    switchBtn.className = 'btn btn-outline-info btn-small version-switch-btn';
    switchBtn.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 10000;
        font-size: 12px;
        padding: 5px 10px;
    `;
    
    if (isModular) {
        switchBtn.textContent = '🔧 模块化版本';
        switchBtn.title = '当前使用模块化版本\n点击切换回原版本';
        switchBtn.onclick = function() {
            const newUrl = window.location.href.replace(/[?&]modular=true/, '');
            window.location.href = newUrl;
        };
    } else {
        switchBtn.textContent = '🚀 切换到模块化版本';
        switchBtn.title = '点击切换到模块化版本';
        switchBtn.onclick = function() {
            const newUrl = window.location.href + (window.location.search ? '&' : '?') + 'modular=true';
            window.location.href = newUrl;
        };
    }
    
    document.body.appendChild(switchBtn);
}); 