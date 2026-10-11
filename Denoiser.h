// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <juce_dsp/juce_dsp.h>
#include <array>
#include <algorithm>
#include <cmath>
#include <memory>
#include <vector>
struct HissSettings { float reduction=12, highEndCut=0, bias=0, threshold=-65, lowBias=0, mix=1; bool automatic=true, bypass=false; };
class HissChannel
{
public:
    void prepare(double sampleRate)
    {
        fs=sampleRate; order=10;
        while ((1<<order) < sampleRate/48.828125 && order<13) ++order;
        n=1<<order; hop=n/2; bins=n/2+1;
        fft=std::make_unique<juce::dsp::FFT>(order);
        input.assign(n,0); dry.assign(n,0); output.assign(4*n,0);
        work.assign(2*n,0); window.resize(n); noise.assign(bins,0); gain.assign(bins,1);
        histories.assign(bins*21,0); frames=0; historyPos=0; cursor=0; sinceFrame=0;
        for(int i=0;i<n;++i) window[i]=float(std::sin(juce::MathConstants<double>::pi*i/n));
    }
    int latency() const {return n;}
    float process(float sample,const HissSettings& s)
    {
        if(!std::isfinite(sample)) sample=0;
        sample=std::clamp(sample,-16.f,16.f);
        const int pos=int(cursor%n), outPos=int(cursor%output.size());
        const float delayed=dry[pos]; dry[pos]=sample; input[pos]=sample;
        const float wet=output[outPos]; output[outPos]=0;
        if(++sinceFrame==hop){sinceFrame=0;frame(s);}
        ++cursor;
        const bool inactive=s.reduction<=0 && (s.highEndCut<=0 || fs*0.5<=15000);
        const float selected=(s.bypass || inactive) ? delayed : delayed+s.mix*(wet-delayed);
        return std::isfinite(selected) ? selected : 0;
    }
private:
    void frame(const HissSettings& s)
    {
        const int start=int((cursor+1)%n);
        std::fill(work.begin(),work.end(),0.f);
        for(int i=0;i<n;++i) work[i]=input[(start+i)%n]*window[i];
        fft->performRealOnlyForwardTransform(work.data());
        const int used=int(std::min<uint64_t>(frames+1,21));
        const double manualPower=std::pow(10.0,s.threshold/10.0)*n*0.5;
        const double timeGain=std::exp(-double(hop)/(fs*0.035));
        for(int k=0;k<bins;++k)
        {
            const double real=work[2*k], imag=work[2*k+1];
            const double p=real*real+imag*imag;
            histories[k*21+historyPos]=p;
            std::array<double,21> sorted{};
            std::copy_n(histories.begin()+k*21,used,sorted.begin());
            std::sort(sorted.begin(),sorted.begin()+used);
            const double estimate=sorted[used/2]/std::log(2.0);
            if(frames==0) noise[k]=estimate;
            else {const double alpha=std::exp(-double(hop)/(fs*(estimate<noise[k]?0.15:3.0)));
                  noise[k]=alpha*noise[k]+(1-alpha)*estimate;}
            const double frequency=double(k)*fs/n;
            // Same noise estimator and suppression law, restricted to the high band.
            // A short transition ABOVE 15 kHz avoids a discontinuous spectral edge.
            const double highWeight=std::clamp((frequency-15000.0)/500.0,0.0,1.0);
            const double effectiveReduction=std::max(double(s.reduction),s.highEndCut*highWeight);
            const double floorGain=std::pow(10.0,-effectiveReduction/20.0);
            const double shape=std::pow(10.0,(s.bias+s.lowBias*std::max(0.0,1.0-frequency/5000.0))/10.0);
            const double np=(s.automatic?noise[k]:manualPower)*shape;
            // Independent beta baseline: Wiener-style spectral suppression, not recovered CEDAR code.
            const double target=std::max(floorGain,std::sqrt(std::max(0.0,1.0-np/(p+1e-30))));
            gain[k]=timeGain*gain[k]+(1-timeGain)*target;
            const double g=(effectiveReduction<=0 || s.bypass)?1.0:gain[k];
            work[2*k]=float(real*g); work[2*k+1]=float(imag*g);
        }
        fft->performRealOnlyInverseTransform(work.data());
        for(int i=0;i<n;++i) output[(cursor+1+i)%output.size()]+=work[i]*window[i];
        ++frames; historyPos=(historyPos+1)%21;
    }
    double fs=48000; int order=10,n=1024,hop=512,bins=513,sinceFrame=0,historyPos=0;
    uint64_t frames=0, cursor=0;
    std::unique_ptr<juce::dsp::FFT> fft;
    std::vector<float> input,dry,output,work,window;
    std::vector<double> histories,noise,gain;
};
