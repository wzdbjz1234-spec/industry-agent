# 阶段 14：作品集交付与全项目验收

## 完成内容

- README 改为答案优先：先说明事件驱动业务闭环，再说明 EfficientAD/Adapter 边界。
- 增加 `docker-compose.yml`、API/Web Dockerfile、健康检查、CI 和一键 Seed/Fast Replay 脚本。
- 增加系统架构图、事件时序图、Case 状态机、Demo Runbook、面试讲解稿、简历描述和数据真实性/限制声明。
- 增加 Playwright 关键流程测试：加载工作台、触发光照 Demo、查看 Worker 运维页和 Eval/ROI 页。
- 将阶段 00–13 的日志、脚本、Schema、Golden Example、Eval 报告和测试结果纳入最终验收报告。

## 运行方式

```powershell
docker compose up --build
uv run python scripts/seed_demo.py
cd web
npm run test:e2e
```

## 交付边界

仓库交付的是可复现的本地 Demo、自动化录制脚本和演示 Runbook；未包含真实企业数据、真实客户收益声明或预录制视频文件。视频录制按 `docs/portfolio/demo-runbook.md` 执行即可复现。
