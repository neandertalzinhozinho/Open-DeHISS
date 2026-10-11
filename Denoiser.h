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
        fs=std::isfinite(sampleRate) && sampleRate>=8000?sampleRate:48000; order=12;
        while ((1<<order) < sampleRate/11.71875 && order<13) ++order;
        // Respect the explicit 96 ms budget, including low sample rates.
        while(order>1 && double(1<<order)/fs>.096)--order;
        n=1<<order; hop=n/4; bins=n/2+1;
        fft=std::make_unique<juce::dsp::FFT>(order);
        input.assign(n,0); dry.assign(n,0); output.assign(4*n,0);
        work.assign(2*n,0); window.resize(n); noise.assign(bins,0); gain.assign(bins,1);
        histories.assign(bins*21,0); frames=0; historyPos=0; cursor=0; sinceFrame=0; rapidTrackingFrames=0; denseWeight=0;
        power.assign(bins,0); temporalEstimate.assign(bins,0); averagedPower.assign(bins,0); frameEstimate.assign(bins,0);
        // Hann/75% overlap reduces leakage from dense vocal harmonics into hiss
        // bins. Sum of squared periodic Hann windows is 1.5.
        for(int i=0;i<n;++i) window[i]=float(.5-.5*std::cos(2*juce::MathConstants<double>::pi*i/n));
    }
    int latency() const {return n;}
    float denseSpectrumWeight()const{return denseWeight;}
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
        const double averageAlpha=std::exp(-double(hop)/(fs*0.060));
        int risingBins=0, examinedBins=0;
        for(int k=0;k<bins;++k)
        {
            const double real=work[2*k], imag=work[2*k+1];
            const double p=real*real+imag*imag;
            power[k]=p;
            histories[k*21+historyPos]=p;
            std::array<double,21> sorted{};
            std::copy_n(histories.begin()+k*21,used,sorted.begin());
            std::sort(sorted.begin(),sorted.begin()+used);
            temporalEstimate[k]=sorted[used/2]/std::log(2.0);
        }
        for(int k=0;k<bins;++k)
        {
            // A sustained narrow component must not train its own noise floor.
            // Use robust neighbouring temporal estimates, excluding the main lobe.
            std::array<double,29> neighbours{};int count=0;
            for(int j=std::max(0,k-14);j<=std::min(bins-1,k+14);++j)
                if(std::abs(j-k)>2)neighbours[count++]=temporalEstimate[j];
            std::sort(neighbours.begin(),neighbours.begin()+count);
            const double spectralFloor=count?neighbours[count/4]*1.3:temporalEstimate[k];
            const double estimate=std::min(temporalEstimate[k],spectralFloor);
            frameEstimate[k]=estimate;
            const double f=double(k)*fs/n;
            if(f>=800 && f<=12000){++examinedBins;if(estimate>noise[k]*4 && noise[k]>1e-25)++risingBins;}
        }
        // A median over 21 frames rejects brief consonants. Only a persistent
        // rise across most of the speech/high band accelerates floor tracking;
        // individual harmonics keep the conservative upward time constant.
        const bool broadbandRise=examinedBins>0 && risingBins>examinedBins*.65;
        if(frames>=21 && broadbandRise)rapidTrackingFrames=int(std::ceil(fs*.8/hop));
        else if(rapidTrackingFrames>0)--rapidTrackingFrames;
        for(int k=0;k<bins;++k)
        {
            const double estimate=frameEstimate[k];
            if(frames==0) noise[k]=estimate;
            else {const double alpha=std::exp(-double(hop)/(fs*(frames<21?0.020:(estimate<noise[k]?0.15:(rapidTrackingFrames>0?0.15:3.0)))));
                  noise[k]=alpha*noise[k]+(1-alpha)*estimate;}
            const double observed=power[k];
            if(frames==0)averagedPower[k]=observed;
            else averagedPower[k]=averageAlpha*averagedPower[k]+(1-averageAlpha)*observed;
            const double frequency=double(k)*fs/n;
            // Same noise estimator and suppression law, restricted to the high band.
            // A short transition ABOVE 15 kHz avoids a discontinuous spectral edge.
            const double highWeight=std::clamp((frequency-15000.0)/500.0,0.0,1.0);
            // Small Auto-only floor calibration from the licensed reference
            // sweeps. Preserve exact manual/high-band amounts and default zero.
            const double mainReduction=s.automatic?std::max(0.0,double(s.reduction)-.25):double(s.reduction);
            const double effectiveReduction=std::max(mainReduction,s.highEndCut*highWeight);
            const double floorGain=std::pow(10.0,-effectiveReduction/20.0);
            const double shape=std::pow(10.0,(s.bias+s.lowBias*std::max(0.0,1.0-frequency/5000.0))/10.0);
            const double np=(s.automatic?noise[k]:manualPower)*shape;
            // Independent probability-like classifier. Averaging avoids treating
            // random frame peaks in stationary hiss as useful signal.
            const double ratio=averagedPower[k]/(np+1e-30);
            const double confidence=std::clamp((ratio-6.0)/6.0,0.0,1.0);
            // No unconditional tonal exemption: weak coherent residue is still
            // attenuated, and positive Bias increases suppression under speech.
            const double useful=confidence*confidence*(3-2*confidence);
            const double target=floorGain+(1-floorGain)*useful;
            const double timeGain=std::exp(-double(hop)/(fs*(target>gain[k]?0.005:0.035)));
            gain[k]=timeGain*gain[k]+(1-timeGain)*target;
            const double g=(effectiveReduction<=0 || s.bypass)?1.0:gain[k];
            work[2*k]*=float(g); work[2*k+1]*=float(g);
        }
        int peaks=0;
        for(int k=1;k<bins-1;++k){const double f=k*fs/n;
            if(f<800||f>6000)continue;
            std::array<double,29> local{};int count=0;
            for(int j=std::max(0,k-14);j<=std::min(bins-1,k+14);++j)if(std::abs(j-k)>2)local[count++]=power[j];
            std::sort(local.begin(),local.begin()+count);
            const double instantFloor=count?local[count/4]*1.3:frameEstimate[k];
            if(power[k]>power[k-1]&&power[k]>power[k+1]&&power[k]>25*std::max({frameEstimate[k],instantFloor,1e-30}))++peaks;}
        denseWeight=float(std::clamp((peaks-4)/4.,0.,1.));
        fft->performRealOnlyInverseTransform(work.data());
        for(int i=0;i<n;++i) output[(cursor+1+i)%output.size()]+=work[i]*window[i]*(2.f/3.f);
        ++frames; historyPos=(historyPos+1)%21;
    }
    double fs=48000; int order=10,n=1024,hop=512,bins=513,sinceFrame=0,historyPos=0,rapidTrackingFrames=0;
    uint64_t frames=0, cursor=0;float denseWeight=0;
    std::unique_ptr<juce::dsp::FFT> fft;
    std::vector<float> input,dry,output,work,window;
    std::vector<double> histories,noise,gain,power,temporalEstimate,averagedPower,frameEstimate;
};
