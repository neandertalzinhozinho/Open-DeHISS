"""Study packaging and offline UI behavior tests; synthetic fixtures are never human data."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

from build_blind_study import build


class BlindStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for role, scale in (("reference", .2), ("candidate", .3), ("anchor", .4)):
            wavfile.write(self.root / (role + ".wav"), 8000,
                          (scale * np.sin(np.arange(24000) * .1)).astype(np.float32))

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, count=1, split="pilot"):
        result = {"studyId": "test-listening-v2", "provenance": {
            "privateSourcePath": "C:/secret/voice.wav",
            "plugins": [{"name": "Open DeHISS", "version": "0.9", "sha256": "a" * 64,
                         "path": "C:/secret/plugin.vst3"}]}, "excerpts": []}
        for i in range(count):
            result["excerpts"].append({"id": f"e{i:02}", "sourceId": "voice",
                "startSeconds": float(i * 4), "endSeconds": i * 4 + 3, "condition": "original", "split": split,
                **{role: str(self.root / (role + ".wav")) for role in ("reference", "candidate", "anchor")}})
        return result

    def package(self, spec=None, folder="study", seed=20261013):
        source = self.root / (folder + ".json")
        source.write_text(json.dumps(spec or self.spec()), encoding="utf-8")
        return build(source, self.root / folder, seed)

    def test_manifests_hashes_balanced_and_no_public_answers(self):
        result = self.package(self.spec(12, "evaluation"))
        output = Path(result["output"])
        manifest, key = result["manifest"], result["key"]
        self.assertEqual(len(manifest["trials"]), 72)
        self.assertTrue(manifest["protocol"]["confirmatoryEligible"])
        self.assertEqual(key["manifestSha256"], hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest())
        self.assertEqual(key["protocol"]["requiredPercent"], 9)
        self.assertEqual(json.loads((output / "private/key.json").read_text(encoding="utf-8")), key)
        for trial in manifest["trials"]:
            for side in ("a", "b"):
                self.assertEqual(hashlib.sha256((output / trial[side]).read_bytes()).hexdigest(), trial["sha256" + side.upper()])
            self.assertNotIn("role", trial)
        for session in ("s1", "s2"):
            for excerpt in manifest["excerpts"]:
                roles = [t["role"] for t in key["trials"] if t["sessionId"] == session and t["excerptId"] == excerpt["id"]]
                self.assertCountEqual(roles, ["reference", "candidate", "anchor"])
        html = (output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("C:/secret", html)
        self.assertNotIn('"role":', html)
        self.assertNotIn('"seed":', html)
        self.assertNotIn("private/key.json", html)
        self.assertNotIn("value=\"50\"", html)
        self.assertFalse((output / "scores.json").exists())

    def test_fixed_seed_is_reproducible_and_sessions_have_different_orders(self):
        a = self.package(self.spec(4), "a")
        b = self.package(self.spec(4), "b")
        self.assertEqual(a["manifest"], b["manifest"])
        with self.assertRaisesRegex(ValueError, "fixed v2 protocol"):
            self.package(self.spec(4), "c", 11)
        self.assertFalse((self.root / "c").exists())
        self.assertNotEqual([(x["excerptId"], x["role"]) for x in a["key"]["trials"] if x["sessionId"] == "s1"],
                            [(x["excerptId"], x["role"]) for x in a["key"]["trials"] if x["sessionId"] == "s2"])

    def test_no_overwrite(self):
        result = self.package()
        before = (Path(result["output"]) / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.package()
        self.assertEqual(before, (Path(result["output"]) / "manifest.json").read_bytes())

    def test_pilot_overlap_allowed_and_insufficient_for_confirmatory(self):
        spec = self.spec(4)
        for e in spec["excerpts"]:
            e["startSeconds"], e["endSeconds"] = 0, 3
        result = self.package(spec)
        self.assertEqual(len(result["manifest"]["trials"]), 24)
        self.assertFalse(result["manifest"]["protocol"]["confirmatoryEligible"])
        self.assertEqual(result["manifest"]["protocol"]["evaluationExcerptCount"], 0)
        self.assertEqual(result["manifest"]["protocol"]["status"], "pilot-insufficient-excerpts")

    def test_invalid_specs_fail_before_creating_output(self):
        changes = [lambda s: s.update(excerpts=[]),
                   lambda s: s["excerpts"][0].update(reference="relative.wav"),
                   lambda s: s["excerpts"][0].update(candidate=str(self.root / "missing.wav")),
                   lambda s: s["excerpts"][0].update(startSeconds=float("nan")),
                   lambda s: s["excerpts"][0].update(endSeconds=5),
                   lambda s: s["excerpts"][0].update(split="training"),
                   lambda s: s["excerpts"].append(dict(s["excerpts"][0]))]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                spec = self.spec()
                change(spec)
                with self.assertRaises(ValueError):
                    self.package(spec, str(i))
                self.assertFalse((self.root / str(i)).exists())

    def test_evaluation_cannot_overlap_or_reuse_pilot(self):
        for first_split in ("pilot", "evaluation"):
            spec = self.spec(2, "evaluation")
            spec["excerpts"][0]["split"] = first_split
            spec["excerpts"][1].update(startSeconds=0, endSeconds=3)
            with self.assertRaisesRegex(ValueError, "overlap"):
                self.package(spec)

    def test_mismatched_audio_and_nonfinite_audio_rejected(self):
        wavfile.write(self.root / "candidate.wav", 8000, np.zeros(799, np.float32))
        with self.assertRaisesRegex(ValueError, "must match"):
            self.package()
        wavfile.write(self.root / "candidate.wav", 8000, np.full(24000, np.nan, np.float32))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.package()

    def test_short_evaluation_refused_before_output_creation(self):
        spec = self.spec(12, "evaluation")
        spec["excerpts"][0]["endSeconds"] = 2.9
        with self.assertRaisesRegex(ValueError, "at least 3 seconds"):
            self.package(spec)
        self.assertFalse((self.root / "study").exists())

    @unittest.skipUnless(shutil.which("node"), "Node is needed to execute browser logic with a DOM/audio test double")
    def test_ui_requires_full_playback_explicit_rating_and_two_sessions(self):
        result = self.package()
        # VM exercises real emitted JavaScript. Audio/DOM are deterministic test doubles;
        # this verifies gating/export/resume, not audio hardware or browser codec support.
        harness = r"""
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const html=fs.readFileSync(process.argv[1],'utf8');
const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const storage={}; let nodes, audios, blobs, context;
function initialize(){
 nodes={};audios=[];blobs=[];
 function el(id){return nodes[id] ||= {value:'',disabled:false,hidden:false,textContent:'',addEventListener(n,fn){this[n]=fn;}};}
 context=vm.createContext({console,Date,JSON,Number,Object,Set,Promise,Error,
  document:{getElementById:el,createElement(){return {click(){}};}},
  localStorage:{getItem(k){return storage[k]||null},setItem(k,v){storage[k]=v}},
  Audio:class{constructor(path){this.path=path;audios.push(this)}play(){return Promise.resolve()}pause(){this.paused=true}},
  Blob:class{constructor(parts){blobs.push(parts.join(''))}},URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout(){}});
 vm.runInContext(script,context);
}
function latest(){return audios.at(-1)}
function playBoth(){nodes.playA.onclick();assert.equal(latest().volume,1);latest().onended();nodes.playB.onclick();latest().onended();}
function rate(value){nodes.rating.value=value;nodes.rating.input();nodes.next.onclick()}
function snapshot(){return JSON.parse(Object.values(storage)[0]);}
initialize();
assert.equal(Object.keys(snapshot().scores).length,0);
nodes.exportPartial.onclick();assert.equal(JSON.parse(blobs.at(-1)).completion,'pending');
nodes.listener.value='Synthetic UI test';nodes.start.onclick();
assert.equal(nodes.rating.value,'');assert.equal(nodes.rating.disabled,true);assert.equal(nodes.next.disabled,true);
rate('50');assert.equal(Object.keys(snapshot().scores).length,0);
nodes.playA.onclick();const interrupted=latest();nodes.playB.onclick();assert.equal(interrupted.paused,true);
interrupted.onended();latest().onended();assert.equal(nodes.rating.disabled,true);
nodes.playA.onclick();latest().onseeking();latest().onended();assert.equal(nodes.rating.disabled,true);
nodes.playA.onclick();latest().onended();assert.equal(nodes.rating.disabled,false);
rate('');assert.equal(Object.keys(snapshot().scores).length,0);
rate('101');assert.equal(Object.keys(snapshot().scores).length,0);
rate('-1');assert.equal(Object.keys(snapshot().scores).length,0);
rate('NaN');assert.equal(Object.keys(snapshot().scores).length,0);
rate('0');assert.equal(Object.keys(snapshot().scores).length,1);assert.equal(nodes.rating.value,'');
initialize();assert.equal(Object.keys(snapshot().scores).length,1);assert.equal(nodes.rating.disabled,true);
playBoth();rate('80');playBoth();rate('90');
assert.equal(nodes.welcome.hidden,false);assert.equal(snapshot().sessions.s2,undefined);
assert.ok(snapshot().sessions.s1.completedAt);
nodes.exportFinal.onclick();assert.equal(blobs.length,0);
nodes.start.onclick();playBoth();rate('60');playBoth();rate('70');playBoth();rate('90');
assert.equal(nodes.finished.hidden,false);assert.ok(snapshot().sessions.s2.completedAt);
nodes.exportFinal.onclick();const exported=JSON.parse(blobs.at(-1));
assert.equal(exported.completion,'complete');assert.equal(Object.keys(exported.scores).length,6);
assert.ok(Object.values(exported.scores).every(s=>s.playedA===true&&s.playedB===true&&s.ratedAt));
assert.equal(exported.format,'open-dehiss-blind-scores-v2');
console.log('UI playback, explicit scores, resume, session break and export gating passed');
"""
        completed = subprocess.run([shutil.which("node"), "-e", harness, str(Path(result["output"]) / "index.html")],
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for end-to-end browser export testing")
    def test_builder_browser_export_and_scorer_end_to_end_synthetic_fixture(self):
        from score_blind_similarity import score

        result = self.package(self.spec(12, "evaluation"))
        output = Path(result["output"])
        # Answers are supplied ONLY in this temporary synthetic test harness, never
        # in the generated UI or in real study output. This is a software contract test.
        harness = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync(process.argv[1],'utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const key=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const nodes={},storage={};let lastAudio,exported,tick=Date.parse('2026-10-13T12:00:00Z');
class Clock extends Date{constructor(...args){super(...(args.length?args:[tick+=1000]));}}
function el(id){return nodes[id] ||= {value:'',hidden:false,disabled:false,textContent:'',addEventListener(n,fn){this[n]=fn;}};}
const context=vm.createContext({Date:Clock,JSON,Number,Object,Set,Promise,Error,
 document:{getElementById:el,createElement(){return {click(){}}}},
 localStorage:{getItem(k){return storage[k]||null},setItem(k,v){storage[k]=v}},
 Audio:class{constructor(){lastAudio=this}pause(){}play(){return Promise.resolve()}},
 Blob:class{constructor(parts){exported=parts.join('')}},URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout(){}});
vm.runInContext(script,context);
nodes.listener.value='SYNTHETIC AUTOMATED TEST - NOT HUMAN EVIDENCE';
for(const trial of key.trials){
 if(!nodes.welcome.hidden)nodes.start.onclick();
 nodes.playA.onclick();lastAudio.onended();nodes.playB.onclick();lastAudio.onended();
 const index=Number(trial.excerptId.slice(1));
 nodes.rating.value=String(trial.role==='reference'?96+index%4:trial.role==='anchor'?10+index%7:35+index);
 nodes.rating.input();nodes.next.onclick();
}
assert.equal(nodes.finished.hidden,false);nodes.exportFinal.onclick();
assert.equal(JSON.parse(exported).completion,'complete');
process.stdout.write(exported);
"""
        completed = subprocess.run([shutil.which("node"), "-e", harness, str(output / "index.html"),
                                    str(output / "private/key.json")], capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        exported = self.root / "SYNTHETIC-TEST-ONLY-scores.json"
        exported.write_text(completed.stdout, encoding="utf-8")
        ratings = json.loads(completed.stdout)
        self.assertEqual(len(ratings["scores"]), 72)
        report = score(output / "private/key.json", exported)
        self.assertTrue(report["targetReached"], report)
        self.assertEqual(report["decision"], "met")


if __name__ == "__main__":
    unittest.main()
