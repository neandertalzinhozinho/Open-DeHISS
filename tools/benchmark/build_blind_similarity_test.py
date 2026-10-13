"""Build a local, randomized listening test against licensed reference renders.

The generated test contains only audio already rendered by the user.  It does
not load, inspect, or redistribute the commercial plug-in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path


KINDS = ("original.wav", "added_-65.wav", "added_-55.wav", "added_step.wav")


def build(reference: Path, candidate: Path, anchor: Path, output: Path, seed: int) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    for directory in (reference, candidate, anchor):
        missing = [name for name in KINDS if not (directory / name).is_file()]
        if missing:
            raise FileNotFoundError(f"{directory}: missing {', '.join(missing)}")

    audio = output / "audio"
    audio.mkdir(parents=True)
    rng = random.Random(seed)
    trials = []
    sources = {"reference": reference, "candidate": candidate, "anchor": anchor}
    # Every stimulus has a candidate trial. Hidden references and anchors make
    # the listener's scale use measurable instead of trusting raw scores.
    schedule = [(kind, role) for kind in KINDS for role in ("candidate", "reference", "anchor")]
    rng.shuffle(schedule)
    for index, (kind, role) in enumerate(schedule, 1):
        ref_name = f"{index:02d}-A.wav"
        test_name = f"{index:02d}-B.wav"
        shutil.copy2(reference / kind, audio / ref_name)
        shutil.copy2(sources[role] / kind, audio / test_name)
        trials.append({"id": index, "stimulus": kind, "role": role,
                       "a": f"audio/{ref_name}", "b": f"audio/{test_name}"})

    public_trials = [{k: v for k, v in row.items() if k != "role"} for row in trials]
    key = {str(row["id"]): row["role"] for row in trials}
    (output / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps({
        "method": "reference-anchored blind similarity",
        "seed": seed,
        "trials": public_trials,
        "scoring": "100*(candidateMedian-anchorMedian)/(referenceMedian-anchorMedian), clipped 0..100",
        "threshold": 25,
    }, indent=2), encoding="utf-8")
    html = TEMPLATE.replace("__TRIALS__", json.dumps(public_trials, separators=(",", ":")))
    (output / "index.html").write_text(html, encoding="utf-8")
    digest = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    return {"trials": len(trials), "manifestSha256": digest, "output": str(output)}


TEMPLATE = r'''<!doctype html><meta charset="utf-8"><title>Open DeHISS — teste cego</title>
<style>body{font:17px system-ui;background:#17131d;color:#eee;max-width:820px;margin:35px auto;padding:0 20px}section{background:#261d32;padding:22px;border-radius:14px;margin:18px 0}button{font-size:17px;padding:10px 18px;margin:6px}input{width:100%}.muted{color:#bba9cc}</style>
<h1>Teste cego de similaridade</h1><p class="muted">Use fones. Compare B com a referência A e avalie apenas o resultado sonoro, de 0 (nada parecido) a 100 (indistinguível). O teste não revela se B é Open DeHISS, referência oculta ou áudio sem o processamento de referência.</p>
<main></main><button id="save">Salvar resultado</button>
<script>const trials=__TRIALS__,main=document.querySelector('main');let scores={};
for(const t of trials){const s=document.createElement('section');s.innerHTML=`<b>Rodada ${t.id} de ${trials.length}</b><br><button class=a>A: referência</button><button class=b>B: comparação</button><p>Similaridade: <output>50</output></p><input type=range min=0 max=100 value=50>`;const aud=new Audio();s.querySelector('.a').onclick=()=>{aud.src=t.a;aud.play()};s.querySelector('.b').onclick=()=>{aud.src=t.b;aud.play()};const range=s.querySelector('input'),out=s.querySelector('output');range.oninput=()=>{out.value=range.value;scores[t.id]=+range.value};scores[t.id]=50;main.appendChild(s)}
document.querySelector('#save').onclick=()=>{const blob=new Blob([JSON.stringify({format:'open-dehiss-blind-v1',scores},null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='blind-scores.json';a.click()};</script>'''


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("reference", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("anchor", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--seed", type=int, default=20261012)
    args = p.parse_args()
    print(json.dumps(build(args.reference, args.candidate, args.anchor, args.output, args.seed), indent=2))
