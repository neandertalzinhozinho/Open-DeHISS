// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <juce_audio_processors/juce_audio_processors.h>
#include "Denoiser.h"
#if OPEN_DEHISS_EXPERIMENTAL_DERIVED
#include "DerivedChannel.h"
#include "MultiResolutionChannel.h"
#endif
class OpenHissProcessor final : public juce::AudioProcessor
{
public:
    OpenHissProcessor();
    void prepareToPlay(double,int) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported(const BusesLayout&) const override;
    void processBlock(juce::AudioBuffer<float>&,juce::MidiBuffer&) override;
    void processBlockBypassed(juce::AudioBuffer<float>&,juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override {return true;}
    const juce::String getName() const override {return "Open DeHISS";}
    bool acceptsMidi() const override {return false;}
    bool producesMidi() const override {return false;}
    bool isMidiEffect() const override {return false;}
    double getTailLengthSeconds() const override {return getSampleRate()>0?double(getLatencySamples())/getSampleRate():0;}
    int getNumPrograms() override {return 1;}
    int getCurrentProgram() override {return 0;}
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override {return "Default";}
    void changeProgramName(int,const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*,int) override;
    juce::AudioProcessorValueTreeState state;
private:
    void processAudio(juce::AudioBuffer<float>&,bool forceBypass);
#if OPEN_DEHISS_EXPERIMENTAL_DERIVED
    std::array<MultiResolutionChannel,2> channels;
#else
    std::array<HissChannel,2> channels;
#endif
    std::array<std::atomic<float>*,8> params{};
    bool prepared=false;
};
