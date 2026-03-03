@echo off
REM 构建脚本 - Windows 版本
REM 用于在 Windows 中构建和部署 ripgrep-all MCP

setlocal enabledelayedexpansion

echo.
echo 🔨 开始构建 ripgrep-all MCP...
echo.

REM 检查 npm
where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ npm 未安装
    exit /b 1
)

REM 检查 rga
where rga >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  警告: ripgrep-all (rga) 未在 PATH 中
    echo 请确保已安装 rga: https://github.com/phiresky/ripgrep-all
)

echo 📦 检查依赖...
call npm --version

echo.
echo 📥 安装 npm 包...
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo ❌ npm install 失败
    exit /b 1
)

echo.
echo ✨ 运行代码检查...
call npm run lint
REM 忽略 lint 错误，继续构建

echo.
echo 📝 编译 TypeScript...
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 编译失败
    exit /b 1
)

echo.
echo 📚 构建输出:
dir dist\

echo.
echo ✅ 构建完成！
echo.
echo 后续步骤:
echo 1. 运行服务器: npm start
echo 2. 配置 MCP 客户端 (见 QUICK_START.md)
echo 3. 重启 MCP 客户端
echo.
echo 需要帮助？查看 QUICK_START.md
echo.

pause
