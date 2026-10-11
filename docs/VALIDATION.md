# Validação local — 11/10/2026

Versão 0.2.0, Windows x64 Release, MSVC 19.44, JUCE 8.0.15.

CTest: DSP e editor aprovados, incluindo as verificações herdadas do beta e as novas verificações de controles gráficos. Atenuação visual padrão 0 dB; ajuste do knob para −26 dB atualiza o parâmetro DSP. Modo manual mapeia o knob Bias para Threshold, inicialmente −65 dBFS. Renderizações em 0 e −26 dB inspecionadas visualmente.

Host isolado carregou o VST3 compilado: Open DeHISS. Confirmou atenuação padrão 0 dB e, após ajuste −12 dB, mediu redução automática de 5,44806 dB no estímulo de ruído estacionário. Saída finita, sem vazamento entre canais, bypass com erro absoluto zero após alinhamento da latência.

SHA256 do binário local: `D13566F609267DB0C9F09D6E5A5062E27C958FE247F387573AD8B02F4E343DA8`.

Não se afirma equivalência ao CEDAR nem validação perceptiva completa da voz. O teste de GUI verifica renderização e vinculação dos controles; uso e escalonamento na DAW ainda precisam de avaliação.

## High End Cut — 0.3.0

Controle independente 0…−40 dB, dedicado ao dehiss acima de 15 kHz, transição até 15,5 kHz. Todos os testes anteriores e os novos testes passaram. Com Atenuação geral=0 e High End Cut=−24, tons de 18/21 kHz classificados como ruído foram reduzidos em aproximadamente24 dB em44,1/48/96 kHz; alteração nos tons1/14 kHz menor0,001 dB. Teste no VST3 real, 48 kHz: perda na faixa baixa−0,000424737 dB; redução em18 kHz24,001 dB. Presets/GUI/default0/Nyquist≤15kvalidados. Preview550×426inspecionado.

SHA256 binário0.3.0: `707360CB0A63B2B1BEF078EDB9080DF72B716A27B60C96FFD6587BC521C3B88A`. Supressão adaptativa; não se promete apagar componentes acima de15 kHz classificados como sinal. Instalado após usuáriofecharFLStudio; versãoanteriorpreservada.
