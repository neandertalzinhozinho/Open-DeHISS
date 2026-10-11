# Validação local — 11/10/2026

Versão 0.2.0, Windows x64 Release, MSVC 19.44, JUCE 8.0.15.

CTest: DSP e editor aprovados, incluindo as verificações herdadas do beta e as novas verificações de controles gráficos. Atenuação visual padrão 0 dB; ajuste do knob para −26 dB atualiza o parâmetro DSP. Modo manual mapeia o knob Bias para Threshold, inicialmente −65 dBFS. Renderizações em 0 e −26 dB inspecionadas visualmente.

Host isolado carregou o VST3 compilado: Open DeHISS. Confirmou atenuação padrão 0 dB e, após ajuste −12 dB, mediu redução automática de 5,44806 dB no estímulo de ruído estacionário. Saída finita, sem vazamento entre canais, bypass com erro absoluto zero após alinhamento da latência.

SHA256 do binário local: `D13566F609267DB0C9F09D6E5A5062E27C958FE247F387573AD8B02F4E343DA8`.

Não se afirma equivalência ao CEDAR nem validação perceptiva completa da voz. O teste de GUI verifica renderização e vinculação dos controles; uso e escalonamento na DAW ainda precisam de avaliação.

## High End Cut — 0.3.0

Controle independente 0…−40 dB, dedicado ao dehiss acima de 15 kHz, transição até 15,5 kHz. Todos os testes anteriores e os novos testes passaram. Com Atenuação geral=0 e High End Cut=−24, tons de 18/21 kHz classificados como ruído foram reduzidos em aproximadamente24 dB em44,1/48/96 kHz; alteração nos tons1/14 kHz menor0,001 dB. Teste no VST3 real, 48 kHz: perda na faixa baixa−0,000424737 dB; redução em18 kHz24,001 dB. Presets/GUI/default0/Nyquist≤15kvalidados. Preview550×426inspecionado.

SHA256 binário0.3.0: `707360CB0A63B2B1BEF078EDB9080DF72B716A27B60C96FFD6587BC521C3B88A`. Supressão adaptativa; não se promete apagar componentes acima de15 kHz classificados como sinal. Instalado após usuáriofecharFLStudio; versãoanteriorpreservada.

## Comparação com referência — 11/10/2026

A licença/avaliação da referência foi carregada normalmente. Foram concluídos32casos A/B (16sinais × Auto−12/−26), todos finitos. Bias/LFBias0, HighEndCut0, Mix100%,48kHz,bloco256. Atraso medido e alinhado por arquivo; métricas estacionárias após3s. O primeiro pré-teste automático lento apresentou23,1083dB de redução; a matriz final e a repetição com cadência por deadline apresentaram25,5735dB no ruído−65dBFS em−26. A diferença de cadência/caminho foi registrada, sem assumir determinismo global.

| Sinal e ajuste Auto | Redução CEDAR | Redução beta |
|---|---:|---:|
| Ruído branco−65dBFS,−12 | 11,436dB | 5,740dB |
| Ruído branco−65dBFS,−26 | 25,574dB | 7,168dB |
| Tom1,4kHz+ruído,−12 | 0,068dB | 11,995dB |
| Tom1,4kHz+ruído,−26 | 0,090dB | 25,907dB |
| Degrau de ruído−65→−45,−26 | 20,465dB | 4,879dB |

Valores dos tons são queda RMS total da mistura, dominada pelo tom, não medição isolada de sua amplitude. O beta trata componentes sustentados como ruído nesse cenário; preservação tonal e estimativa/suavização precisam ser corrigidas. Não foi feita validação de voz real nesta rodada. Os atrasos de tons foram estimados pelo ruído residual com uma rejeição ±100Hz do tom apenas para correlação, evitando ambiguidade entre ciclos. Valores agregados em [benchmark-2026-10-11.json](benchmark-2026-10-11.json).

O critério parcial proposto de diferença na redução RMS ≤0,5dB falhou nos54checks avaliáveis (dois canais, excluídos silêncio, impulso e canal sem entrada). Isso comprova divergência nesses cenários; não é certificação do fabricante. Os resultados de impulso e demais métricas requerem análise própria. Na repetição do ruído principal, a diferença de redução foi menor0,001dB; não comprova repetibilidade para toda a matriz.

O carregamento da referência não basta para validar o benchmark. Os primeiros renders offline não demonstraram atuação; a comparação válida usa pipeline cadenciado em tempo real, controle após preparação e sincronização do dispatcher, com atraso medido por arquivo. Detalhes de reprodução em [BENCHMARK.md](BENCHMARK.md). Testes do próprio beta passam, mas os resultados A/B demonstram que a equivalência não foi atingida.

## Beta 0.4.0
Resultados atuais, mudanças e limitações: [BETA-0.4.md](BETA-0.4.md). As seções acima registram versões anteriores; a latência atual é 4096 amostras a 48 kHz.

## Beta 0.5.0
Resultados de adaptação e limites: [BETA-0.5.md](BETA-0.5.md). Comparação sintética agregada em benchmark-0.5-2026-10-11.json.
