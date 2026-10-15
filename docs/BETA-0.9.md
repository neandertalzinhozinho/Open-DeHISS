# Open DeHISS beta 0.9

Esta versão aprofunda a supressão **apenas na banda alta e apenas em atenuação funda**, onde a
medição contra a referência licenciada mostrava déficit. A lei de mistura do ganho passou a
usar interpolação em domínio do log (`piso^(1−q)`) **somente** quando a frequência é maior ou
igual a 8 kHz **e** a atenuação pedida passa de 12 dB, com rampa progressiva até −26 dB. Fora
desse intervalo o processamento retorna a lei afine anterior, sem alteração.

O caminho de áudio não mudou: latência declarada de 4608 amostras a 48 kHz (96 ms), até 96 ms
nas 12 taxas testadas, `High End Cut`, `Bypass` e `Mix` com o mesmo comportamento.

## Por que só essa faixa

Medição das 32 casos próprios contra as referências golden da beta 0.8:

- Em `auto--26`, os sete casos de ruído largo estacionário suprimiam **0,306 a 0,309 dB menos**
  que a referência, e o desvio estava todo acima de 8 kHz (banda 15–24 kHz: +0,70 dB de saída
  a mais; 12–15 kHz: +0,22; abaixo de 8 kHz: 0,00).
- Em `auto--12` a mesma banda alta já suprimia **mais** que a referência (−0,10 a −0,19 dB).
  Ou seja: o erro crescia com a profundidade, e a referência mantinha resíduo quase constante
  (~0,45 dB acima do pedido) nas duas atenuações.

Duas formulações mais amplas foram medidas e **rejeitadas** antes desta:

1. Achatar a prateleira de topo acima de 8 kHz em qualquer atenuação: melhorou −26 dB
   (−0,308 → −0,144) mas piorou −12 dB (+0,113 → +0,278); soma dos desvios absolutos dos 28
   casos subiu de 5,677 para 5,912 dB.
2. Interpolação log-domain global: fechou o déficit de −26 dB (−0,308 → −0,044) porém
   rebaixou o guarda de barítono de 6,635/6,950/7,254 para 5,614/5,734/5,890 dB, abaixo do piso
   de 25% da atenuação. O controle com o binário anterior reproduziu a baseline dígito por
   dígito, então a regressão era real. A checagem de consistência mostrou o mecanismo: o RMS
   total do sinal mudou só 0,004 dB, mas a energia **entre** as parciais subiu 1,02 a 1,36 dB —
   a curva foi redistribuída, não aprofundada, porque ela passa pela janela de impulso circular
   e pelo crossfade antigo/novo da síntese.

A restrição por frequência e profundidade existe para não repetir esses dois erros.

## Evidência funcional

Comparação das 32 casos próprias (16 estímulos × `auto--12` e `auto--26`) com as referências
licenciadas já gravadas, sem alterar critério nem tolerância:

| portão | beta 0.8 | beta 0.9 |
|---|---|---|
| ruído estacionário em `auto--26` (7 casos) | −0,306 a −0,309 dB | **−0,042 a −0,045 dB** |
| banda 15–24 kHz em `auto--26` | +0,70 dB | **+0,11 dB** |
| soma dos desvios absolutos em `auto--26` | 4,231 dB | **3,028 dB** |
| casos `auto--12` (14) | — | **14/14 inalterados, bit a bit** |
| 6 tons sustentados | — | **Δ 0,000 dB** |
| ruído entre harmônicos de barítono (Bias 6) | 6,635 / 6,950 / 7,254 dB | **6,635 / 6,950 / 7,254 dB (exatos)** |
| transientes (perda adicional vs referência) | fricativa −0,5481, banda larga +0,1665, barítono −2,2304 | fricativa −0,5481, banda larga **+0,2057**, barítono −2,2304 |
| critério RMS de 0,5 dB | 27/28 casos | **27/28 casos** |
| critério por canal | 52 aprovados, 2 reprovados | 52 aprovados, 2 reprovados |
| `ctest` | 3/3 | 3/3 |
| suítes de medição em Python | 35/35 | 35/35 |

A invariância sob a faixa fechada foi verificada **antes** de compilar, comparando o módulo do
protótipo contra a versão extraída do próprio commit anterior: 1008 pontos, zero diferenças,
pior diferença 0,000e+00.

## O que piorou, registrado

O caso de salto de ruído em `auto--26` subiu de +1,352 para **+1,997 dB** de diferença
agregada e continua sendo o único reprovado. A causa já está diagnosticada: a referência
libera a supressão nos últimos 250 ms do render (redução de 25,58 para 10,68 dB nessa janela,
que concentra 38,8% da energia da janela de medida agregada), e esta versão suprimindo mais
fundo em regime aumenta a distância nesse número. É consequência de um efeito de borda do
render de referência, não de comportamento em regime, e por isso a tolerância e a janela
oficiais continuam as mesmas, com o caso reprovado à vista.

## Limites

Os resultados comprovam os critérios automatizados descritos. Eles **não** demonstram
equivalência com nenhum produto comercial, nem equivalência perceptiva, nem recuperação de
algoritmo. A perda adicional em transientes e a redução entre harmônicos são medidas de
estabilidade, não de naturalidade. A comparação às cegas com participação humana continua a
única medição de similaridade percebida, e nenhuma nota dela foi preenchida por este
trabalho. A escala de atenuação manual própria não é semanticamente equivalente à da
referência por usar o mesmo número.
