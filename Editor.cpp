// SPDX-License-Identifier: AGPL-3.0-or-later
#include "Editor.h"
static const auto purple=juce::Colour(0xffc6a0ff);
void PurpleDialLook::drawRotarySlider(juce::Graphics& g,int x,int y,int w,int h,float position,float start,float end,juce::Slider& s)
{
    auto bounds=juce::Rectangle<float>(float(x),float(y),float(w),float(h)).reduced(7);
    const float r=std::min(bounds.getWidth(),bounds.getHeight())/2,cx=bounds.getCentreX(),cy=bounds.getCentreY();
    auto circle=juce::Rectangle<float>(cx-r,cy-r,2*r,2*r);
    g.setColour(juce::Colours::black.withAlpha(0.4f));g.fillEllipse(circle.translated(0,4).expanded(3));
    g.setGradientFill(juce::ColourGradient(juce::Colour(0xff68616e),cx,cy-r,juce::Colour(0xff18151d),cx,cy+r,false));g.fillEllipse(circle);
    g.setColour(juce::Colour(0xff0c0911));g.fillEllipse(circle.reduced(5));
    g.setColour(juce::Colour(0xff44384f));g.drawEllipse(circle.reduced(10),2);
    auto face=circle.reduced(17);
    g.setGradientFill(juce::ColourGradient(juce::Colour(0xff4d4557),cx,face.getY(),juce::Colour(0xff27212f),cx,face.getBottom(),false));g.fillEllipse(face);
    // Negative attenuation grows counterclockwise away from the zero position.
    const float angle=start+position*(end-start),trackR=r-10;
    juce::Path track;track.addCentredArc(cx,cy,trackR,trackR,0,start,end,true);
    g.setColour(juce::Colour(0xff221b2a));g.strokePath(track,juce::PathStrokeType(4));
    juce::Path active;
    const bool isMain=w>180;const float neutral=(start+end)*0.5f;
    active.addCentredArc(cx,cy,trackR,trackR,0,isMain?angle:std::min(neutral,angle),isMain?end:std::max(neutral,angle),true);
    g.setColour(purple.withAlpha(0.9f));g.strokePath(active,juce::PathStrokeType(4,juce::PathStrokeType::curved,juce::PathStrokeType::rounded));
    const float px=cx+trackR*std::sin(angle),py=cy-trackR*std::cos(angle);
    g.setColour(purple.withAlpha(0.18f));g.fillEllipse(px-7,py-7,14,14);
    g.setColour(juce::Colour(0xfff5eaff));g.fillEllipse(px-3,py-3,6,6);
    const bool large=w>180;
    g.setColour(juce::Colour(0xffddd1e9));g.setFont(large?42.f:23.f);
    const double v=s.getValue();const juce::String text=std::abs(v)<0.05?"0":juce::String(v,0);
    g.drawText(text,juce::Rectangle<float>(cx-r,cy-(large?29.f:23.f),2*r,large?50.f:32.f),juce::Justification::centred);
    g.setColour(juce::Colour(0xffbaacc6));g.setFont(large?13.f:10.f);
    g.drawText(s.getName(),juce::Rectangle<float>(cx-r,cy+16,2*r,22),juce::Justification::centred);
}
void PurpleDialLook::drawToggleButton(juce::Graphics& g,juce::ToggleButton& b,bool hover,bool)
{
    auto box=juce::Rectangle<float>(2,5,20,20);
    g.setColour(b.getToggleState()?purple:juce::Colour(0xff665d70));g.fillRoundedRectangle(box,3);
    g.setColour(juce::Colours::white.withAlpha(hover?0.5f:0.2f));g.drawRoundedRectangle(box,3,1);
    g.setColour(juce::Colour(0xffd0c1dd));g.setFont(11.f);g.drawText(b.getButtonText(),27,0,b.getWidth()-27,b.getHeight(),juce::Justification::centredLeft);
}
OpenDeHISSEditor::OpenDeHISSEditor(OpenHissProcessor& p):AudioProcessorEditor(p),processor(p)
{
    setLookAndFeel(&look);setSize(550,426);
    const char* ids[]={"attenuation","lowBias","bias","threshold","mix","highEndCut"};
    juce::Slider* controls[]={&attenuation,&lfBias,&bias,&threshold,&mix,&highEndCut};
    const char* names[]={"ATTENUATION","LF BIAS","BIAS","THRESHOLD","MIX %","HIGH END CUT"};
    for(int i=0;i<6;++i){auto& s=*controls[i];s.setName(names[i]);s.setComponentID(ids[i]);
        s.setSliderStyle(i<3?juce::Slider::RotaryVerticalDrag:juce::Slider::LinearHorizontal);
        s.setTextBoxStyle(i<3?juce::Slider::NoTextBox:juce::Slider::TextBoxRight,false,46,20);
        s.setColour(juce::Slider::thumbColourId,purple);s.setColour(juce::Slider::textBoxTextColourId,juce::Colour(0xffd9c5ee));
        s.setColour(juce::Slider::textBoxOutlineColourId,juce::Colours::transparentBlack);addAndMakeVisible(s);
        sliders[i]=std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(p.state,ids[i],s);}
    attenuation.setDoubleClickReturnValue(true,0);lfBias.setDoubleClickReturnValue(true,0);bias.setDoubleClickReturnValue(true,0);
    attenuation.setRotaryParameters(juce::MathConstants<float>::halfPi,juce::MathConstants<float>::pi*2.5f,true);
    lfBias.setRotaryParameters(juce::MathConstants<float>::pi*1.5f,juce::MathConstants<float>::pi*2.5f,true);
    bias.setRotaryParameters(juce::MathConstants<float>::pi*1.5f,juce::MathConstants<float>::pi*2.5f,true);
    threshold.setVisible(false);mix.setVisible(false);
    highEndCut.setDoubleClickReturnValue(true,0);
    highEndCut.setTooltip("Dehiss acima de 15 kHz. 0 dB desliga; valores negativos aumentam a reducao.");
    addAndMakeVisible(bypass);addAndMakeVisible(automatic);
    buttons[0]=std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(p.state,"bypass",bypass);
    buttons[1]=std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(p.state,"auto",automatic);
    timerCallback();startTimerHz(10);
}
OpenDeHISSEditor::~OpenDeHISSEditor(){stopTimer();setLookAndFeel(nullptr);}
void OpenDeHISSEditor::timerCallback()
{
    const bool isAuto=processor.state.getRawParameterValue("auto")->load()>0.5f;
    if(isAuto!=lastAuto){sliders[2].reset();bias.setName(isAuto?"BIAS":"THRESHOLD");
        sliders[2]=std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(processor.state,isAuto?"bias":"threshold",bias);
        bias.setDoubleClickReturnValue(true,isAuto?0:-65);lastAuto=isAuto;}
    repaint();
}
void OpenDeHISSEditor::resized()
{
    lfBias.setBounds(58,72,128,128);bias.setBounds(58,200,128,128);attenuation.setBounds(266,63,255,255);
    bypass.setBounds(44,331,95,30);automatic.setBounds(145,331,85,30);
    threshold.setBounds(40,366,185,22);mix.setBounds(375,366,146,22);
    highEndCut.setBounds(245,386,287,27);
}
void OpenDeHISSEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff242029));
    g.setGradientFill(juce::ColourGradient(juce::Colour(0xff5a4a67),0,0,juce::Colour(0xff29232f),235,400,false));g.fillRect(0,0,235,400);
    g.setColour(juce::Colour(0xff100e14));g.fillRoundedRectangle(235,6,309,363,29);
    g.setGradientFill(juce::ColourGradient(juce::Colour(0xff34273e),260,0,juce::Colour(0xff19141f),500,365,false));g.fillRoundedRectangle(239,8,303,359,27);
    for(int line=0;line<30;++line){juce::Path wave;for(int x=239;x<=542;x+=3){float y=205+float(line-15)*4+float(std::sin(x*0.014+line*0.1)*62);
        if(x==239)wave.startNewSubPath(float(x),y);else wave.lineTo(float(x),y);}g.setColour(purple.withAlpha(0.09f));g.strokePath(wave,juce::PathStrokeType(0.7f));}
    g.setColour(juce::Colour(0xfff1ddff));g.setFont(25.f);g.drawText("OPEN DeHISS",27,24,207,34,juce::Justification::centredLeft);
    g.setColour(juce::Colour(0xff9989a9));g.setFont(20.f);g.drawText("OPEN DEHISS",265,321,260,29,juce::Justification::centred);
    g.setColour(juce::Colour(0xff34283f));g.fillRoundedRectangle(12,379,526,38,6);
    g.setColour(purple);g.setFont(13.f);g.drawText("HIGH END CUT",26,386,145,26,juce::Justification::centredLeft);
    g.setColour(juce::Colour(0xffa99ab5));g.setFont(10.f);g.drawText("> 15 kHz",170,386,70,26,juce::Justification::centredLeft);
    g.setColour(juce::Colour(0xffb89ecb).withAlpha(0.5f));g.drawRoundedRectangle(1,1,548,424,4,1);
}
