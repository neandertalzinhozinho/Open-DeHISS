# Beta 0.7 — processamento derivado e resolução adaptativa

## Mudança comprovada na candidata

A beta 0.7 ativa por padrão uma implementação independente das equações derivadas da auditoria estática do DSP: energia de curvatura da FFT, mediana global de 21 frames, dois ramos temporais/espectrais, combinação de probabilidades, perfil de ganho e reconstrução por janela circular do impulso e crossfade. Ela não contém código binário do CEDAR ou componentes de licença. Não há alegação de recuperação integral do algoritmo ou equivalência perceptiva.

A antecipação foi encurtada e renormalizada para respeitar 96 ms. As constantes adaptadas são próprias: ramo lento de 125 ms, largura espectral rápida de 1500 Hz e detecção persistente de aumento de ruído por 50 ms. A curva de probabilidade contém proteções numéricas próprias. O modo manual converte dBFS em energia de curvatura usando a mediana teórica de ruído branco; essa escala não foi declarada idêntica à escala interna do CEDAR.

Um segundo caminho, de maior resolução, resolve melhor os espaços entre os harmônicos da voz. Ambos rodam em paralelo e suas saídas são alinhadas ao mesmo atraso; as latências não são somadas. A seleção usa picos fortes em 800–6000 Hz comparados com pisos temporal e espectral instantâneo. Comparar apenas com o piso temporal produzia um falso disparo ao aumentar o hiss; o teste detectou essa regressão e ela foi corrigida.

## Critérios e resultados anteriores à identificação final da versão

| Critério | Resultado da candidata final R6 |
|---|---|
| Diferença RMS em regime até 0,5 dB em todos os canais ativos de cada caso, ajustes Auto −12/−26, Bias 0 | 28 de 28 casos passam |
| Degrau de ruído −65→−45 dBFS, ajuste −26 | CEDAR 20,465 dB; Open 20,836 dB; diferença 0,371 dB |
| Resíduo entre harmônicos em seis casos sintéticos, fundamentais 90/120/150 Hz, Bias 6 | Todos passam no mínimo de 25% da atenuação selecionada |
| Preservação de três eventos curtos: perda adicional no máximo 0,5 dB versus referência | Todos passam |
| Carregamento VST3, canais, bypass, High End Cut e silêncio | Passam no host separado |
| Atraso medido por impulso em 12 taxas de 8 a 384 kHz | Até 96 ms, erro de alinhamento zero |
| Partição dos blocos, estado e interface | Passam nos testes do processador |

São critérios separados, não uma porcentagem de qualidade sonora. Os 28 casos RMS excluem silêncio e impulso e não contam canais como casos independentes. As referências CEDAR foram processadas normalmente com licença ativa, em tempo real. Os testes de resíduos incluem artefatos na energia entre harmônicos; não medem ruído isolado sobre os mesmos harmônicos.

Nos eventos de 120/20/250 ms, as perdas RMS Open/CEDAR foram respectivamente 1,008/1,555 dB (fricativa sintética), 0,373/0,210 dB (evento difuso) e 0,006/2,236 dB (barítono). A referência também deixou resíduos entre harmônicos; a melhoria de resolução busca atender à necessidade do usuário além de reproduzir essa limitação.

## Uso e limitações

Atenuação começa em 0 dB, transparente; desça para selecionar a intensidade. Comece com −12 dB e Bias 0; experimente Bias 6 para resíduos sob voz. High End Cut começa desligado e atua acima de 15 kHz, com transição até 15,5 kHz. O bypass e Mix 0 mantêm o atraso para evitar desalinhamento. Versão e data aparecem na interface.

Em 48/96 kHz, o atraso interno é de 96 ms; em 44,1/88,2 kHz, 92,880 ms. Drivers e buffers da DAW acrescentam latência. Sons contínuos difusos podem ser confundidos com ruído; a seleção entre resoluções pode mudar o timbre. Não existe prova de ausência de ruído musical nem de naturalidade perceptiva em qualquer voz. A gravação pessoal foi processada localmente e não acompanha o código ou os artefatos públicos. Diferenças de saídas com ruído adicionado incluem mudanças não lineares na voz e não são um SNR isolado.

O código de análise binária, dumps e executáveis de referência não são distribuídos. O plugin usa código próprio AGPL-3.0-or-later e JUCE; não precisa de iLok, licença paga ou conexão de rede. A instalação não altera configurações de áudio do Windows. Preserve a versão anterior e feche a DAW antes de atualizar o VST3.

## Reprodução

O workflow Windows compila o motor novo por padrão e executa testes numéricos, DSP/interface, host VST3 e casos de barítono. A comparação com CEDAR requer uma instalação licenciada e os respectivos renders locais; ela não roda na CI pública. `OPEN_DEHISS_EXPERIMENTAL_DERIVED=OFF` seleciona o motor legado para investigações, sem representar o comportamento padrão da beta 0.7.
