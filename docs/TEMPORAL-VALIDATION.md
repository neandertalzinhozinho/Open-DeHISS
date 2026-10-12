# Validação da resposta temporal

A média RMS de um arquivo pode ocultar erros locais que se compensam. Registre a matriz RMS existente e a resposta temporal separadamente; nenhuma delas representa uma porcentagem de qualidade perceptiva.

Com um relatório produzido por `compare_renders.py`, execute:

```powershell
python tools/benchmark/audit_noise_step.py comparison.json temporal.json --transition 6
```

O auditor examina os dois segundos após a transição, em janelas de 250 ms já alinhadas pelo comparador. A diferença é a redução do candidato menos a redução da referência. Valores negativos indicam menor supressão. A tolerância diagnóstica é 0,5 dB por janela. Não substitui o critério agregado nem altera suas aprovações.

Ao comparar versões, publique também o erro absoluto médio e máximo das janelas, os casos que falharam e os testes de preservação de eventos curtos. Não aprove uma mudança somente porque melhorou uma métrica. A resposta antes da transição deve ser examinada quando os algoritmos usam antecipação diferente.

Os testes unitários do auditor verificam seleção temporal, sinal da diferença, inclusão da fronteira da tolerância e rejeição de medições ausentes. Eles rodam na CI sem o plugin proprietário. A comparação real com CEDAR exige os renders licenciados locais; esses arquivos não são publicados.
