// SPDX-License-Identifier: AGPL-3.0-or-later
#include "Processor.h"
#include <random>
#include <iostream>
#include <stdexcept>
static void require(bool condition,const char* name){if(!condition)throw std::runtime_error(name);std::cout<<"PASS "<<name<<'\n';}
static double rms(const std::vector<float>& x,int start,int end){double p=0;for(int i=start;i<end;++i)p+=double(x[i])*x[i];return std::sqrt(p/(end-start));}
static std::vector<float> render(const std::vector<float>& x,double fs,HissSettings s)
{HissChannel c;c.prepare(fs);std::vector<float> out;out.reserve(x.size()+c.latency());for(float a:x)out.push_back(c.process(a,s));for(int i=0;i<c.latency();++i)out.push_back(c.process(0,s));return out;}
int main()
{
    try{
    juce::ScopedJuceInitialiser_GUI runtime;
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
    require(processor.getLatencySamples()==4096,"48 kHz latency reported to host");
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
    require(lowRateOutput[6000]==lowRateInput[1904],"high cut is exact dry when Nyquist is at or below 15 kHz");
    require(processor.state.getRawParameterValue("highEndCut")->load()==0,"High End Cut defaults off");
    processor.state.getParameter("highEndCut")->setValueNotifyingHost(0.4f);
    processor.getStateInformation(saved);restored.setStateInformation(saved.getData(),int(saved.getSize()));
    require(std::abs(restored.state.getRawParameterValue("highEndCut")->load()+24)<0.001,"High End Cut survives state restore");
    OpenHissProcessor uiProcessor;
    std::unique_ptr<juce::AudioProcessorEditor> editor(uiProcessor.createEditor());
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
