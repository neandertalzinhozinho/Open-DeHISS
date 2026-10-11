// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include "DerivedChannel.h"
// Independent parallel adaptation. The longer analysis resolves dense voice
// partials; the derived path retains rapid broadband-noise response. No serial
// latency addition: both outputs are delayed to the same reported position.
class MultiResolutionChannel {
public:
    void prepare(double rate){
        fs=std::isfinite(rate)&&rate>=8000?rate:48000.;fine.prepare(fs);derived.prepare(fs);
        delay=std::max(fine.latency(),derived.latency());
        finePadding.assign(delay-fine.latency(),0);derivedPadding.assign(delay-derived.latency(),0);
        cursor=0;weight=0;attack=std::exp(-1/(fs*.02));release=std::exp(-1/(fs*.12));
    }
    int latency()const{return delay;}
    float process(float input,const HissSettings& settings){
        float a=fine.process(input,settings),b=derived.process(input,settings);
        align(a,finePadding);align(b,derivedPadding);
        const double target=settings.automatic?fine.denseSpectrumWeight():0.;
        const double alpha=target>weight?attack:release;weight=alpha*weight+(1-alpha)*target;
        ++cursor;return float(b+weight*(a-b));
    }
private:
    void align(float& value,std::vector<float>& padding){if(!padding.empty()){
        const auto index=cursor%padding.size();const float old=padding[index];padding[index]=value;value=old;}}
    HissChannel fine;DerivedChannel derived;std::vector<float> finePadding,derivedPadding;
    uint64_t cursor=0;double fs=48000,weight=0,attack=0,release=0;int delay=0;
};
