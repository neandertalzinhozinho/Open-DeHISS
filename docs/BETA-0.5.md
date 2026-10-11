# Beta0.5 — adaptação de ruído e comparação sob voz

Implementação independente, sem equivalência comprovada ao CEDAR.

## Mudança

O acompanhamento do piso podia levar segundos quando o hiss aumentava. Agora uma elevação de potência superior a4× em mais de65% dos bins de800–12000 Hz, observada no estimador temporal robusto, ativa o acompanhamento de150 ms por0,8 s. Elevações isoladas de harmônicos não acionam o mesmo mecanismo. Não há proteção tonal incondicional, nem alteração de parâmetros do usuário.

A mediana de21 frames impõe uma espera antes de reconhecer a mudança. Isso preserva eventos curtos, mas permite vazamento no começo do aumento de hiss. Sons difusos prolongados podem ser classificados como ruído. Essa ambiguidade continua sendo uma limitação.

## Regressões

69 verificações DSP/editor, incluindo salto de ruído+20 dB e evento difuso de fala de120 ms em44,1/48/96 kHz. Após1 s do salto, reduções23,93/24,40/24,36 dB. O evento curto teve perdas0,00436/0,00371/0,00408 dB. Os testes anteriores de harmônicos, resíduo tonal fraco, High End Cut, latência, dry/bypass/Mix, silêncio, estado e interface permanecem.

Dois novos testes de medição verificam nível/faixa do hiss adicionado, preservação do arquivo original e rejeição de entrada curta. Total11 testes de ferramentas.

## Referência A/B licenciada — 48 kHz

Mesmos16 estímulos por ajuste Auto−12/−26, Bias0, High End Cut0, Mix100%, delay medido por arquivo. Referências licenciadas anteriores reutilizadas; sem alteração do CEDAR ou do iLok.

| Caso | CEDAR | Open0.4 | Open0.5 |
|---|---:|---:|---:|
| Degrau−65→−45, ajuste−26, queda RMS3–12 s | 20,465 dB | 7,752 dB | 12,387 dB |
| Degrau−65→−45, ajuste−12, queda RMS3–12 s | 11,181 dB | 6,404 dB | 9,301 dB |
| Hiss−65, ajuste−26 | 25,574 dB | 23,267 dB | 23,267 dB |
| Tom1,4 kHz+hiss, ajuste−26, queda RMS total | 0,090 dB | 0,001 dB | 0,001 dB |

Na janela6,00–6,25 s após o salto em6 s, CEDAR reduz11,54 dB e Open0,03 dB. Em6,50–6,75 s:25,59 contra22,85 dB. Em6,75–7,00 s:25,58 contra25,30 dB. O vazamento inicial ainda domina a métrica RMS agregada. Não confundir a redução após acomodação com resposta imediata.

37 de54 verificações parciais de diferença RMS≤0,5 dB passam (25/27 em−12 e12/27 em−26). Isso é contagem de verificações desse critério, NÃO percentual de equivalência perceptiva. Impulso, silêncio e canal sem entrada não entram nessa contagem.

## Voz real

Ferramenta voice_injection.py adiciona hiss conhecido de800–6000 Hz a uma gravação, processa entrada original e entrada com hiss separadamente e compara as saídas. A diferença inclui mudanças não lineares na voz: NÃO é ruído residual isolado, SNR absoluto ou prova de qualidade. A gravação pessoal e seus resultados ficam locais.

Testes com voz mostram alterações maiores ao subir Bias. Deve-se avaliar o áudio removido e a voz processada; pequena queda RMS não garante naturalidade. Uma repetição da referência na gravação pessoal também apresentou diferença não nula; não se usa esse ensaio para dar uma nota percentual de qualidade.

## Build

Windowsx64/MSVC/JUCE8.0.15. Latência inalterada:4096 amostras a48 kHz (85,3 ms),8192 a96 kHz. Presets e IDs dos parâmetros mantidos. Instâncias carregadas no FLStudio não são substituídas durante uso. Arquivos da versão anterior são preservados.

SHA256 DLL0.5: FD8504273F69E2F7EA809932800EB0D3E60A0AAF563207D092957BBF887192E4.
