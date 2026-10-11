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
    auto y=render(noise,fs,s);const int latency=1024;
    double reduction=20*std::log10(rms(noise,fs,3*fs)/rms(y,fs+latency,3*fs+latency));
    std::cout<<"Measured manual noise reduction dB: "<<reduction<<'\n';
    require(reduction>10 && reduction<13,"manual attenuation follows 12 dB floor");
    s.automatic=true;s.bias=0;y=render(noise,fs,s);
    reduction=20*std::log10(rms(noise,fs,3*fs)/rms(y,fs+latency,3*fs+latency));
    std::cout<<"Measured auto noise reduction dB: "<<reduction<<'\n';
    require(reduction>2,"automatic estimator reduces stationary hiss");
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
    require(processor.getLatencySamples()==1024,"48 kHz latency reported to host");
    const auto partitioned=[&noise](int size){OpenHissProcessor p;p.prepareToPlay(48000,size);p.state.getParameter("attenuation")->setValueNotifyingHost(0.7f);juce::MidiBuffer m;
        std::vector<float> result;for(int offset=0;offset<24000;){const int count=std::min(size,24000-offset);juce::AudioBuffer<float> a(2,count);a.clear();
            for(int i=0;i<count;++i)a.setSample(0,i,noise[offset+i]);p.processBlock(a,m);
            result.insert(result.end(),a.getReadPointer(0),a.getReadPointer(0)+count);offset+=count;}return result;};
    require(partitioned(64)==partitioned(257),"output independent of host block partition");
    OpenHissProcessor uiProcessor;
    std::unique_ptr<juce::AudioProcessorEditor> editor(uiProcessor.createEditor());
    const auto preview=editor->createComponentSnapshot(editor->getLocalBounds());
    juce::FileOutputStream previewFile(juce::File::getCurrentWorkingDirectory().getChildFile("editor-preview.png"));
    juce::PNGImageFormat png;
    require(preview.isValid() && preview.getWidth()>0 && png.writeImageToStream(preview,previewFile),"editor instantiates and renders to PNG");
    auto* dial=dynamic_cast<juce::Slider*>(editor->findChildWithID("attenuation"));
    require(dial && dial->getValue()==0,"attenuation dial displays zero by default");
    dial->setValue(-26,juce::sendNotificationSync);
    require(std::abs(uiProcessor.state.getRawParameterValue("attenuation")->load()+26)<0.001,"GUI dial updates the DSP attenuation parameter");
    juce::FileOutputStream activePreview(juce::File::getCurrentWorkingDirectory().getChildFile("editor-preview-26.png"));
    require(png.writeImageToStream(editor->createComponentSnapshot(editor->getLocalBounds()),activePreview),"active attenuation editor renders to PNG");
    uiProcessor.state.getParameter("auto")->setValueNotifyingHost(0);
    std::unique_ptr<juce::AudioProcessorEditor> manualEditor(uiProcessor.createEditor());
    auto* manualDial=dynamic_cast<juce::Slider*>(manualEditor->findChildWithID("bias"));
    require(manualDial && manualDial->getName()=="THRESHOLD" && manualDial->getValue()==-65,"manual mode maps the bias dial to threshold");
    std::cout<<"All beta tests passed. These are tests of Open Hiss, not CEDAR equivalence.\n";
    return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}
