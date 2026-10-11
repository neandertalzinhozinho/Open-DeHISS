// SPDX-License-Identifier: AGPL-3.0-or-later
#include <juce_audio_processors_headless/juce_audio_processors_headless.h>
#include <random>
#include <iostream>
#include <cmath>
int main(int argc,char** argv)
{
    juce::ScopedJuceInitialiser_GUI runtime;
    if(argc!=2){std::cerr<<"Pass VST3 bundle path\n";return 2;}
    juce::AudioPluginFormatManager manager;
    auto format=std::make_unique<juce::VST3PluginFormatHeadless>();auto* scanner=format.get();
    manager.addFormat(std::move(format));
    juce::OwnedArray<juce::PluginDescription> descriptions;
    scanner->findAllTypesForFile(descriptions,argv[1]);
    if(descriptions.size()!=1){std::cerr<<"Factory scan did not return exactly one plugin\n";return 3;}
    juce::String error;auto instance=manager.createPluginInstance(*descriptions[0],48000,257,error);
    if(!instance){std::cerr<<error<<'\n';return 4;}
    std::cout<<"Loaded compiled VST3: "<<instance->getName()<<'\n';
    juce::AudioProcessorParameter* attenuation=nullptr;
    for(auto* p:instance->getParameters())if(p->getName(128).containsIgnoreCase("Atenuacao"))attenuation=p;
    if(!attenuation || std::abs(attenuation->getValue()-1)>0.00001){std::cerr<<"Default attenuation is not 0 dB\n";return 9;}
    std::cout<<"Default attenuation 0 dB confirmed; testing at -12 dB\n";
    attenuation->setValueNotifyingHost(0.7f);
    instance->setRateAndBufferSizeDetails(48000,257);instance->prepareToPlay(48000,257);
    if(instance->getLatencySamples()!=1024){std::cerr<<"Wrong latency\n";return 5;}
    juce::AudioBuffer<float> buffer(2,257);juce::MidiBuffer midi;
    std::mt19937 rng(20261011);std::normal_distribution<float> normal(0,0.0005623413f);
    double inPower=0,outPower=0;bool finite=true,rightSilent=true;
    for(int b=0;b<600;++b)
    {
        buffer.clear();for(int i=0;i<257;++i){const float x=normal(rng);buffer.setSample(0,i,x);if(b>200)inPower+=double(x)*x;}
        instance->processBlock(buffer,midi);
        for(int i=0;i<257;++i){const float x=buffer.getSample(0,i);finite &= std::isfinite(x);rightSilent &= buffer.getSample(1,i)==0;if(b>200)outPower+=double(x)*x;}
    }
    const double reduction=10*std::log10(inPower/outPower);
    std::cout<<"Actual VST3 auto reduction dB: "<<reduction<<"\nFinite: "<<finite<<"\nNo stereo leakage: "<<rightSilent<<'\n';
    if(!finite || !rightSilent || reduction<2)return 6;
    juce::AudioProcessorParameter* bypass=nullptr;
    for(auto* p:instance->getParameters())if(p->getName(128).containsIgnoreCase("Bypass"))bypass=p;
    if(!bypass)return 7;bypass->setValueNotifyingHost(1);
    instance->releaseResources();instance->prepareToPlay(48000,257);
    double worst=0;
    for(int b=0;b<20;++b){buffer.clear();for(int i=0;i<257;++i)buffer.setSample(0,i,float(0.1*std::sin((b*257+i)*0.1)));
        instance->processBlock(buffer,midi);for(int i=0;i<257;++i){const int t=b*257+i;const float expected=t<1024?0:float(0.1*std::sin((t-1024)*0.1));worst=std::max(worst,std::abs(double(buffer.getSample(0,i)-expected)));}}
    std::cout<<"Actual VST3 bypass alignment error: "<<worst<<'\n';
    instance->releaseResources();
    if(worst>0.000001)return 8;
    std::cout<<"PASS actual compiled VST3 load, processing, latency and bypass\n";return 0;
}
