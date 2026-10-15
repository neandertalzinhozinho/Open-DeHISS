import unittest
import json
import tempfile
from pathlib import Path
import numpy as np
from score_objective_voice import agreement,evaluate,_render_records
from prepare_blind_pilot import KINDS,digest
from voice_injection import write_wav

class ObjectiveTests(unittest.TestCase):
    def test_identity_and_gain_error(self):
        x=np.random.default_rng(3).normal(0,.02,(48000,2))
        self.assertEqual(agreement(x,x,48000)['worstChannelAgreementPercent'],100)
        self.assertEqual(agreement(x,x*.5,48000)['worstChannelAgreementPercent'],0)
        self.assertAlmostEqual(agreement(x,x*.5,48000)['channels'][0]['medianAbsoluteSpectralErrorDb'],6.020599913,places=6)
    def test_invalid_and_empty_reference(self):
        with self.assertRaises(ValueError): agreement(np.zeros((48000,2)),np.zeros((48000,2)),48000)
        with self.assertRaises(ValueError): agreement(np.zeros((48000,2)),np.zeros((10,2)),48000)

    def test_phase_inversion_exposes_nonperceptual_limit(self):
        x=np.random.default_rng(8).normal(0,.02,(48000,2))
        self.assertEqual(agreement(x,-x,48000)['worstChannelAgreementPercent'],100)
        self.assertGreater(np.max(abs(x-(-x))),.1)

    def test_candidate_silence_does_not_match_active_reference(self):
        x=np.random.default_rng(8).normal(0,.02,(48000,2))
        self.assertEqual(agreement(x,np.zeros_like(x),48000)['worstChannelAgreementPercent'],0)

    def test_gain_threshold_and_worst_channel(self):
        x=np.random.default_rng(8).normal(0,.02,(48000,2))
        self.assertEqual(agreement(x,x*10**(.99/20),48000)['worstChannelAgreementPercent'],100)
        y=x.copy();y[:,1]*=10**(1.01/20)
        result=agreement(x,y,48000)
        self.assertEqual(result['channels'][0]['agreementPercent'],100)
        self.assertEqual(result['worstChannelAgreementPercent'],0)

    def test_nonfinite_and_short_audio_or_invalid_rate_rejected(self):
        x=np.random.default_rng(8).normal(0,.02,(48000,2))
        for value in (np.nan,np.inf,-np.inf):
            broken=x.copy();broken[0,0]=value
            for a,b in ((x,broken),(broken,x)):
                with self.assertRaises(ValueError): agreement(a,b,48000)
        for rate in (0,-1,8000,48000.5,True):
            with self.assertRaises(ValueError): agreement(x,x,rate)
        for invalid in (np.empty((0,2)),x[:2047],np.empty((5000,0)),x[:,0]):
            with self.assertRaises(ValueError): agreement(invalid,invalid,48000)

    def test_below_reference_floor_is_inconclusive(self):
        x=np.random.default_rng(8).normal(0,1e-12,(48000,2))
        with self.assertRaisesRegex(ValueError,'No reference cells'): agreement(x,x,48000)


