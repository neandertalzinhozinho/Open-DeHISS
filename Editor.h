// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include "Processor.h"
class PurpleDialLook final : public juce::LookAndFeel_V4
{
public:
    void drawRotarySlider(juce::Graphics&,int,int,int,int,float,float,float,juce::Slider&) override;
    void drawToggleButton(juce::Graphics&,juce::ToggleButton&,bool,bool) override;
};
class OpenDeHISSEditor final : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit OpenDeHISSEditor(OpenHissProcessor&);
    ~OpenDeHISSEditor() override;
    void paint(juce::Graphics&) override;
    void resized() override;
private:
    void timerCallback() override;
    OpenHissProcessor& processor;
    PurpleDialLook look;
    bool lastAuto=true;
    juce::Slider attenuation,lfBias,bias,threshold,mix,highEndCut;
    juce::ToggleButton bypass{"BYPASS"},automatic{"AUTO"};
    std::array<std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment>,6> sliders;
    std::array<std::unique_ptr<juce::AudioProcessorValueTreeState::ButtonAttachment>,2> buttons;
};
