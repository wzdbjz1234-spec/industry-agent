@echo off
rem EfficientAD UI 免安装启动（Windows 双击/命令行均可用）
cd /d %~dp0
python run_ui.py %*
