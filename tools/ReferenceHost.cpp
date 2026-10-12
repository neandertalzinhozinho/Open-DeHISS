// SPDX-License-Identifier: AGPL-3.0-or-later
#if REFERENCE_WITH_EDITOR
#include <juce_audio_processors/juce_audio_processors.h>
#else
#include <juce_audio_processors_headless/juce_audio_processors_headless.h>
#endif
#include <juce_audio_formats/juce_audio_formats.h>
#include <iostream>
#include <windows.h>
#include <thread>
#include <atomic>
#include <chrono>
#if REFERENCE_WITH_EDITOR
struct ReferenceWindow : juce::DocumentWindow {
    ReferenceWindow():DocumentWindow("Reference test host",juce::Colours::black,DocumentWindow::closeButton){setUsingNativeTitleBar(true);}
    void closeButtonPressed()override{setVisible(false);}
};
#endif
int main(int argc, char** argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    std::cout << std::unitbuf;
    std::atomic<bool> complete{false};
    std::thread watchdog([&] { for(int i=0;i<(argc>2?18000:600) && !complete;++i) Sleep(100); if(!complete) { std::cout << "TIMEOUT: probe deadline exceeded" << std::endl; ExitProcess(124); } });
    struct Completion { std::atomic<bool>& flag; std::thread& thread; ~Completion(){flag=true;thread.join();} } finish{complete,watchdog};
    juce::ScopedJuceInitialiser_GUI runtime;
    if (argc != 2 && argc != 7 && argc != 8 && argc != 9 && argc != 10) { std::cout << "bundle [inputDir outputDir attenuationDb autoBool thresholdDb [masterBypassNormalized [realtime|offline [biasDb]]]]" << std::endl; return 2; }
    std::cout << "Scanning " << argv[1] << std::endl;
    juce::AudioPluginFormatManager manager;
#if REFERENCE_WITH_EDITOR
    auto format = std::make_unique<juce::VST3PluginFormat>();
#else
    auto format = std::make_unique<juce::VST3PluginFormatHeadless>();
#endif
    auto* scanner = format.get(); manager.addFormat(std::move(format));
    juce::OwnedArray<juce::PluginDescription> descriptions;
    scanner->findAllTypesForFile(descriptions, argv[1]);
    std::cout << "Descriptions: " << descriptions.size() << std::endl;
    if (descriptions.isEmpty()) return 3;
    juce::String error;
    std::unique_ptr<juce::AudioPluginInstance> instance;
    bool callbackDone=false;
    manager.createPluginInstanceAsync(*descriptions[0], 48000, 256,
        [&](std::unique_ptr<juce::AudioPluginInstance> loaded, const juce::String& problem) {
            instance=std::move(loaded); error=problem; callbackDone=true;
        });
    while(!callbackDone) { MSG message; while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); } Sleep(1); }
    if (!instance) { std::cout << "Load error: " << error << std::endl; return 4; }
    std::cout << "Loaded: " << instance->getName() << std::endl;
    int index = 0;
    for (auto* p : instance->getParameters()) {
        std::cout << "Parameter " << index++ << " name=" << p->getName(128)
                  << " value=" << p->getValue() << " text=" << p->getText(p->getValue(), 128)
                  << " endpoints=" << p->getText(0,128) << "," << p->getText(1,128) << std::endl;
    }
    instance->setRateAndBufferSizeDetails(48000, 256); instance->prepareToPlay(48000, 256);
    juce::AudioBuffer<float> buffer(juce::jmax(2, instance->getTotalNumInputChannels()),256);
    juce::MidiBuffer midi;
    for (int i=0;i<400;++i) { buffer.clear(); instance->processBlock(buffer,midi); }
    std::cout << "PASS silence processing; latency=" << instance->getLatencySamples() << std::endl;
    instance->releaseResources();
    if(argc>=7) {
        instance.reset();
        juce::AudioFormatManager audio; audio.registerBasicFormats();
        juce::File outputDir=juce::File::getCurrentWorkingDirectory().getChildFile(argv[3]);
        if(!outputDir.createDirectory()) return 5;
        const auto inputDir=juce::File::getCurrentWorkingDirectory().getChildFile(argv[2]);
        juce::Array<juce::File> files; inputDir.findChildFiles(files,juce::File::findFiles,false,"*.wav");
        files.sort();
        for(const auto& file:files) {
            const auto destination=outputDir.getChildFile(file.getFileName());
            if(destination.exists()) { std::cout << "Refusing overwrite: " << destination.getFullPathName() << std::endl; return 6; }
            std::unique_ptr<juce::AudioFormatReader> reader(audio.createReaderFor(file)); if(!reader) return 7;
            if(!std::isfinite(reader->sampleRate) || reader->sampleRate<8000 || reader->sampleRate>384000) {
                std::cerr << "Unsupported WAV sample rate: " << reader->sampleRate << std::endl; return 8;
            }
            callbackDone=false;
            manager.createPluginInstanceAsync(*descriptions[0],reader->sampleRate,256,
                [&](std::unique_ptr<juce::AudioPluginInstance> loaded,const juce::String& problem){instance=std::move(loaded);error=problem;callbackDone=true;});
            while(!callbackDone){MSG message;while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}Sleep(1);}
            if(!instance) {std::cout << error << std::endl;return 9;}
#if REFERENCE_WITH_EDITOR
            auto window=std::make_unique<ReferenceWindow>();
            if(auto* editor=instance->createEditorIfNeeded()){window->setContentOwned(editor,true);window->centreWithSize(editor->getWidth(),editor->getHeight());window->setVisible(true);std::cout << "Official editor opened" << std::endl;}
#endif
            const bool realtime=argc>=9 && juce::String(argv[8])=="realtime";
            instance->setNonRealtime(!realtime);
            instance->setRateAndBufferSizeDetails(reader->sampleRate,256);instance->prepareToPlay(reader->sampleRate,256);
            for(auto* p:instance->getParameters()) {
                const auto name=p->getName(128);
                // Test kIsBypass semantics: zero disables host bypass.
                if(name=="Master Bypass") p->setValueNotifyingHost(argc>=8?float(std::atof(argv[7])):0);
                if(name=="Attenuation" || name.startsWith("Atenuacao")) p->setValueNotifyingHost(float((std::atof(argv[4])+40)/40));
                if(name=="Automatic Threshold" || name=="Automatico") p->setValueNotifyingHost(float(std::atoi(argv[5])));
                if(name=="Threshold") p->setValueNotifyingHost(float((std::atof(argv[6])+99)/99));
                if(name.startsWith("Noise floor")) p->setValueNotifyingHost(float((std::atof(argv[6])+90)/70));
                if(argc==10 && (name=="Bias" || name=="Bias (dB)")) p->setValueNotifyingHost(float((std::atof(argv[9])+10)/20));
                std::cout << "CONFIG " << name << " normalized=" << p->getValue() << " text=" << p->getText(p->getValue(),128) << std::endl;
            }
            // Flush JUCE's asynchronous controller parameter dispatcher before rendering.
            juce::MemoryBlock stateSnapshot;
            instance->getStateInformation(stateSnapshot); // JUCE explicitly flushes pending controller changes here.
            const auto dispatchStart=GetTickCount64();
            while(GetTickCount64()-dispatchStart<250){MSG message;while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}Sleep(1);}
            const int latency=instance->getLatencySamples();
            const int length=int(reader->lengthInSamples);const int total=length+latency+96000;
            juce::AudioBuffer<float> input(2,total); input.clear();reader->read(&input,0,length,0,true,true);
            if(reader->numChannels==1)input.copyFrom(1,0,input,0,0,length);
            juce::WavAudioFormat wav; auto stream=destination.createOutputStream();
            if(!stream) return 10;
            std::unique_ptr<juce::AudioFormatWriter> writer(wav.createWriterFor(stream.release(),reader->sampleRate,2,32,{},0));
            if(!writer)return 11;
            juce::AudioBuffer<float> block(2,256);
            bool finite=true;
            std::atomic<bool> renderDone{false};int renderError=0;
            std::thread audioThread([&] {
            const auto renderStart=std::chrono::steady_clock::now();
            for(int pos=0;pos<total;pos+=256) {
                const int n=(std::min)(256,total-pos);block.setSize(2,n,false,false,true);
                for(int ch=0;ch<2;++ch)block.copyFrom(ch,0,input,ch,pos,n);
                instance->processBlock(block,midi);
                if(realtime)std::this_thread::sleep_until(renderStart+std::chrono::microseconds(static_cast<long long>((pos+n)*1000000.0/reader->sampleRate)));
                for(int ch=0;ch<2;++ch)for(int i=0;i<n;++i)finite &= std::isfinite(block.getSample(ch,i));
                if(!writer->writeFromAudioSampleBuffer(block,0,n)){renderError=12;break;}
            }
            renderDone=true;
            });
            while(!renderDone){MSG message;while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}Sleep(1);}
            audioThread.join();if(renderError)return renderError;
            for(auto* p:instance->getParameters()) std::cout << "FINAL " << p->getName(128) << " normalized=" << p->getValue() << " text=" << p->getText(p->getValue(),128) << std::endl;
            writer.reset();instance->releaseResources();
#if REFERENCE_WITH_EDITOR
            window.reset();
#endif
            instance.reset();
            std::cout << "RENDER " << file.getFileName() << " latency=" << latency << " finite=" << finite << " frames=" << total << std::endl;
            if(!finite)return 13;
        }
        std::cout << "PASS renders=" << files.size() << std::endl;
    }
    return 0;
}
