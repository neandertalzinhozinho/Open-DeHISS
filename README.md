# Open DeHISS

Plugin VST3 Windows x64 para redução de hiss, open source AGPLv3, em desenvolvimento beta.

Interface lilás com três knobs: Atenuação grande à direita, LF Bias e Bias à esquerda, Auto e Bypass embaixo. Com Auto desligado, Bias passa a Threshold. Gráficos próprios; nenhum recurso ou código do CEDAR é distribuído. Atenuação padrão **0 dB**, ajustável até **−40 dB**.

## Uso

Copie a pasta inteira `Open DeHISS.vst3` para `C:\Program Files\Common Files\VST3\`. No FL Studio: Options → Manage plugins → Find installed plugins. Procure Open DeHISS. Comece em 0 dB e desça gradualmente para −6, −12… conforme o ruído. Duplo clique nos knobs restaura o padrão. Auto estima o ruído ao longo do tempo; em modo manual, ajuste Threshold. Mix fica disponível na lista de parâmetros do host.

Latência reportada: 1024 amostras a 44,1/48 kHz; 2048 a 96 kHz. O plugin não altera configurações de áudio do Windows. Sem iLok, ativação ou comunicação de rede no código próprio.

## Build

Requisitos: Visual Studio 2022 Build Tools com C++, Windows SDK e CMake ≥3.22. Use um checkout curto (por exemplo C:\OpenDeHISS). JUCE 8.0.15 é baixado automaticamente de um commit fixado com hash do ZIP validado. Para build offline, passe `-DJUCE_SOURCE_DIR=C:/caminho/JUCE`.

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DOPEN_DEHISS_BUILD_HOST_CHECK=ON
cmake --build build --config Release --parallel 2
ctest --test-dir build -C Release -V
```

Saída: `build/OpenDeHISS_artefacts/Release/VST3/Open DeHISS.vst3`. GitHub Actions compila e testa no Windows; o ZIP fica nos artefatos de cada execução bem-sucedida.

## Escopo do beta

DSP próprio: STFT com janela seno e overlap de 50%, estimativa mediana de ruído com acompanhamento assimétrico, ganho espectral tipo Wiener e suavização temporal. Não há equivalência comprovada ao CEDAR. Preservação perceptiva da voz, musical noise, automação sem cliques e desempenho prolongado ainda estão em avaliação. Sons sustentados podem entrar na estimativa automática de ruído.

Testes: transparência 0 dB, latência, overlap-add, bypass, Mix=0, silêncio, NaN/Inf, atenuação manual, redução automática, canais estéreo, persistência de parâmetros, blocos variáveis e renderização da interface. O host de teste separado carrega o VST3 compilado.

## Licença

Código próprio AGPL-3.0-or-later (LICENSE.txt). JUCE utilizado sob AGPLv3; suas licenças e avisos de dependências acompanham o código baixado. Não há dependência de licença paga.
