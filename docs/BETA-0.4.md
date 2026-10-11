# Beta 0.4.0 — evidência de 11/10/2026

Implementação independente. Sem equivalência comprovada ao CEDAR.

## Correções

O beta 0.3 reduzia um tom sustentado de 1,4 kHz como se fosse ruído e aplicava apenas cerca de 7 dB de redução em hiss com Atenuação −26. O novo estimador usa mediana temporal e vizinhança espectral robusta; a decisão usa potência média relativa ao piso. Janela Hann, FFT maior e overlap 75% melhoram a separação entre harmônicos. Uma alternativa experimental de proteção por fase foi rejeitada: deixava passar ruído entre harmônicos e podia criar energia residual. O candidato entregue não contém essa proteção.

Bias positivo aumenta a supressão de componentes fracos, inclusive coerentes. O padrão continua 0. Não há detecção garantida de quais componentes harmônicos o usuário considera indesejados.

## Validação

63 verificações DSP/editor passaram; CTest aprovou DSP/editor, carregamento/processamento do VST3 real e carregamento pelo host de referência. Nove testes das ferramentas de medição passaram. Três probes tonais fracos entre harmônicos de uma voz sintética de 120 Hz, Atenuação −26/Bias +10, foram reduzidos em 24,86, 25,37 e 20,79 dB (1,02/1,86/4,02 kHz). Probes apenas 10 Hz de um harmônico forte não ficaram resolvidos; não se afirma removê-los.

Regressão de hiss entre harmônicos: F0=90/120/150 Hz, muitos parciais até 6 kHz, hiss −65 dBFS, 48 kHz. Medição entre 800 Hz e 6 kHz exclui ±5 Hz de cada parcial e também contabiliza possíveis artefatos fora dos parciais. Em Atenuação −26/Bias +6, redução de 6,96/7,36/7,76 dB. Em −12/+6: 5,85/6,21/6,55 dB. O mínimo de regressão é 25% do limite escolhido; não é um critério de equivalência perceptiva. Há ruído residual sob voz e isto requer mais trabalho.

## Comparação reutilizando referências licenciadas

16 estímulos por ajuste, 48 kHz, blocos 256, Auto/Bias0, High End Cut0, métricas após 3 s e alinhamento medido por arquivo.

| Entrada / ajuste | CEDAR | Open 0.4 |
|---|---:|---:|
| Hiss −65 dBFS / −12 | 11,436 dB | 11,739 dB |
| Hiss −65 dBFS / −26 | 25,574 dB | 23,267 dB |
| Tom 1,4 kHz + hiss / −26, queda RMS total | 0,090 dB | 0,001 dB |
| Degrau de hiss −65→−45 / −26 | 20,465 dB | 7,752 dB |

A resposta a aumentos de ruído ainda diverge bastante. O resultado de tom mede a mistura, não só o ruído. Não foi atingida equivalência. Os resultados agregados e sintéticos acompanham o repositório; gravações pessoais não são publicadas.

## Custo e instalação

Latência 4096 amostras a 44,1/48 kHz; 8192 a 96 kHz. Aproximadamente 85 ms a 48/96 kHz, maior que o beta anterior. Não recomendado assumir monitoramento confortável sem avaliar esse atraso. Zero dB, bypass e Mix=0 continuam dry exato com atraso compensado.

Feche a DAW antes de substituir a pasta do plugin; preserve a versão anterior em outro diretório. O ZIP contém a pasta VST3 inteira, README e licença. A instalação existente não é substituída automaticamente enquanto a DAW está aberta.

SHA256 DLL Windows x64: `A30976805E647E1AE1AEAFE9A027A7FFE38B21E6B427B7324708D7C0C9BBFE0C`.
