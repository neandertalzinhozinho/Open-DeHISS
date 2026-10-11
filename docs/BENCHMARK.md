# Comparação com referência VST3 no Windows

O beta não é equivalente ao CEDAR AutoDehiss. Este harness carrega plugins normalmente pelas APIs VST3/JUCE e mede saídas; não extrai código nem contorna licenças. Para a referência comercial, é necessária licença/avaliação válida. A interface aberta na DAW é uma instância separada: os ajustes nela não mudam o benchmark.

## Preparação

Na raiz do repositório, com CMake, Visual Studio Build Tools e Python com NumPy:

```powershell
cmake -S . -B build -DOPEN_DEHISS_BUILD_REFERENCE_HOST=ON
cmake --build build --config Release --target OpenDeHISSReferenceHost
python tools/benchmark/test_audio_metrics.py
python tools/benchmark/test_compare_renders.py
python tools/benchmark/generate_stimuli.py
```

O gerador cria 16 WAVs float32 de 12 segundos a 48 kHz, com seed 20261011 e hashes no manifesto. Recusa sobrescrever um manifesto existente. O host recusa sobrescrever renders existentes. Para repetir a comparação, preserve os resultados anteriores e escolha outro diretório de saída.

## Renderização

Sintaxe do host:

```text
OpenDeHISSReferenceHost.exe bundle [inputDir outputDir attenuationDb autoBool thresholdDb [masterBypassNormalized [realtime]]]
```

Sem argumentos de render, apenas enumera parâmetros e testa silêncio. Os nomes e escalas de controles deste harness correspondem às versões testadas de Open DeHISS/CEDAR AutoDehiss; outros plugins exigem adaptação do mapeamento. Mono é duplicado para estéreo, estéreo é preservado. Cada arquivo recebe uma instância nova, bloco 256 e cauda suficiente para análise. High End Cut permanece no padrão 0 e Mix em 100%.

Exemplo de um par em Auto, −26 dB:

```powershell
$hostExe = '.\build\OpenDeHISSReferenceHost_artefacts\Release\OpenDeHISSReferenceHost.exe'
& $hostExe 'C:\Program Files\Common Files\VST3\CEDARAutoDehiss.vst3' outputs/AutoDehiss-test-stimuli outputs/equivalence-renders/cedar-realtime-auto--26 -26 1 -65 0 realtime
& $hostExe 'C:\Program Files\Common Files\VST3\Open DeHISS.vst3' outputs/AutoDehiss-test-stimuli outputs/equivalence-renders/open-auto--26 -26 1 -65
python tools/benchmark/compare_renders.py auto--26
python tools/benchmark/evaluate_equivalence.py
```

Repita com −12 e nomes `cedar-realtime-auto--12` / `open-auto--12`, e execute o comparador passando ambos os perfis. `realtime` significa modo VST3 em tempo real com alimentação cadenciada por software; não abre dispositivo nem acessa microfone. Sem essa opção usa modo offline. A referência testada exigiu validação em tempo real: renders offline não demonstraram atuação automática e não devem ser aceitos só porque o carregamento funcionou.

O host aplica controles após preparar a instância, sincroniza as atualizações do controlador por uma captura de estado somente em memória, mantém mensagens do Windows ativas e processa numa thread separada. Os logs CONFIG/FINAL registram os valores. Não publica ou grava o snapshot de estado.

## Validade dos resultados

O comparador mede atraso por correlação para cada arquivo e alinha antes de calcular RMS/bandas/resíduo. Não usa automaticamente a latência declarada: na referência foram observados caminhos de 1024 e 16128 amostras. Silêncio não permite medir atraso e usa o atraso do caso de banda larga como fallback. Para tons, usa apenas na estimativa do atraso o ruído residual num trecho central, removendo ±100Hz ao redor do tom; as métricas usam o áudio completo sem esse filtro. Essa estimativa foi testada com atraso conhecido de16128amostras. Primeiro validar atuação da referência e repetibilidade antes de interpretar diferenças. O avaliador aplica apenas um critério proposto de diferença RMS ≤0,5 dB; retorna código1 quando há divergências. Não cobre todos os requisitos de equivalência.

GitHub Actions verifica as métricas e o host carregando o plugin aberto. Não carrega a referência comercial no runner, que não possui sua licença.

Threshold manual não deve ser considerado semanticamente equivalente por usar o mesmo número: escalas/referências internas diferem. Como verificação extrema, referência em Manual, Threshold=0, Atenuação=−26 apresentou cerca de 25,58 dB de redução do ruído usado na rodada inicial; no beta com Threshold=−20 apresentou 26 dB. Isso comprova atuação em condições distintas, não equivalência de controles.

Testes finitos cobrem apenas os sinais e configurações executados. Resultados numéricos e diferenças conhecidas devem acompanhar qualquer afirmação de proximidade. Nenhum requisito de equivalência é considerado aprovado pelo simples sucesso dos testes do próprio beta.
