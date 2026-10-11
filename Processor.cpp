// SPDX-License-Identifier: AGPL-3.0-or-later
#include "Processor.h"
#include "Editor.h"
static juce::AudioProcessorValueTreeState::ParameterLayout layout()
{
    juce::AudioProcessorValueTreeState::ParameterLayout p;
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"attenuation",1},"Atenuacao (dB)",-40.f,0.f,0.f));
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"bias",1},"Bias (dB)",-10.f,10.f,0.f));
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"threshold",1},"Noise floor manual (dBFS)",-90.f,-20.f,-65.f));
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"lowBias",1},"LF Bias (dB)",-10.f,10.f,0.f));
    p.add(std::make_unique<juce::AudioParameterBool>(juce::ParameterID{"auto",1},"Automatico",true));
    p.add(std::make_unique<juce::AudioParameterBool>(juce::ParameterID{"bypass",1},"Bypass",false));
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"mix",1},"Mix (%)",0.f,100.f,100.f));
    p.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"highEndCut",1},"High End Cut (dB)",-40.f,0.f,0.f));
    return p;
}
OpenHissProcessor::OpenHissProcessor()
 : AudioProcessor(BusesProperties().withInput("Input",juce::AudioChannelSet::stereo(),true).withOutput("Output",juce::AudioChannelSet::stereo(),true)),
   state(*this,nullptr,"OpenHissState",layout())
{
    const char* ids[]={"attenuation","bias","threshold","lowBias","auto","bypass","mix","highEndCut"};
    for(int i=0;i<8;++i) params[i]=state.getRawParameterValue(ids[i]);
}
void OpenHissProcessor::prepareToPlay(double fs,int)
{
    for(auto& c:channels)c.prepare(fs>0?fs:48000);
    setLatencySamples(channels[0].latency()); prepared=true;
}
bool OpenHissProcessor::isBusesLayoutSupported(const BusesLayout& l) const
{return (l.getMainOutputChannelSet()==juce::AudioChannelSet::mono() || l.getMainOutputChannelSet()==juce::AudioChannelSet::stereo()) && l.getMainInputChannelSet()==l.getMainOutputChannelSet();}
void OpenHissProcessor::processBlock(juce::AudioBuffer<float>& b,juce::MidiBuffer&)
{processAudio(b,false);}
void OpenHissProcessor::processBlockBypassed(juce::AudioBuffer<float>& b,juce::MidiBuffer&)
{processAudio(b,true);}
void OpenHissProcessor::processAudio(juce::AudioBuffer<float>& b,bool forceBypass)
{
    juce::ScopedNoDenormals safe;
    if(!prepared){b.clear();return;}
    HissSettings s;
    const auto safeParam=[](float v,float lo,float hi,float fallback){return std::isfinite(v)?std::clamp(v,lo,hi):fallback;};
    s.reduction=-safeParam(params[0]->load(),-40,0,0);s.bias=safeParam(params[1]->load(),-10,10,0);
    s.threshold=safeParam(params[2]->load(),-90,-20,-65);s.lowBias=safeParam(params[3]->load(),-10,10,0);
    s.automatic=params[4]->load()>0.5f;s.bypass=forceBypass || params[5]->load()>0.5f;
    s.mix=safeParam(params[6]->load(),0,100,100)/100.f;
    s.highEndCut=-safeParam(params[7]->load(),-40,0,0);
    for(int c=0;c<std::min(2,b.getNumChannels());++c)
    {auto* p=b.getWritePointer(c);for(int i=0;i<b.getNumSamples();++i)p[i]=channels[c].process(p[i],s);}
    for(int c=2;c<b.getNumChannels();++c)b.clear(c,0,b.getNumSamples());
}
juce::AudioProcessorEditor* OpenHissProcessor::createEditor()
{return new OpenDeHISSEditor(*this);}
void OpenHissProcessor::getStateInformation(juce::MemoryBlock& dst)
{auto xml=state.copyState().createXml();copyXmlToBinary(*xml,dst);}
void OpenHissProcessor::setStateInformation(const void* data,int size)
{auto xml=getXmlFromBinary(data,size);if(xml && xml->hasTagName(state.state.getType()))state.replaceState(juce::ValueTree::fromXml(*xml));}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter(){return new OpenHissProcessor();}