class ProvenanceTests(unittest.TestCase):
    """Synthetic fixtures test validation; they are never study results."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.x=np.random.default_rng(43).normal(0,.02,(96000,2)).astype(np.float32)
        source=self.root/'supplied.wav';write_wav(source,self.x,48000)
        (self.root/'inputs').mkdir()
        for name in KINDS: write_wav(self.root/'inputs'/name,self.x,48000)
        self.protocol={'sourceSha256':digest(source),'attenuationDb':-26,'biasDb':6,'auto':True,'plugins':{}}
        self.evidence={'source':{'path':str(source),'sha256':digest(source)},
                       'inputs':{name:digest(self.root/'inputs'/name) for name in KINDS},'roles':{}}
        for role in ('open','cedar'):
            dest=self.root/role;dest.mkdir()
            bundle=self.root/(role+'.vst3');binary=bundle/'Contents/x86_64-win'/bundle.name
            binary.parent.mkdir(parents=True);binary.write_bytes(b'fixture plugin')
            host=self.root/(role+'-fixture-host.exe');host.write_bytes(b'fixture host')
            self.protocol['plugins'][role]={'path':str(binary),'sha256':digest(binary)}
            lines=[]
            params=({'Attenuation':(.35,'-26.00'),'Bias':(.8,'6.00'),'Low Frequency Bias':(.5,'0.00'),
                     'Automatic Threshold':(1,'on'),'Master Bypass':(0,'bypass')} if role=='cedar' else
                    {'Atenuacao (dB)':(.35,'-26.00'),'Bias (dB)':(.8,'6.00'),'LF Bias (dB)':(.5,'0.00'),
                     'Automatico':(1,'On'),'Bypass':(0,'Off'),'Mix (%)':(1,'100.00'),
                     'High End Cut (dB)':(1,'0.00')})
            for name in KINDS:
                write_wav(dest/name,self.x*.3,48000)
                lines.extend(f'FINAL {key} normalized={value} text={text}' for key,(value,text) in params.items())
                lines.append(f'RENDER {name} latency=0 finite=1 frames={len(self.x)}')
            lines.append('PASS renders=4')
            log=self.root/(role+'-host.log');log.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            self.evidence['roles'][role]={'capturedBeforeRender':True,'pluginSha256':digest(binary),
                'pluginSha256After':digest(binary),'host':{'path':str(host),'sha256':digest(host)},
                'hostSha256After':digest(host),'logSha256':digest(log),
                'command':[str(host),str(bundle),str(self.root/'inputs'),str(dest),'-26','1','-65','0','offline','6'],
                'renders':{name:digest(dest/name) for name in KINDS}}
        self.save()

    def save(self):
        (self.root/'objective-protocol.json').write_text(json.dumps(self.protocol),encoding='utf-8')
        (self.root/'render-evidence.json').write_text(json.dumps(self.evidence),encoding='utf-8')

    def test_complete_fixture_scores_identity_without_perceptual_claim(self):
        result=evaluate(self.root)
        self.assertEqual(result['worstConditionAndChannelPercent'],100)
        self.assertTrue(result['technicalTargetReached'])
        self.assertFalse(result['perceptualEquivalenceEstablished'])
        self.assertEqual(len(result['conditions']),4)

    def test_missing_reference_render_rejected(self):
        (self.root/'cedar'/KINDS[-1]).unlink()
        with self.assertRaisesRegex(ValueError,'Missing cedar'): evaluate(self.root)

    def test_missing_provenance_rejected(self):
        (self.root/'render-evidence.json').unlink()
        with self.assertRaisesRegex(ValueError,'pre-render provenance'): evaluate(self.root)

    def test_changed_source_input_host_plugin_render_and_log_rejected(self):
        paths=[Path(self.evidence['source']['path']),self.root/'inputs'/KINDS[0],
               Path(self.evidence['roles']['open']['host']['path']),
               Path(self.protocol['plugins']['cedar']['path']),self.root/'open'/KINDS[0],
               self.root/'cedar-host.log']
        for path in paths:
            with self.subTest(path=path):
                saved=path.read_bytes();path.write_bytes(saved+b'changed')
                try:
                    with self.assertRaisesRegex(ValueError,'changed'): evaluate(self.root)
                finally: path.write_bytes(saved)

    def test_postrender_only_binary_evidence_rejected(self):
        self.evidence['roles']['open']['capturedBeforeRender']=False;self.save()
        with self.assertRaisesRegex(ValueError,'pre/post'): evaluate(self.root)

    def test_changed_render_command_rejected(self):
        self.evidence['roles']['open']['command'][4]='0';self.save()
        with self.assertRaisesRegex(ValueError,'Render command'): evaluate(self.root)

    def test_incomplete_or_mismatched_parameter_log_rejected(self):
        good=(self.root/'cedar-host.log').read_text()
        for bad in (good.replace('PASS renders=4','PASS renders=3'),
                    good.replace('text=-26.00','text=0.00',1),
                    good.replace('finite=1','finite=0',1),
                    good.replace('original.wav','added_step.wav')):
            with self.subTest(log=bad[:50]):
                with self.assertRaises(ValueError): _render_records(bad,'cedar')

    def test_nonfinite_render_rejected_even_with_matching_hash(self):
        path=self.root/'cedar'/KINDS[0];bad=self.x.copy();bad[20,0]=np.nan
        write_wav(path,bad,48000);self.evidence['roles']['cedar']['renders'][KINDS[0]]=digest(path);self.save()
        with self.assertRaisesRegex(ValueError,'Nonfinite'): evaluate(self.root)

    def test_logged_frame_count_and_actual_render_must_match(self):
        path=self.root/'cedar'/KINDS[0];write_wav(path,self.x[:-1],48000)
        self.evidence['roles']['cedar']['renders'][KINDS[0]]=digest(path);self.save()
        with self.assertRaisesRegex(ValueError,'frame count'): evaluate(self.root)

    def test_one_bad_condition_cannot_be_hidden_by_averaging(self):
        path=self.root/'open'/KINDS[-1];write_wav(path,self.x*.15,48000)
        self.evidence['roles']['open']['renders'][KINDS[-1]]=digest(path);self.save()
        result=evaluate(self.root)
        self.assertEqual(result['worstConditionAndChannelPercent'],0)
        self.assertFalse(result['technicalTargetReached'])
        self.assertEqual(sum(row['worstChannelAgreementPercent']==100 for row in result['conditions']),3)

    def test_original_hash_alone_does_not_prove_source_waveform_matches(self):
        path=self.root/'inputs/original.wav';write_wav(path,self.x*.5,48000)
        self.evidence['inputs']['original.wav']=digest(path);self.save()
        with self.assertRaisesRegex(ValueError,'Original input differs'): evaluate(self.root)

    def test_extra_or_unexpected_input_condition_rejected(self):
        write_wav(self.root/'inputs/extra.wav',self.x,48000)
        with self.assertRaisesRegex(ValueError,'exactly four'): evaluate(self.root)

if __name__=='__main__':unittest.main()
