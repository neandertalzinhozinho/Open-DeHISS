// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once
#include <algorithm>
#include <cmath>
#include <complex>
#include <vector>
// Independent mathematical expression of audited DSP evidence, not original
// source. Experimental only: the installed plugin does not call this module.
namespace openhiss_derived {
class BoundedTemporal {
public:
    void prepare(int bins,int n,double fs,double tau){
        state.assign(bins,0.);mass=0;alpha=std::exp(-n/(2*fs*tau));
        futureLimit=std::min(19,std::max(0,int(std::floor((.096*fs-n)/(n/2)))));
    }
    // Contiguous chronological frames, current first. No allocation here.
    void process(const double* frames,int count,double* result){
        const int bins=int(state.size()),future=std::min(count-1,futureLimit);
        mass=alpha*mass+1.;double denominator=mass,weight=1.;
        for(int j=1;j<=future;++j){denominator+=weight;weight*=alpha;}
        for(int k=0;k<bins;++k){
            state[k]=alpha*state[k]+frames[k];double value=state[k];weight=1.;
            for(int j=1;j<=future;++j){value+=weight*frames[j*bins+k];weight*=alpha;}
            result[k]=value/denominator;
        }
    }
    int lookahead()const{return futureLimit;}
private:
    std::vector<double> state;double mass=0,alpha=0;int futureLimit=0;
};
class GlobalNoiseHistory {
public:
    void prepare(int usedBins){bins=usedBins;frames=position=0;history.assign(21*bins,0.);scratch.resize(21*bins);}
    void push(const double* energy){std::copy_n(energy,bins,history.data()+position*bins);position=(position+1)%21;frames=std::min(21,frames+1);}
    double median(int recent=21){
        const int count=std::min(frames,recent);int filled=0;
        for(int j=0;j<count;++j){const int slot=(position+20-j)%21;
            std::copy_n(history.data()+slot*bins,bins,scratch.data()+filled);filled+=bins;}
        if(!filled)return 0.;
        std::nth_element(scratch.begin(),scratch.begin()+filled/2,scratch.begin()+filled);return scratch[filled/2];
    }
private:
    std::vector<double> history,scratch;int bins=0,frames=0,position=0;
};
inline void curvature(const std::complex<double>* z,double* e,int bins){
    e[0]=std::norm(std::complex<double>(z[0].real()-z[1].real(),z[0].imag()));
    for(int k=1;k<bins-1;++k)e[k]=std::norm(z[k]-.5*(z[k-1]+z[k+1]));
    e[bins-1]=std::norm(std::complex<double>(z[bins-1].real()-z[bins-2].real(),z[bins-1].imag()));
}
inline double upperMedian(double* scratch,int count){
    std::nth_element(scratch,scratch+count/2,scratch+count);return scratch[count/2];
}
inline void spectral(const double* input,double* out,int bins,int n,double fs,double width){
    const double lambda=std::exp(-fs/(n*width));
    const double s=(1-lambda)/(1+lambda),v=s*lambda;double state=0;
    for(int j=bins-1;j>0;--j)state=lambda*state+input[j];
    for(int j=0;j<bins-1;++j){out[j]=v*state;state=lambda*state+input[j];}
    out[bins-1]=v*state;
    for(int j=bins-1;j>=0;--j){state=lambda*state+input[j];out[j]+=s*state;}
}
inline double probability(double first,double second){
    // Our numerical protections match the independently tested Python model.
    first=std::clamp(first,-1.+1e-12,1.);second=std::clamp(second,-1.+1e-12,1.);
    const double a=5+100*first,b=-5+100*second,m=std::max({a,b,0.});
    const double w1=std::exp(a-m),w2=std::exp(b-m),w0=std::exp(-m);
    return std::clamp((w1*(1-first)/(1+first)+w2*(1-second)/(1+second)+w0)/(w1+w2+w0),0.,1.);
}
inline double gain(double probability,double frequency,double attenuation){
    const double f2=frequency*frequency;
    const double floor=std::pow(10.,attenuation/20.)*1.25*(f2+81e6)/(f2+4500*frequency+81e6);
    const double x=1-probability;return floor+(1-floor)*(1.5*x-.5*x*x);
}
}
