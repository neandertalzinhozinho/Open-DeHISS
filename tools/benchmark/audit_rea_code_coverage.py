"""Fail-closed audit of REA-derived DSP source coverage.

Coverage is deliberately about active DSP source, not the editor, tests, build
files, or generated code.  An evidence artifact must exist for every mapped
REA operation before its source module counts as derived.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

TARGET_SHA256 = "ed7669d8981b6533da17b47c6d2c28d6f19a5a7cef77e749c332708c24c4ebea"
DERIVED = ("RecoveredMath.h", "RecoveredSynthesis.h", "DerivedChannel.h")
DSP = DERIVED + ("MultiResolutionChannel.h", "Denoiser.h")

# Distinct, useful REA operations represented by retained artifacts.  Several
# operations contribute to one artifact; paths are intentionally private and
# remain outside the public repository.
OPERATIONS = {
    "inventory_artifact": "rea-autodehiss-evidence/rea-session-bundle.json",
    "inspect_artifact": "REA_AUTODEHISS_PRELIMINAR.md",
    "inspect_pe_resources": "rea-pe-resources-evidence.json",
    "inspect_native_load_image": "rea-autodehiss-evidence/active-code-provenance.json",
    "list_procedures": "rea-autodehiss-active-evidence/ghidra-inventory.tsv",
    "list_strings": "rea-autodehiss-active-evidence/runtime-type-names.json",
    "search_procedures": "rea-autodehiss-active-evidence/ghidra-inventory.tsv",
    "search_strings": "rea-autodehiss-active-evidence/runtime-type-names.json",
    "procedure_pseudo_code": "ida93-rea-spectral-branch.json",
    "procedure_assembly": "rea-autodehiss-active-evidence/seed-disassembly.txt",
    "procedure_callees": "rea-autodehiss-active-evidence/function-1a2064f0.txt",
    "procedure_callers": "rea-autodehiss-deep-evidence/dossier-1a2078a0.txt",
    "procedure_references": "rea-autodehiss-deep-evidence/dossier-1a205270.txt",
    "analyze_function": "ida93-rea-noise-median-long.json",
    "read_function_instructions": "rea-autodehiss-active-evidence/seed-disassembly.txt",
    "xrefs": "rea-autodehiss-active-evidence/core-vtable-code-refs.json",
    "read_bytes": "rea-autodehiss-active-evidence/fft-scale-constant.json",
    "address_to_file_offset": "rea-autodehiss-evidence/pe-static.json",
    "resolve_native_call_targets": "rea-autodehiss-active-evidence/dispatch-inverse.json",
    "inspect_native_data_type": "rea-autodehiss-active-evidence/vtables.json",
}

def code_lines(path: Path) -> int:
    count=0;block=False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if block:
            if "*/" in line:block=False
            continue
        if line.startswith("/*"):
            block="*/" not in line;continue
        if not line or line.startswith("//") or line in ("{","}"):continue
        count+=1
    return count

def audit(repo: Path, evidence: Path) -> dict:
    missing=[name for name,rel in OPERATIONS.items() if not (evidence/rel).is_file()]
    lines={name:code_lines(repo/name) for name in DSP}
    derived=sum(lines[name] for name in DERIVED);total=sum(lines.values())
    fraction=derived/total if total else 0
    ids=[]
    for rel in ("ida93-rea-noise-median-long.json","ida93-rea-spectral-branch.json","rea-pe-resources-evidence.json"):
        path=evidence/rel
        if path.is_file():
            match=re.search(r'"evidence_id"\s*:\s*"(ev_[0-9a-f]{64})"',path.read_text(encoding="utf-8",errors="replace"))
            if match:ids.append(match.group(1))
    return {"targetSha256":TARGET_SHA256,"distinctReaOperations":len(OPERATIONS),
            "requiredReaOperations":20,"operationEvidence":OPERATIONS,"missingEvidence":missing,
            "dspCodeLines":lines,"reaDerivedCodeLines":derived,"totalDspCodeLines":total,
            "reaDerivedFraction":fraction,"requiredFraction":.5,
            "canonicalEvidenceIds":ids,
            "passed":not missing and len(OPERATIONS)>=20 and fraction>=.5,
            "limitations":"Line coverage proves implementation provenance, not behavioral or perceptual equivalence."}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("repo",type=Path);p.add_argument("evidence",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    result=audit(a.repo,a.evidence);a.output.write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["passed"] else 1)
