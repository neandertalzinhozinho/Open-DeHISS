# Validação local — 11/10/2026

Versão 0.2.0, Windows x64 Release, MSVC 19.44, JUCE 8.0.15.

CTest: DSP e editor aprovados, incluindo as verificações herdadas do beta e as novas verificações de controles gráficos. Atenuação visual padrão 0 dB; ajuste do knob para −26 dB atualiza o parâmetro DSP. Modo manual mapeia o knob Bias para Threshold, inicialmente −65 dBFS. Renderizações em 0 e −26 dB inspecionadas visualmente.

Host isolado carregou o VST3 compilado: Open DeHISS. Confirmou atenuação padrão 0 dB e, após ajuste −12 dB, mediu redução automática de 5,44806 dB no estímulo de ruído estacionário. Saída finita, sem vazamento entre canais, bypass com erro absoluto zero após alinhamento da latência.

SHA256 do binário local: `D13566F609267DB0C9F09D6E5A5062E27C958FE247F387573AD8B02F4E343DA8`.

Não se afirma equivalência ao CEDAR nem validação perceptiva completa da voz. O teste de GUI verifica renderização e vinculação dos controles; uso e escalonamento na DAW ainda precisam de avaliação.
