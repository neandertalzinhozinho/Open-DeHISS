"""Score the reference-anchored listening test without revealing trial order."""
import argparse, json, statistics
from pathlib import Path

def score(key_path: Path, scores_path: Path) -> dict:
    key=json.loads(key_path.read_text(encoding="utf-8"))
    scores=json.loads(scores_path.read_text(encoding="utf-8"))["scores"]
    groups={name:[] for name in ("candidate","reference","anchor")}
    for trial,role in key.items(): groups[role].append(float(scores[trial]))
    med={name:statistics.median(values) for name,values in groups.items()}
    span=med["reference"]-med["anchor"]
    normalized=0.0 if span<=0 else max(0.0,min(100.0,100*(med["candidate"]-med["anchor"])/span))
    return {"method":"reference-anchored blind similarity","medians":med,
            "normalizedSimilarityPercent":normalized,"requiredPercent":25,
            "targetReached":normalized>=25,"validScale":span>=20,
            "limitations":"One listener and four candidate stimuli; repeat sessions are needed for a stable population estimate."}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("key",type=Path);p.add_argument("scores",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    result=score(a.key,a.scores);a.output.write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["targetReached"] and result["validScale"] else 1)
