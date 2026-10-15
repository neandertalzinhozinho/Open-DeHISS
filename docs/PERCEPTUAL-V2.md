# Avaliação perceptiva pessoal v2 — meta 9/100

Este protocolo mede um **índice de similaridade** relativo ao CEDAR, à âncora,
ao ouvinte, aos parâmetros e ao material do estudo. Não mede porcentagem de
algoritmo recuperado, não comprova equivalência geral e não transforma RMS em
opinião humana. Não há resultado perceptivo até o ouvinte exportar suas notas.

## Protocolo fixado antes da escuta

- Beta 0.9 como candidata inicial; Auto ligado, Atenuação −26 dB, Bias +6 dB,
  LF Bias 0, Mix 100%, High End Cut 0. Referência com parâmetros correspondentes.
- 12 trechos novos, distintos, não sobrepostos, de pelo menos 3 segundos. Material
  usado no ajuste não pode ser reutilizado como avaliação. Quatro condições:
  ruído original, hiss adicional −65 e −55 dBFS, e ruído variável.
- Duas sessões aleatorizadas, com pausa deliberada, no mesmo fone e volume:
  12 trechos × 3 papéis × 2 sessões = 72 comparações A/B. A é a referência;
  B pode ser candidata, referência oculta ou entrada sem redução.
- Ouvir A e B inteiros e fornecer nota explícita de 0 a 100. O programa registra
  os eventos de reprodução; esses eventos não comprovam atenção humana.
- Índice bruto: `100*(medianaCandidata-medianaÂncora)/(medianaReferência-medianaÂncora)`.
  Só a exibição é limitada a 0–100; o bruto permanece no relatório.
- Bootstrap pareado por trecho: todas as sessões e papéis de um trecho permanecem
  juntos em cada reamostragem. SciPy, percentil, 9.999 reamostragens, seed 20261013,
  limite inferior unilateral de 95%. O método supõe permutabilidade dos trechos;
  as variantes da mesma gravação não são ouvintes ou gravações independentes.
- Aprovar somente com **limite inferior ≥9**, referência oculta com mediana ≥90
  e separação referência–âncora ≥20 em **cada** sessão. Denominadores inválidos,
  material insuficiente ou controles inválidos deixam o resultado inconclusivo.

O bootstrap usa a [implementação SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).
Este é um protocolo pessoal exploratório, não uma certificação de equivalência.

## Estado em 13/10/2026

A cópia disponível da voz tem 10,2644 segundos e já foi usada no ajuste. O arquivo
original no antigo caminho Music não foi encontrado; a cópia float preservada em
`outputs/nean-voice-injection-0.5/inputs/original.wav` foi conferida e utilizada.
Repetir essa gravação ou adicionar vários ruídos não cria 12 trechos independentes.

Foram refeitos quatro renders de cada plugin instalado pelo host VST3, em tempo
real, sem captura de microfone. Ambos concluíram `PASS renders=4`. O atraso medido
nos dois canais foi 4.608 amostras no Open DeHISS e 16.128 no CEDAR, a 48 kHz.
Os áudios de escuta compensam esses atrasos; não recebem normalização individual.
O ganho comum do piloto é 1,0. Cópias de escuta em PCM24; renders float preservados.

O piloto tem quatro condições do mesmo intervalo 1,5–9,5 s, duas sessões e **24
comparações**, marcado explicitamente como insuficiente para aprovação da meta.
Nenhuma nota humana foi criada. Dados antigos v1 só podem produzir descrição,
sem aprovação da meta nova.

## Uso

Abra `outputs/blind-beta09-v2-pilot/index.html` diretamente no navegador mantendo
a pasta `audio` ao lado. O piloto é opcional, para conhecer o procedimento. Não
abra `private/key.json` antes da escuta, pois contém a ordem dos papéis.

Para a avaliação válida, forneça uma **nova gravação WAV de 60–90 segundos**, sem
dehiss, gate ou compressor: comece com 3 segundos de ruído sem falar, depois fale
naturalmente, incluindo sons s/f/ch e frases graves. Mantenha microfone, ganho e
distância estáveis. Preserve a gravação como avaliação; não a use para afinar o
algoritmo antes de testar a candidata fixada.

O gerador genérico aceita um JSON com `studyId`, `provenance` e `excerpts`; cada
trecho contém `id`, `sourceId`, `startSeconds`, `endSeconds`, `condition`, `split`
(`evaluation` ou `pilot`) e caminhos absolutos WAV `reference`, `candidate`,
`anchor`, já alinhados, com mesmas taxas, canais e durações. Ele recusa sobrescrita.

Comandos a partir do repositório OpenDeHISS:

```powershell
python -m pip install -r tools/benchmark/requirements.txt
python tools/benchmark/build_blind_study.py --spec C:/caminho/study-spec.json --output C:/caminho/novo-estudo
python tools/benchmark/score_blind_similarity.py C:/caminho/novo-estudo/private/key.json C:/caminho/blind-scores-complete.json C:/caminho/resultado-novo.json
python -m unittest discover -s tools/benchmark -p "test_*.py" -v
```

O scorer retorna 0 apenas quando a meta foi demonstrada neste protocolo; 1 para
resultado não aprovado/inconclusivo; 2 para arquivo inválido ou saída já existente.
Ele valida notas finitas, identidade do estudo, hash de manifesto, sessões,
completude, papéis, sobreposição, evidência de reprodução e timestamps.

Dados pessoais, áudios e chaves ficam fora do repositório. Os testes automatizados
usam notas sintéticas apenas em diretórios temporários e não são resultados humanos.
