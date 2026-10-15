# Diagnóstico do efeito de processamento

Este diagnóstico compara **o que cada plugin modificou na mesma entrada**. Ele
complementa a medição anterior de magnitudes, na qual o áudio seco podia receber
uma nota alta por preservar a voz dominante. Não cria uma porcentagem de
equivalência, não muda o critério técnico anterior de 9/100 e não estabelece
equivalência perceptiva.

## Definição

Depois da compensação da latência inteira, sejam `X` a entrada, `R` a saída do
CEDAR e `C` a saída do Open DeHISS. Para cada canal, janela temporal e banda:

```text
efeito_referencia = STFT(X) - STFT(R)
efeito_candidato  = STFT(X) - STFT(C)
erro_normalizado = energia(efeito_candidato - efeito_referencia)
                  / energia(efeito_referencia)
```

As STFTs são **complexas**: a fase permanece na diferença. Não se ajusta o ganho
de nenhum arquivo. A divisão pela energia do efeito apenas define a unidade do
erro; não modifica o áudio.

- **0:** efeito numericamente idêntico à referência.
- **1:** erro do controle seco, que não processa nada.
- **Acima de 1:** erro maior que o do controle seco naquela análise.

Esses valores são razões de energia, e não porcentagens. Não há valor de
aprovação nem conversão automática para nota perceptiva. Uma redução uniforme
de volume pode imitar certos efeitos da referência sem separar voz e ruído.

## Seleção e análise

O script `tools/benchmark/score_processing_effect.py` mantém a exclusão inicial
de 1,5 s do protocolo anterior. Usa janelas consecutivas de 1 s, incluindo a
última janela parcial se contiver pelo menos 2048 amostras. Em cada uma:

- STFT Hann de 2048 amostras, avanço de 1024, extensão por zeros nas duas bordas
  e preenchimento até o último quadro, para cobrir também as caudas das janelas;
- integração da densidade espectral de potência unilateral com pesos corretos
  para representar energia, usando a parte complexa para os resíduos;
- bandas `[80,800)`, `[800,2000)`, `[2000,6000)`, `[800,6000)`,
  `[6000,15000)` e `[15000,24000)` Hz, limitadas à frequência de Nyquist;
- referência materialmente ativa somente quando a entrada da banda supera
  −80 dBFS e a potência do efeito da referência equivale a pelo menos −20 dB da
  potência da entrada, isto é, ao menos 10% de mudança em amplitude RMS.

Esses limiares identificam mudança mensurável na referência, não presença de
ruído. Uma inversão de fase satisfaz a condição de mudança, apesar de não
reduzir o nível. O relatório registra separadamente quantas janelas tiveram
redução de pelo menos 1 dB. Referência inativa produz resultado **inconclusivo**,
sem atribuir mérito ao bypass. O limiar de entrada evita dividir pelo efeito de
uma referência praticamente silenciosa.

A razão agregada de cada banda e canal é ponderada pela energia do efeito da
referência e pela duração da janela. A mediana e o percentil 95 por janela
também são preservados, para evidenciar comportamentos que o agregado pode
ocultar. As bandas `[800,2000)` e `[2000,6000)` são subdivisões de `[800,6000)`;
não se devem somar todas as bandas em um resultado global. Canais permanecem
separados. O piso de apresentação das potências em dB é −300 dB.

Outros campos registram a redução RMS da referência e do candidato, a diferença
de nível entre as saídas, a energia dos efeitos e do erro, e a projeção do efeito
do candidato sobre o da referência. A projeção é 0 para o controle seco e 1
quando os efeitos são iguais; também não é uma porcentagem de equivalência.

## Procedência e execução

Antes de avaliar os resíduos, o script executa toda a validação existente em
`score_objective_voice.evaluate`: hashes da fonte, das quatro condições de
entrada, dos plugins, do host, dos logs e dos renders; parâmetros finais;
contagem de frames e amostras finitas; compensação de latência medida contra
o log. Portanto, ele pode falhar se um binário instalado tiver mudado desde a
captura. Não substitui automaticamente arquivos ou renders históricos.

Na pasta do repositório, com o ambiente Python do projeto:

```powershell
& ../bench-venv/Scripts/python.exe tools/benchmark/score_processing_effect.py `
  ../../outputs/nean-final-objective09-verified `
  ../../outputs/processing-effect-20261014/verified-run.json

& ../bench-venv/Scripts/python.exe -m unittest discover `
  -s tools/benchmark -p test_processing_effect.py -v
```

O destino deve ser novo. O relatório é JSON com todas as janelas e um resumo
por condição, banda e canal. Não contém o áudio privado. A execução lê renders
já auditados: não altera o plugin, não toca no licenciamento e não grava entrada
de microfone.

## Limitações e testes

A gravação real não possui uma versão de voz limpa conhecida. O sinal removido
pode incluir ruído, harmônicos de voz, diferenças de fase, transientes e
artefatos. A análise não os separa. A proximidade ao processamento do CEDAR
não demonstra naturalidade, inteligibilidade ou identidade de algoritmo.

As quatro condições usam a mesma gravação. Janelas e canais não são ensaios
estatísticos independentes; o relatório não calcula uma confiança artificial
com base no número de células espectrais. A compensação usa latência inteira;
diferenças fracionárias e resposta de fase permanecem no erro. Os resultados
dependem dos parâmetros, limiares, arquivo e estado dos plugins documentados.

A revisão 2 exige igualdade exata entre atraso inteiro medido e declarado;
uma discordância de uma amostra é rejeitada. A extensão por zeros é comum aos
três sinais e influencia as estimativas de potência perto das bordas de cada
janela. Resultados anteriores à revisão 2 devem ser recalculados: a versão
inicial descartava pequenas caudas a cada segundo. Não comparar números das
duas revisões como se usassem o mesmo suporte temporal.

Os testes sintéticos verificam identidade, bypass, referência inativa, piso de
energia, inversão de fase, diferença de ganho, separação de canais, exclusão de
janelas sem efeito, janelas parciais, rejeição de dados inválidos, JSON finito,
latência correta/incorreta, ausência da cauda e auditoria obrigatória de
procedência. Os controles sintéticos não são apresentados como resultados da
voz do usuário.
