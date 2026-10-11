// SPDX-License-Identifier: AGPL-3.0-or-later
#include "Processor.h"
#include "RecoveredMath.h"
#include "RecoveredSynthesis.h"
#include "DerivedChannel.h"
#include <juce_audio_formats/juce_audio_formats.h>
#include <random>
#include <iostream>
#include <stdexcept>
static void require(bool condition,const char* name){if(!condition)throw std::runtime_error(name);std::cout<<"PASS "<<name<<'\n';}
static double rms(const std::vector<float>& x,int start,int end){double p=0;for(int i=start;i<end;++i)p+=double(x[i])*x[i];return std::sqrt(p/(end-start));}
static std::vector<float> render(const std::vector<float>& x,double fs,HissSettings s)
{HissChannel c;c.prepare(fs);std::vector<float> out;out.reserve(x.size()+c.latency());for(float a:x)out.push_back(c.process(a,s));for(int i=0;i<c.latency();++i)out.push_back(c.process(0,s));return out;}
int main(int argc,char** argv)
{
    try{
    juce::ScopedJuceInitialiser_GUI runtime;
    if(argc>1 && juce::String(argv[1])=="--derived-render"){
        if(argc!=6)throw std::runtime_error("--derived-render input.wav output.wav attenuationPositive bias");
        juce::AudioFormatManager formats;formats.registerBasicFormats();
        std::unique_ptr<juce::AudioFormatReader> reader(formats.createReaderFor(juce::File(argv[2])));
        if(!reader || reader->numChannels<1 || reader->numChannels>2 || reader->lengthInSamples>10000000)throw std::runtime_error("Invalid input audio");
        const juce::File destination(argv[3]);if(destination.exists())throw std::runtime_error("Preserve existing output");
        DerivedChannel probe;probe.prepare(reader->sampleRate);const int delay=probe.latency(),length=int(reader->lengthInSamples);
        juce::AudioBuffer<float> input(int(reader->numChannels),length),output(int(reader->numChannels),length+delay);
        if(!reader->read(&input,0,length,0,true,true))throw std::runtime_error("Audio read failed");
        HissSettings settings;settings.reduction=float(std::atof(argv[4]));settings.bias=float(std::atof(argv[5]));
        for(int ch=0;ch<input.getNumChannels();++ch){DerivedChannel channel;channel.prepare(reader->sampleRate);
            for(int t=0;t<length+delay;++t)output.setSample(ch,t,channel.process(t<length?input.getSample(ch,t):0,settings));}
        juce::WavAudioFormat wav;auto stream=destination.createOutputStream();
        if(!stream)throw std::runtime_error("Output stream failed");
        std::unique_ptr<juce::AudioFormatWriter> writer(wav.createWriterFor(stream.get(),reader->sampleRate,unsigned(output.getNumChannels()),32,{},0));
        if(!writer)throw std::runtime_error("WAV writer failed");stream.release();
        if(!writer->writeFromAudioSampleBuffer(output,0,output.getNumSamples()))throw std::runtime_error("WAV write failed");
        std::cout<<"Derived render latency="<<delay<<" samples, Fs="<<reader->sampleRate<<" frames="<<output.getNumSamples()<<'\n';return 0;
    }
    for(double rate:{8000.,44100.,48000.,96000.}){
        DerivedChannel channel;channel.prepare(rate);const int delay=channel.latency();
        require(delay/rate<=.096,"derived streaming channel stays within 96 ms");
        HissSettings settings;settings.reduction=0;double error=0;
        for(int t=0;t<delay+5000;++t){const float x=float(.1*std::sin(t*.13));const float y=channel.process(x,settings);
            const float expected=t<delay?0:float(.1*std::sin((t-delay)*.13));error=std::max(error,std::abs(double(y-expected)));}
        require(error==0,"derived streaming dry delay is exact");
        channel.prepare(rate);settings.reduction=.000001f;settings.automatic=false;settings.threshold=-150;error=0;
        for(int t=0;t<delay+5000;++t){const float x=float(.1*std::sin(t*.13));const float y=channel.process(x,settings);
            const float expected=t<delay?0:float(.1*std::sin((t-delay)*.13));error=std::max(error,std::abs(double(y-expected)));}
        require(error<2e-6,"derived streaming wet reconstruction aligns with dry");
    }
    {
        const double input[]={-.8,.1,.9,-.2,.5};double output[5];
        const double expected[]={.040171935836507855,.04105496772205626,.041880431414837944,.04186781951698711,.04209142588418635};
        openhiss_derived::spectral(input,output,5,1024,48000,1500);
        double error=0;for(int k=0;k<5;++k)error=std::max(error,std::abs(output[k]-expected[k]));
        require(error<1e-12,"derived C++ spectral sweep matches independent Python fixture");
        require(std::abs(openhiss_derived::probability(.1,.4)-.42857142937447573)<1e-12 &&
                std::abs(openhiss_derived::probability(.6,.8)-.11111741637065309)<1e-12,
                "derived C++ stable probability matches independent Python fixture");
        require(std::abs(openhiss_derived::gain(.5,9000,-26)-.6437945212610228)<1e-12 &&
                std::abs(openhiss_derived::gain(1,18000,-26)-.05220700350284086)<1e-12,
                "derived C++ frequency gain matches independent Python fixture");
        double values[]={1,100,3,2};require(openhiss_derived::upperMedian(values,4)==3,"derived global upper median");
        openhiss_derived::BoundedTemporal temporal;temporal.prepare(3,1024,48000,.125);
        const double first[]={-.8,.2,.7,.1,.9,-.5,.8,-.4,.3};double smoothed[3];
        temporal.process(first,3,smoothed);
        const double initial[]={.011844581835505446,.2510849106576259,.16292949249313138};
        error=0;for(int k=0;k<3;++k)error=std::max(error,std::abs(smoothed[k]-initial[k]));
        require(error<1e-12,"C++ bounded temporal startup matches Python fixture");
        const double next[]={.8,-.4,.3,.1,.9,-.5,-.8,.2,.7};temporal.process(next,3,smoothed);
        const double second[]={-.14834950328722935,.22606601986851083,.28294368210382675};
        error=0;for(int k=0;k<3;++k)error=std::max(error,std::abs(smoothed[k]-second[k]));
        require(error<1e-12,"C++ bounded temporal history matches Python fixture");
        require((1024+temporal.lookahead()*512)/48000.<=.096,"C++ temporal lookahead respects latency budget");
        openhiss_derived::GlobalNoiseHistory estimator;estimator.prepare(2);
        for(int frame=0;frame<25;++frame){double energy[]={double(frame),double(frame+100)};estimator.push(energy);}
        require(estimator.median()==104 && estimator.median(3)==122,"C++ global median retains chronological history across ring wrap");
        juce::dsp::FFT frameFft(10);std::vector<float> waveform(1024),packed(2048,0),block(512);
        std::vector<std::complex<float>> spectrum(513);std::vector<double> curve(513,1.);
        for(int j=0;j<1024;++j)waveform[j]=packed[j]=float(.1*std::sin(j*.13)+.07*std::cos(j*.037));
        frameFft.performRealOnlyForwardTransform(packed.data());
        for(int k=0;k<513;++k)spectrum[k]={packed[2*k],packed[2*k+1]};
        DerivedSynthesis synthesis;synthesis.prepare(10);synthesis.render(spectrum.data(),curve.data(),block.data());
        error=0;for(int j=0;j<512;++j)error=std::max(error,std::abs(double(block[j]-waveform[256+j])));
        require(error<2e-6,"C++ derived synthesis is transparent at unit gain");
        synthesis.prepare(10);for(int k=0;k<513;++k)curve[k]=.1+.8*k/512.;
        synthesis.render(spectrum.data(),curve.data(),block.data());
        const int points[]={0,1,63,127,255,383,510,511};
        const double audioFixture[]={.02580819542222028,.021389849678714885,-.007545803509620561,-.03777812630133492,.013835791580460742,.036462149548190666,-.01899510185393798,-.017603360610348284};
        error=0;for(int j=0;j<8;++j)error=std::max(error,std::abs(block[points[j]]-audioFixture[j]));
        require(error<2e-6,"C++ circular impulse reconstruction matches Python audio fixture");
    }
    for(double rate:{8000.,16000.,22050.,24000.,30000.,32000.,44100.,48000.,88200.,96000.,192000.,384000.}){
        HissChannel latencyProbe;latencyProbe.prepare(rate);
        require(double(latencyProbe.latency())/rate<=.096,"algorithmic latency never exceeds 96 ms at supported sample rates");
    }
    for(double fs:{44100.0,48000.0,96000.0})
    {
        std::vector<float> x(static_cast<size_t>(fs),0.f);for(int i=0;i<int(x.size());++i)x[i]=float(0.2*std::sin(i*0.13));
        HissChannel c;c.prepare(fs);const int latency=c.latency();
        HissSettings s;s.reduction=0;auto y=render(x,fs,s);double error=0;
        for(int i=0;i<int(x.size());++i)error=std::max(error,std::abs(double(y[i+latency]-x[i])));
        require(error==0,"0 dB is exact delayed dry at each sample rate");
        s.reduction=0.00001f;s.automatic=false;s.threshold=-90;y=render(x,fs,s);error=0;
        for(int i=0;i<int(x.size());++i)error=std::max(error,std::abs(double(y[i+latency]-x[i])));
        require(error<0.00001,"overlap-add latency and near-unity reconstruction");
        s.bypass=true;y=render(x,fs,s);require(y[latency+100]==x[100],"bypass retains host latency");
        s.bypass=false;s.mix=0;y=render(x,fs,s);require(y[latency+100]==x[100],"mix zero is aligned dry");
    }
    const int fs=48000;std::mt19937 rng(20261011);std::normal_distribution<float> normal(0,1);
    std::vector<float> noise(3*fs);for(auto& a:noise)a=normal(rng)*0.0005623413f;
    HissSettings s;s.automatic=false;s.threshold=-50;s.reduction=12;
    auto y=render(noise,fs,s);const int latency=4096;
    double reduction=20*std::log10(rms(noise,fs,3*fs)/rms(y,fs+latency,3*fs+latency));
    std::cout<<"Measured manual noise reduction dB: "<<reduction<<'\n';
    require(reduction>10 && reduction<13,"manual attenuation follows 12 dB floor");
    s.automatic=true;s.bias=0;y=render(noise,fs,s);
    reduction=20*std::log10(rms(noise,fs,3*fs)/rms(y,fs+latency,3*fs+latency));
    std::cout<<"Measured auto noise reduction dB: "<<reduction<<'\n';
    require(reduction>2,"automatic estimator reduces stationary hiss");
    // Regression from the reference benchmark: sustained useful tones must not
    // become the automatically learned noise floor.
    for(double rate:{44100.0,48000.0,96000.0}) {
        HissSettings tonal;tonal.reduction=26;
        HissChannel delayProbe;delayProbe.prepare(rate);const int delay=delayProbe.latency();
        const auto amplitude=[rate](const std::vector<float>& v,int offset,double freq){
            double re=0,im=0;const int count=int(rate*2);
            for(int i=0;i<count;++i){const double phase=2*juce::MathConstants<double>::pi*freq*(i+int(rate))/rate;
                re+=v[offset+int(rate)+i]*std::cos(phase);im+=v[offset+int(rate)+i]*std::sin(phase);}
            return 2*std::hypot(re,im)/count;};
        for(double freq:{1400.0,11000.0}) {
            std::vector<float> toneNoise(static_cast<size_t>(rate*3));
            for(int i=0;i<int(toneNoise.size());++i)toneNoise[i]=float(.05*std::sin(2*juce::MathConstants<double>::pi*freq*i/rate))+normal(rng)*.0005623413f;
            const auto filtered=render(toneNoise,rate,tonal);
            const double loss=20*std::log10(amplitude(toneNoise,0,freq)/amplitude(filtered,delay,freq));
            std::cout<<"Auto sustained tone "<<rate<<" Hz, "<<freq<<" Hz loss: "<<loss<<" dB\n";
            require(std::abs(loss)<.5,"automatic mode preserves sustained useful tones with hiss");
        }
        std::vector<float> vowel(static_cast<size_t>(rate*3));
        for(int i=0;i<int(vowel.size());++i){double voiced=0;
            for(int h=1;h<=12;++h)voiced+=.03/h*std::sin(2*juce::MathConstants<double>::pi*120*h*i/rate);
            vowel[i]=float(voiced)+normal(rng)*.0005623413f;}
        const auto filtered=render(vowel,rate,tonal);
        for(double harmonic:{120.0,600.0,1440.0}) {
            const double loss=20*std::log10(amplitude(vowel,0,harmonic)/amplitude(filtered,delay,harmonic));
            std::cout<<"Synthetic vowel "<<rate<<" Hz, harmonic "<<harmonic<<" Hz loss: "<<loss<<" dB\n";
            require(std::abs(loss)<1,"automatic mode preserves sustained synthetic vowel harmonics");
        }
    }
    s.reduction=26;s.automatic=true;y=render(noise,fs,s);
    reduction=20*std::log10(rms(noise,fs,3*fs)/rms(y,fs+latency,3*fs+latency));
    std::cout<<"Auto stationary noise at -26 dB: "<<reduction<<" dB\n";
    require(reduction>20 && reduction<27,"automatic suppression approaches selected amount on stationary hiss");
    for(double rate:{44100.0,48000.0,96000.0}) {
        HissChannel probe;probe.prepare(rate);const int delay=probe.latency();
        HissSettings tracking;tracking.reduction=26;
        std::vector<float> step(static_cast<size_t>(rate*5));
        for(int i=0;i<int(step.size());++i)step[i]=normal(rng)*(i<int(2*rate)?.0005623413f:.005623413f);
        const auto filtered=render(step,rate,tracking);
        const double cut=20*std::log10(rms(step,int(3*rate),int(4*rate))/rms(filtered,int(3*rate)+delay,int(4*rate)+delay));
        std::cout<<"Broadband +20 dB step "<<rate<<" Hz, reduction after 1 second: "<<cut<<" dB\n";
        require(cut>18,"persistent broadband noise rise is suppressed within one second");
        // A short broadband consonant must not cause accelerated noise learning.
        std::vector<float> burst(static_cast<size_t>(rate*3));
        for(int i=0;i<int(burst.size());++i)burst[i]=normal(rng)*(i>=int(rate)&&i<int(1.12*rate)?.02f:.0005623413f);
        const auto voiced=render(burst,rate,tracking);
        const double loss=20*std::log10(rms(burst,int(rate),int(1.12*rate))/rms(voiced,int(rate)+delay,int(1.12*rate)+delay));
        std::cout<<"Short broadband consonant "<<rate<<" Hz loss: "<<loss<<" dB\n";
        require(loss<3,"brief broadband speech onset is not learned as persistent noise");
    }
    // Low-level tonal residue must not be exempt merely because it is coherent.
    // Dense baritone harmonics surround these probes in the user's target band.
    // Probes sit halfway between harmonics. A tone only 10 Hz from a strong
    // harmonic is unresolved at this FFT size and is not claimed removable.
    for(double residueFrequency:{1020.0,1860.0,4020.0}) {
        std::vector<float> mixture(3*fs);
        for(int i=0;i<int(mixture.size());++i){double voice=0;
            for(int h=1;h<=50;++h)voice+=.015/h*std::sin(2*juce::MathConstants<double>::pi*120*h*i/fs);
            mixture[i]=float(voice+.00015*std::sin(2*juce::MathConstants<double>::pi*residueFrequency*i/fs))+normal(rng)*.0005623413f;}
        HissSettings aggressive;aggressive.reduction=26;aggressive.bias=10;
        const auto filtered=render(mixture,fs,aggressive);
        const auto probe=[&](const std::vector<float>& v,int offset){double re=0,im=0;
            for(int i=fs;i<3*fs;++i){const double phase=2*juce::MathConstants<double>::pi*residueFrequency*i/fs;
                re+=v[i+offset]*std::cos(phase);im+=v[i+offset]*std::sin(phase);}
            return std::hypot(re,im);};
        const double residueCut=20*std::log10(probe(mixture,0)/probe(filtered,latency));
        std::cout<<"Baritone weak tonal residue "<<residueFrequency<<" Hz cut: "<<residueCut<<" dB\n";
        require(residueCut>6,"weak coherent residue under baritone is suppressed, not automatically preserved");
    }
    std::vector<float> silence(2*fs,0);y=render(silence,fs,s);
    require(std::all_of(y.begin(),y.end(),[](float v){return v==0 && std::isfinite(v);}),"silence remains finite zero");
    silence[17]=std::numeric_limits<float>::quiet_NaN();silence[42]=std::numeric_limits<float>::infinity();y=render(silence,fs,s);
    require(std::all_of(y.begin(),y.end(),[](float v){return std::isfinite(v);}),"nonfinite inputs do not poison processing");
    OpenHissProcessor processor;processor.prepareToPlay(fs,257);
    require(processor.state.getRawParameterValue("attenuation")->load()==0,"default attenuation is 0 dB");
    processor.state.getParameter("attenuation")->setValueNotifyingHost(0.7f);
    require(std::abs(processor.state.getRawParameterValue("attenuation")->load()+12)<0.001,"negative attenuation selects reduction amount");
    juce::MidiBuffer midi;juce::AudioBuffer<float> block(2,257);bool rightSilent=true;
    for(int b=0;b<100;++b){block.clear();for(int i=0;i<257;++i)block.setSample(0,i,noise[(b*257+i)%noise.size()]);processor.processBlock(block,midi);
        for(int i=0;i<257;++i)rightSilent &= block.getSample(1,i)==0;}
    require(rightSilent,"stereo channels do not leak into each other");
    processor.state.getParameter("bias")->setValueNotifyingHost(0.75f);
    juce::MemoryBlock saved;processor.getStateInformation(saved);OpenHissProcessor restored;
    restored.setStateInformation(saved.getData(),int(saved.getSize()));
    require(std::abs(restored.state.getRawParameterValue("bias")->load()-5)<0.001,"parameter state survives save and restore");
#if OPEN_DEHISS_EXPERIMENTAL_DERIVED
    require(processor.getLatencySamples()==4608,"derived 48 kHz latency reported to host");
#else
    require(processor.getLatencySamples()==4096,"48 kHz latency reported to host");
#endif
    const auto partitioned=[&noise](int size){OpenHissProcessor p;p.prepareToPlay(48000,size);p.state.getParameter("attenuation")->setValueNotifyingHost(0.7f);juce::MidiBuffer m;
        std::vector<float> result;for(int offset=0;offset<24000;){const int count=std::min(size,24000-offset);juce::AudioBuffer<float> a(2,count);a.clear();
            for(int i=0;i<count;++i)a.setSample(0,i,noise[offset+i]);p.processBlock(a,m);
            result.insert(result.end(),a.getReadPointer(0),a.getReadPointer(0)+count);offset+=count;}return result;};
    require(partitioned(64)==partitioned(257),"output independent of host block partition");
    for(double rate:{44100.0,48000.0,96000.0})
    {
        HissChannel probe;probe.prepare(rate);const int delay=probe.latency();
        HissSettings high;high.reduction=0;high.highEndCut=24;high.automatic=false;high.threshold=-20;
        for(double freq:{1000.0,14000.0,18000.0,21000.0})
        {
            std::vector<float> tone(static_cast<size_t>(rate*2),0.f);
            for(int i=0;i<int(tone.size());++i)tone[i]=float(0.0005*std::sin(2*juce::MathConstants<double>::pi*freq*i/rate));
            auto filtered=render(tone,rate,high);
            const double cut=20*std::log10(rms(tone,int(rate),int(2*rate))/rms(filtered,int(rate)+delay,int(2*rate)+delay));
            std::cout<<"High End Cut "<<rate<<" Hz, tone "<<freq<<" Hz: "<<cut<<" dB\n";
            require(freq<15000?std::abs(cut)<0.1:std::abs(cut-24)<0.5,"high-band suppression preserves low band and reaches selected floor");
        }
    }
    HissSettings aboveNyquist;aboveNyquist.reduction=0;aboveNyquist.highEndCut=40;
    std::vector<float> lowRateInput(30000,0.01f);auto lowRateOutput=render(lowRateInput,30000,aboveNyquist);
    HissChannel lowRateProbe;lowRateProbe.prepare(30000);
    require(lowRateOutput[6000]==lowRateInput[6000-lowRateProbe.latency()],"high cut is exact dry when Nyquist is at or below 15 kHz");
    require(processor.state.getRawParameterValue("highEndCut")->load()==0,"High End Cut defaults off");
    processor.state.getParameter("highEndCut")->setValueNotifyingHost(0.4f);
    processor.getStateInformation(saved);restored.setStateInformation(saved.getData(),int(saved.getSize()));
    require(std::abs(restored.state.getRawParameterValue("highEndCut")->load()+24)<0.001,"High End Cut survives state restore");
    OpenHissProcessor uiProcessor;
    std::unique_ptr<juce::AudioProcessorEditor> editor(uiProcessor.createEditor());
    auto* versionInfo=dynamic_cast<juce::Label*>(editor->findChildWithID("versionInfo"));
    require(versionInfo && versionInfo->isVisible() && versionInfo->getText().contains(OPEN_DEHISS_VERSION)
        && versionInfo->getText().contains(OPEN_DEHISS_UPDATE_DATE),"editor visibly identifies compiled version and release date");
    const auto preview=editor->createComponentSnapshot(editor->getLocalBounds());
    juce::FileOutputStream previewFile(juce::File::getCurrentWorkingDirectory().getChildFile("editor-preview.png"));
    previewFile.setPosition(0);previewFile.truncate();
    juce::PNGImageFormat png;
    require(preview.isValid() && preview.getWidth()==550 && preview.getHeight()==426 && png.writeImageToStream(preview,previewFile),"editor instantiates and renders to PNG");
    auto* dial=dynamic_cast<juce::Slider*>(editor->findChildWithID("attenuation"));
    require(dial && dial->getValue()==0,"attenuation dial displays zero by default");
    auto* highDial=dynamic_cast<juce::Slider*>(editor->findChildWithID("highEndCut"));
    require(highDial && highDial->isVisible() && highDial->getValue()==0,"High End Cut control is visible and defaults zero");
    highDial->setValue(-24,juce::sendNotificationSync);
    require(std::abs(uiProcessor.state.getRawParameterValue("highEndCut")->load()+24)<0.001,"High End Cut GUI controls its DSP parameter");
    dial->setValue(-26,juce::sendNotificationSync);
    require(std::abs(uiProcessor.state.getRawParameterValue("attenuation")->load()+26)<0.001,"GUI dial updates the DSP attenuation parameter");
    juce::FileOutputStream activePreview(juce::File::getCurrentWorkingDirectory().getChildFile("editor-preview-26.png"));
    activePreview.setPosition(0);activePreview.truncate();
    require(png.writeImageToStream(editor->createComponentSnapshot(editor->getLocalBounds()),activePreview),"active attenuation editor renders to PNG");
    uiProcessor.state.getParameter("auto")->setValueNotifyingHost(0);
    std::unique_ptr<juce::AudioProcessorEditor> manualEditor(uiProcessor.createEditor());
    auto* manualDial=dynamic_cast<juce::Slider*>(manualEditor->findChildWithID("bias"));
    require(manualDial && manualDial->getName()=="THRESHOLD" && manualDial->getValue()==-65,"manual mode maps the bias dial to threshold");
    std::cout<<"All beta tests passed. These are tests of Open Hiss, not CEDAR equivalence.\n";
    return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}
