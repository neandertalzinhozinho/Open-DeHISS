// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include "Denoiser.h"
#include "RecoveredMath.h"
#include "RecoveredSynthesis.h"
// Experimental independent bounded reconstruction; not the released processor.
class DerivedChannel {
public:
    void prepare(double rate){
        fs=std::isfinite(rate)&&rate>=8000?rate:48000.;int order=2;
        while(fs/(1<<order)>48.828125)++order;
        n=1<<order;hop=n/2;bins=n/2+1;
        ahead=std::max(0,int(std::floor((.096*fs-n)/hop)));slots=ahead+1;delay=n+ahead*hop;
        fft=std::make_unique<juce::dsp::FFT>(order);synthesis.prepare(order);
        input.assign(n,0.0f);dry.assign(delay,0.0f);output.assign(delay+n,0.0f);work.assign(2*n,0.0f);
        spectra.assign(slots*bins,{});energyZ.resize(bins);energy.resize(bins);qHistory.assign(slots*bins,0);
        pending.resize(slots*bins);fast.resize(bins);slow.resize(bins);fastSmooth.resize(bins);slowSmooth.resize(bins);curve.resize(bins);block.resize(hop);
        usedBins=std::min(int(n*24000/fs),n/2);noise.prepare(usedBins);
        temporalFast.prepare(bins,n,fs,1e-5);temporalSlow.prepare(bins,n,fs,.125);
        cursor=frames=0;rising=hold=0;
    }
    int latency()const{return delay;}
    float process(float value,const HissSettings& settings){
        value=std::isfinite(value)?std::clamp(value,-16.f,16.f):0.f;
        const int dryPos=int(cursor%dry.size()),outPos=int(cursor%output.size());
        const float delayed=dry[dryPos],wet=output[outPos];dry[dryPos]=value;output[outPos]=0;
        input[cursor%n]=value;++cursor;
        if(cursor>=uint64_t(3*n/4)&&(cursor-3*n/4)%hop==0)frame(settings);
        const bool inactive=settings.reduction<=0&&(settings.highEndCut<=0||fs/2<=15000);
        const float result=settings.bypass||inactive?delayed:delayed+settings.mix*(wet-delayed);
        return std::isfinite(result)?result:0.f;
    }
private:
    void frame(const HissSettings& s){
        std::fill(work.begin(),work.end(),0.0f);for(int j=0;j<n;++j)work[j]=input[(cursor+j)%n];
        fft->performRealOnlyForwardTransform(work.data());const int slot=int(frames%slots);
        auto* z=spectra.data()+slot*bins;
        for(int k=0;k<bins;++k){z[k]={work[2*k],work[2*k+1]};energyZ[k]=std::complex<double>(z[k]);}
        openhiss_derived::curvature(energyZ.data(),energy.data(),bins);noise.push(energy.data());
        double estimate=noise.median();const double current=noise.median(1);
        rising=current>4*std::max(estimate,1e-100)?rising+1:0;
        if(rising>=int(std::ceil(.04*fs/hop)))hold=21;
        if(hold>0){estimate=std::max(estimate,noise.median(3));--hold;}
        // Independent manual dBFS calibration: median complex curvature energy
        // of white noise is ln(2)*1.5*N*inputVariance (unnormalized FFT).
        const double floor=s.automatic?estimate*std::pow(10.,s.bias/10.):std::pow(10.,s.threshold/10.)*n*1.5*std::log(2.);
        const double c=n*5000/fs,r=std::pow(10.,s.lowBias/10.+2),a=r<=1?c:c/r,b=r<=1?c*r:c;
        for(int k=0;k<bins;++k){const double q=(k+a)*energy[k]/((k+b)*(floor+1e-100));qHistory[slot*bins+k]=1-2/(q+1);}
        if(frames>=uint64_t(ahead)){
            const uint64_t oldest=frames-ahead;
            for(int j=0;j<slots;++j)std::copy_n(qHistory.data()+int((oldest+j)%slots)*bins,bins,pending.data()+j*bins);
            temporalFast.process(pending.data(),slots,fast.data());temporalSlow.process(pending.data(),slots,slow.data());
            std::fill_n(fast.begin(),std::min(bins,int(n*2000/fs)),0.);
            openhiss_derived::spectral(fast.data(),fastSmooth.data(),bins,n,fs,1500);
            openhiss_derived::spectral(slow.data(),slowSmooth.data(),bins,n,fs,1);
            for(int k=0;k<bins;++k){const double f=k*fs/n;
                const double attenuation=std::max(double(s.reduction),s.highEndCut*std::clamp((f-15000)/500,0.,1.));
                curve[k]=attenuation<=0?1:openhiss_derived::gain(openhiss_derived::probability(fastSmooth[k],slowSmooth[k]),f,-attenuation);}
            synthesis.render(spectra.data()+int(oldest%slots)*bins,curve.data(),block.data());
            for(int j=0;j<hop;++j)output[(oldest*hop+delay+j)%output.size()]=block[j];
        }
        ++frames;
    }
    double fs=48000;int n=0,hop=0,bins=0,ahead=0,slots=0,delay=0,usedBins=0,rising=0,hold=0;
    uint64_t cursor=0,frames=0;std::unique_ptr<juce::dsp::FFT> fft;DerivedSynthesis synthesis;
    openhiss_derived::BoundedTemporal temporalFast,temporalSlow;openhiss_derived::GlobalNoiseHistory noise;
    std::vector<float> input,dry,output,work,block;std::vector<std::complex<float>> spectra;
    std::vector<std::complex<double>> energyZ;std::vector<double> energy,qHistory,pending,fast,slow,fastSmooth,slowSmooth,curve;
};
