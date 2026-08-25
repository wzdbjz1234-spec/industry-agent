"""Validated Runbook registry with safe built-in fallback definitions."""

from __future__ import annotations

import json
from pathlib import Path

from quality_case_agent.contracts.investigation import ProposalStepContract
from quality_case_agent.contracts.runbook import (
    RunbookContract,
    RunbookHypothesisContract,
    RunbookProposalContract,
)
from quality_case_agent.domain.runbook.models import Runbook
from quality_case_agent.domain.runbook.validation import to_domain


def _proposal(
    title: str,
    reason: str,
    steps: list[tuple[str, str]],
) -> RunbookProposalContract:
    return RunbookProposalContract(
        title=title,
        reason=reason,
        steps=[
            ProposalStepContract(order=index, instruction=instruction, expected_evidence=evidence)
            for index, (instruction, evidence) in enumerate(steps, start=1)
        ],
        requested_role="QUALITY_ENGINEER",
        priority="HIGH",
        risk_level="LOW",
    )


def _builtins() -> tuple[RunbookContract, ...]:
    return (
        RunbookContract(
            runbook_id="fixture-offset-investigation",
            version="1.0",
            trigger_family="FIXTURE_OFFSET",
            required_tools=[
                "get_case_snapshot",
                "compare_quality_metrics",
                "get_representative_samples",
                "search_knowledge_base",
            ],
            knowledge_query="夹具 定位销 偏移 检查步骤 fixture positioning pin offset inspection",
            candidate_hypotheses=[
                RunbookHypothesisContract(
                    hypothesis_id="H-01",
                    title="夹具定位偏移或定位销状态异常",
                    description="NG样本在局部区域持续聚集，与夹具定位偏移的空间特征一致；仍需现场测量确认。",
                    default_confidence=0.86,
                    missing_evidence=["定位销间隙测量值", "基准件复测位置偏移量"],
                ),
            ],
            proposal=_proposal(
                "检查camera-01工位夹具定位状态",
                "当前Snapshot的区域聚集与适用夹具手册均支持优先检查定位销；历史案例仅作为C级经验，不作为根因证明。",
                [
                    ("测量定位销间隙", "定位销间隙测量值"),
                    ("使用基准件复测工件位置", "基准件位置偏移量"),
                    ("检查最近一次换线记录", "换线时间和操作记录"),
                ],
            ),
        ),
        RunbookContract(
            runbook_id="illumination-drift-investigation",
            version="1.0",
            trigger_family="ILLUMINATION_DRIFT",
            required_tools=[
                "get_case_snapshot",
                "compare_quality_metrics",
                "get_representative_samples",
                "search_knowledge_base",
            ],
            knowledge_query="光照 漂移 曝光 亮度 光源角度 增益 校准 illumination drift exposure brightness",
            candidate_hypotheses=[
                RunbookHypothesisContract(
                    hypothesis_id="H-ILL-01",
                    title="光照或曝光状态发生漂移",
                    description="异常分数和NG率整体抬升，同时缺少单一缺陷区域聚集；与光源或相机参数漂移特征一致。",
                    default_confidence=0.72,
                    missing_evidence=["当前光照强度记录", "相机曝光参数和光源角度"],
                ),
            ],
            proposal=_proposal(
                "检查光源、曝光与相机校准状态",
                "当前分数整体抬升且缺少单一空间聚集，适用光照维护手册支持优先检查亮度、光源角度和曝光参数。",
                [
                    ("测量当前光源亮度并检查光源角度", "光照强度记录和光源角度"),
                    ("核对相机曝光时间、增益和自动曝光状态", "相机曝光参数快照"),
                    ("使用基准件执行光照/相机校准复测", "校准前后基准件分数和图像"),
                ],
            ),
        ),
        RunbookContract(
            runbook_id="generic-investigation",
            version="1.0",
            trigger_family="DEFAULT",
            required_tools=["get_case_snapshot", "compare_quality_metrics", "search_knowledge_base"],
            knowledge_query="质量异常 排查步骤 工艺变化 检测模型",
            candidate_hypotheses=[
                RunbookHypothesisContract(
                    hypothesis_id="H-GENERIC-01",
                    title="当前质量指标存在待验证的共同原因",
                    description="当前事实与指标偏移形成候选问题方向，但不能在缺少现场证据时确定根因。",
                    default_confidence=0.45,
                    missing_evidence=["现场参数快照", "复测结果"],
                ),
            ],
            proposal=None,
        ),
    )


class RunbookRegistry:
    def __init__(self, runbooks: tuple[Runbook, ...] | None = None) -> None:
        self._runbooks = {runbook.trigger_family: runbook for runbook in (runbooks or self._load())}
        if "DEFAULT" not in self._runbooks:
            raise ValueError("Runbook registry requires a DEFAULT runbook")

    @classmethod
    def from_directory(cls, directory: Path) -> RunbookRegistry:
        loaded: list[Runbook] = []
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded.append(to_domain(RunbookContract.model_validate(payload)))
        return cls(tuple(loaded)) if loaded else cls()

    def get(self, trigger_family: str) -> Runbook:
        return self._runbooks.get(trigger_family, self._runbooks["DEFAULT"])

    def _load(self) -> tuple[Runbook, ...]:
        directory = Path(__file__).resolve().parents[5] / "knowledge_base" / "runbooks"
        if directory.is_dir():
            paths = sorted(directory.glob("*.json"))
            if paths:
                return tuple(
                    to_domain(RunbookContract.model_validate(json.loads(path.read_text(encoding="utf-8"))))
                    for path in paths
                )
        return tuple(to_domain(item) for item in _builtins())
