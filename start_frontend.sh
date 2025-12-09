cd frontend
# 优先使用 pnpm 启动, 如果没有安装 pnpm, 则使用 npm 启动
if command -v pnpm >/dev/null 2>&1; then
  pnpm run dev
else
  npm run dev
fi
