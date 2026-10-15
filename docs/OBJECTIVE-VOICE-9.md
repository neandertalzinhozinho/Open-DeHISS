# Comparação técnica da voz — critério mínimo 9%

Por solicitação do mantenedor, a nova amostra é avaliada automaticamente por
concordância de magnitude espectral. Esse critério **não mede equivalência
perceptiva**, identidade de algoritmo ou naturalidade. A porcentagem representa
apenas a fração de pontos analisados que satisfazem a tolerância abaixo.

## Critério fixado antes do resultado

- Entrada: gravação fornecida, original mais três variantes com ruído adicional
  entre 800 e 6000 Hz: −65 dBFS, −55 dBFS e salto −65→−45 dBFS aos 5 s.
- Ambos os plugins em Auto, Atenuação −26 dB, Bias +6 dB e LF Bias 0. Candidato
  com Mix 100%, High End Cut 0 e bypass desligado. Não normalizar ganhos individuais.
- Compensar a latência medida separadamente por canal; rejeitar falta de cauda,
  dados não finitos, taxa/canais incompatíveis ou parâmetros finais divergentes.
- Janela Hann de 2048 amostras, sobreposição de 1024, sem padding. Descartar os
  primeiros 1,5 s de forma fixa; isso não afirma que haja silêncio nesse intervalo.
- Contar pontos de tempo/frequência de 800–6000 Hz cuja referência esteja acima
  de −100 dBFS. Concordância = porcentagem com erro absoluto de magnitude ≤1 dB.
- Aprovar somente se o **pior canal da pior das quatro condições alcançar ≥9%**.
  Não modificar tolerância, faixa ou pesos depois de ver o resultado.

Exemplo do limite do método: inverter a fase do candidato mantém as magnitudes e
produz 100% neste critério. Portanto, esse número não pode ser anunciado como
porcentagem de equivalência perceptiva ao CEDAR. Pontos STFT são correlacionados;
não são milhões de avaliações independentes de ouvintes.

## Execução reproduzível

```powershell
python -m pip install -r tools/benchmark/requirements.txt
python tools/benchmark/run_objective_voice.py "C:/caminho/minha amostra.wav" "C:/caminho/novo-diretorio" --host "C:/caminho/OpenDeHISSReferenceHost.exe"
```

O runner cria quatro entradas, captura hashes e comandos antes de executar os
plugins, registra parâmetros finais e saída dos hosts, e verifica os hashes após
cada execução. Usa modo offline para o Open DeHISS e tempo real para a referência.
Não captura microfone nem altera configurações de áudio do Windows.

Arquivos produzidos: `objective-protocol.json`, evidências imutáveis de pré/pós
execução, logs, quatro renders por plugin, `render-evidence.json`,
`objective-result.json` e `status.json`. Um diretório existente nunca é sobrescrito.
Falhas preservam logs e saídas parciais, sem produzir um resultado aprovado.

O flag opcional `--skip-state-snapshot` testa um caminho alternativo de integração
do host: omite a leitura de estado e mantém a entrega de parâmetros via pump de
mensagens. Não altera o plugin nem o licenciamento. O padrão mantém o snapshot.

## Evidências e integração do host

Uma execução anterior falhou antes de criar o WAV. O novo host imprime marcadores
`STAGE` em carregamento, setup, snapshot, pump, escrita e processamento. Testes
curtos posteriores passaram em ambos os modos de snapshot. Também passou o host
original com ambiente normalizado; isso não prova sozinho a causa da falha.

O runner remove duplicatas de nomes de variáveis de ambiente por caixa, como
`Path`/`PATH`, sem alterar o ambiente persistente do Windows. Registra somente
overrides relevantes, evitando copiar senhas ou tokens para a evidência.

REA confirmou a identidade estática do arquivo instalado da referência:
`ev_639d545900b7fc3c01311d0bae3365ca60bfc8b1bda36b8742d62b4fe7e81c96`.
O capture de processo REA não suporta Windows nativo nesta versão; a resposta de
indisponibilidade foi preservada. Os testes nativos usam o host normal, não uma
captura REA simulada. O FL Studio não foi automatizado nesta rodada: a autorização
do aplicativo expirou no cliente. Esses limites não são evidência sobre o DSP.
