// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <juce_dsp/juce_dsp.h>
#include <complex>
#include <memory>
#include <vector>
// Independent implementation of the audited circular impulse window and
// old/new crossfade, used by DerivedChannel in the derived build.
class DerivedSynthesis {
public:
    void prepare(int order){
        n=1<<order;hop=n/2;bins=n/2+1;fft=std::make_unique<juce::dsp::FFT>(order);
        oldWork.assign(2*n,0.0f);newWork.assign(2*n,0.0f);curveWork.assign(2*n,0.0f);
        previous.assign(bins,1.0f);window.assign(n,0.0f);
        for(int j=0;j<n/4;++j){
            window[j]=float(.5-.5*std::cos(2*juce::MathConstants<double>::pi*(j+hop/2)/hop));
            window[3*n/4+j]=float(.5-.5*std::cos(2*juce::MathConstants<double>::pi*j/hop));
        }
    }
    // The spectrum is the unnormalized real FFT of the historical audio frame.
    // All vectors and FFT state are prepared before this method is called.
    void render(const std::complex<float>* spectrum,const double* curve,float* output){
        std::fill(oldWork.begin(),oldWork.end(),0.0f);std::fill(curveWork.begin(),curveWork.end(),0.0f);
        for(int k=0;k<bins;++k){
            oldWork[2*k]=spectrum[k].real()*previous[k];oldWork[2*k+1]=spectrum[k].imag()*previous[k];
            curveWork[2*k]=float(curve[k]);
        }
        fft->performRealOnlyInverseTransform(oldWork.data());
        fft->performRealOnlyInverseTransform(curveWork.data());
        for(int j=0;j<n;++j)curveWork[j]*=window[j];
        std::fill(curveWork.begin()+n,curveWork.end(),0.0f);
        fft->performRealOnlyForwardTransform(curveWork.data());
        std::fill(newWork.begin(),newWork.end(),0.0f);
        for(int k=0;k<bins;++k){
            const float effective=curveWork[2*k];previous[k]=effective;
            newWork[2*k]=spectrum[k].real()*effective;newWork[2*k+1]=spectrum[k].imag()*effective;
        }
        fft->performRealOnlyInverseTransform(newWork.data());
        for(int j=0;j<hop;++j){const float ramp=float(j)/hop;
            output[j]=(1-ramp)*oldWork[n/4+j]+ramp*newWork[n/4+j];}
    }
private:
    int n=0,hop=0,bins=0;std::unique_ptr<juce::dsp::FFT> fft;
    std::vector<float> oldWork,newWork,curveWork,previous,window;
};
