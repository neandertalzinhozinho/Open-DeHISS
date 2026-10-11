# Beta 0.6 — calibração, identificação e limite de atraso

Implementação independente. Recuperação integral do algoritmo e equivalência perceptiva ao CEDAR continuam não demonstradas.

## Plugin compilado

A interface mostra versão e data: Beta 0.6.0, atualizado em 11/10/2026. No modo Auto, o início da confiança foi ajustado de razão de potência 4 para 6, com transição suave; a redução interna recebeu compensação de 0,25 dB. Modo manual e High End Cut mantêm suas escalas. O tamanho da FFT diminui nas taxas baixas para respeitar 96 ms de atraso interno.

O VST3 foi carregado em host separado e seu atraso medido por impulso em 12 taxas, de 8 a 384 kHz, com erro de alinhamento zero. Atrasos máximos observados: 92,880 ms em 22,05/44,1/88,2 kHz; 85,333 ms em 48/96 kHz. Este limite é do plugin: buffers e drivers acrescentam atraso na DAW.

82 verificações de DSP/interface e três testes CTest passaram. O host verificou processamento, isolamento de canais, bypass e High End Cut: redução de 24,001 dB em 18 kHz, perda de aproximadamente zero em 1 kHz. Seis casos de barítono sintético passaram; redução entre harmônicos em 800–6000 Hz, Bias 6 e Atenuação −26: 6,963/7,386/7,833 dB para fundamentais de 90/120/150 Hz.

## Comparação parcial com referência licenciada

Critério fixo: diferença da redução RMS em regime até 0,5 dB em todos os canais ativos de cada caso. São 28 casos elegíveis, com silêncio e impulso excluídos; canais não contam como casos independentes. A candidata passou em 26/28 (92,857%), acima dos 23 exigidos para 80% neste critério. Os dois degraus de ruído falharam. Essa porcentagem NÃO mede equivalência perceptiva ou recuperação do algoritmo; acomodação inicial, artefatos e voz precisam de critérios adicionais.

Na gravação pessoal, Bias 6 e Atenuação −26, a queda RMS na parte com fala foi 0,508 dB e a queda na faixa 800–6000 Hz foi 1,353 dB. Parte dessa energia pode pertencer à voz. Os arquivos pessoais não acompanham o repositório ou o ZIP do código.

## Pesquisa matemática em andamento

`tools/benchmark/recovered_kernel.py` contém uma expressão independente das equações derivadas de evidência estática: energia de curvatura espectral, mediana global, razão com LF Bias, dois ramos de suavização, combinação de probabilidades, perfil de ganho e reconstrução por janela circular do impulso e crossfade.

A antecipação temporal foi encurtada e renormalizada para caber em 96 ms; a mediana causal e o comportamento inicial diferem da referência. A direção do crossfade foi confirmada pela leitura dos helpers de cópia/multiplicação; isso é evidência estática, não uma validação de execução idêntica. Há proteções numéricas próprias.

Este protótipo NÃO está ativo no VST3. Passou em 13 testes matemáticos e foi renderizado com a gravação pessoal e estímulos sintéticos. Não será tratado como melhoria sonora comprovada antes da comparação completa. A configuração interna após construtores protegidos, escala manual e equivalência perceptiva continuam pendentes. Nenhum componente de licença foi modificado.

SHA256 da DLL beta 0.6: `B751571E07FE54D16819D2E5E644CD46755A9FCD3EFF49AB54DEB62FA94FCDF7`.
