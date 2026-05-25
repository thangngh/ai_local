from __future__ import annotations

from ai_local.audit.store import AuditEvent
from ai_local.knowledge.models import EvidenceRank, EvidenceSignal
from ai_local.knowledge.ranker import rank_evidence
from ai_local.skills.models import (
    SkillInstallResult,
    SkillNextGate,
    SkillOutputDecision,
    SkillOutputEnvelope,
    SkillRuntimeEvidenceHandoff,
    SkillScriptRunResult,
)


def install_result_to_evidence(
    result: SkillInstallResult,
    *,
    audit_events: list[AuditEvent] | None = None,
) -> SkillRuntimeEvidenceHandoff:
    audit_refs = [_audit_ref(event) for event in audit_events or []]
    source_refs = _compact_refs([result.target_dir, result.staging_dir, *audit_refs])
    evidence_refs = _compact_refs([result.target_dir, *audit_refs])
    risk_flags = [] if result.decision in {"installed", "updated"} else [f"skill_install_{result.decision}"]
    envelope = SkillOutputEnvelope(
        skill_id=result.skill_id or "unknown-skill",
        output_kind="workflow",
        query=f"skill package {result.decision}",
        provider="skill_runtime",
        source_refs=source_refs,
        evidence_refs=evidence_refs,
        evidence_summary=result.reason,
        risk_flags=risk_flags,
        recommended_next_gate="evidence_rank",
    )
    rank = rank_evidence(_install_signal(result))
    return _handoff(envelope, rank, audit_refs=audit_refs)


def script_result_to_evidence(
    result: SkillScriptRunResult,
    *,
    audit_events: list[AuditEvent] | None = None,
    risk_flags: list[str] | None = None,
) -> SkillRuntimeEvidenceHandoff:
    audit_refs = [_audit_ref(event) for event in audit_events or []]
    source_refs = _compact_refs([result.cwd, *audit_refs])
    evidence_refs = _compact_refs([*audit_refs, _command_ref(result.command)])
    flags = list(risk_flags or [])
    if result.decision not in {"succeeded"}:
        flags.append(f"skill_script_{result.decision}")
    envelope = SkillOutputEnvelope(
        skill_id=result.package_id or "unknown-skill",
        output_kind="analysis",
        query=f"skill script {result.script_id}",
        provider="skill_runtime",
        source_refs=source_refs,
        evidence_refs=evidence_refs,
        evidence_summary=_script_summary(result),
        risk_flags=flags,
        recommended_next_gate="evidence_rank",
    )
    rank = rank_evidence(_script_signal(result, flags))
    return _handoff(envelope, rank, audit_refs=audit_refs)


def _handoff(
    envelope: SkillOutputEnvelope,
    rank: EvidenceRank,
    *,
    audit_refs: list[str],
) -> SkillRuntimeEvidenceHandoff:
    if "prompt_injection" in envelope.risk_flags:
        decision: SkillOutputDecision = "quarantine"
        next_gate: SkillNextGate = "quarantine"
        reason = "skill runtime evidence is prompt-injected"
    elif "deep_policy_shadowing" in envelope.risk_flags:
        decision = "stop"
        next_gate = "stop"
        reason = "skill runtime evidence shadows policy"
    elif rank.band == "reject":
        decision = "stop"
        next_gate = "stop"
        reason = "skill runtime evidence rejected by rank"
    elif rank.band == "weak":
        decision = "verify_more"
        next_gate = "knowledge_gate"
        reason = "skill runtime evidence is weak"
    else:
        decision = "rank_evidence"
        next_gate = "evidence_rank"
        reason = "skill runtime output is data until evidence ranked"
    return SkillRuntimeEvidenceHandoff(
        envelope=envelope,
        decision=decision,
        next_gate=next_gate,
        reason=reason,
        evidence_rank=rank.rank,
        evidence_band=rank.band,
        audit_refs=audit_refs,
        requires_audit=True,
    )


def _install_signal(result: SkillInstallResult) -> EvidenceSignal:
    if result.decision in {"installed", "updated"}:
        return EvidenceSignal(
            source_authority=24,
            evidence_strength=22,
            freshness=14,
            project_relevance=14,
            confirmation_weight=8,
        )
    if result.decision == "rolled_back":
        return EvidenceSignal(
            source_authority=20,
            evidence_strength=16,
            freshness=12,
            project_relevance=14,
            confirmation_weight=0,
            conflict_penalty=8,
        )
    return EvidenceSignal(
        source_authority=8,
        evidence_strength=8,
        freshness=8,
        project_relevance=10,
        confirmation_weight=0,
        conflict_penalty=10,
        noise_type="unknown_source",
    )


def _script_signal(result: SkillScriptRunResult, risk_flags: list[str]) -> EvidenceSignal:
    if "prompt_injection" in risk_flags:
        return EvidenceSignal(
            source_authority=30,
            evidence_strength=25,
            freshness=15,
            project_relevance=15,
            confirmation_weight=15,
            noise_type="prompt_injection",
        )
    if result.decision == "succeeded":
        return EvidenceSignal(
            source_authority=22,
            evidence_strength=20,
            freshness=14,
            project_relevance=14,
            confirmation_weight=6,
        )
    if result.decision in {"failed", "timed_out"}:
        return EvidenceSignal(
            source_authority=18,
            evidence_strength=14,
            freshness=12,
            project_relevance=12,
            confirmation_weight=0,
            conflict_penalty=8,
        )
    return EvidenceSignal(
        source_authority=8,
        evidence_strength=8,
        freshness=8,
        project_relevance=10,
        confirmation_weight=0,
        conflict_penalty=10,
        noise_type="unknown_source",
    )


def _script_summary(result: SkillScriptRunResult) -> str:
    output = result.stdout.strip() or result.stderr.strip()
    if not output:
        return result.reason
    return f"{result.reason}: {output[:300]}"


def _audit_ref(event: AuditEvent) -> str:
    return f"audit://{event.action}/{event.target}/{event.result}/{event.created_at}"


def _command_ref(command: list[str]) -> str | None:
    if not command:
        return None
    return "command://" + " ".join(command[:4])


def _compact_refs(refs: list[str | None]) -> list[str]:
    compact: list[str] = []
    for ref in refs:
        if ref and ref not in compact:
            compact.append(ref)
    return compact
