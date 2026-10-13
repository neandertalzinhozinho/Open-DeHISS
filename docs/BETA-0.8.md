# Open DeHISS beta 0.8

Esta versão reduz de 50 para 40 ms a persistência exigida para reconhecer uma subida ampla do piso de ruído. O detector continua exigindo vários quadros consecutivos e mantém o estimador recente por 21 quadros. O caminho de áudio e a antecipação não mudaram: a latência declarada permanece em 4608 amostras a 48 kHz (96 ms) e fica em até 96 ms nas taxas testadas.

## Evidência funcional

A matriz licenciada local comparou 28 casos ativos em Auto, com atenuações de -12 e -26 dB. Vinte e sete casos ficaram dentro de 0,5 dB da redução RMS do CEDAR (96,43%, meta do projeto: pelo menos 80%). O único caso fora da tolerância foi a redução agregada da transição de ruído em -26 dB, com diferença de 1,35 dB.

Na análise temporal da mesma transição, o erro absoluto médio em oito janelas de 250 ms caiu de 0,225 para 0,100 dB em -12 dB e de 0,783 para 0,568 dB em -26 dB. O maior erro caiu de 1,36 para 0,37 dB e de 2,59 para 0,98 dB, respectivamente. A melhora temporal não elimina a falha agregada e não é uma porcentagem de qualidade perceptiva.

Três eventos sintéticos processados pelo VST3 mantiveram perda adicional menor que 0,5 dB frente à referência: fricativa de 120 ms, ataque de banda larga de 20 ms e evento barítono de 250 ms. Seis testes de ruído entre harmônicos barítonos passaram. A gravação particular do usuário foi processada em quatro condições com saída finita e atraso de 4608 amostras; a diferença de saídas inclui mudanças não lineares na voz e não mede inteligibilidade ou naturalidade.

## Limites

Os resultados comprovam os critérios automatizados descritos, não equivalência integral do algoritmo nem equivalência perceptiva. As constantes recuperadas estaticamente de 3000 Hz e 250 ms foram testadas e rejeitadas porque pioraram a transição agregada. Uma ativação suave mais rápida também foi rejeitada por exceder o limite de preservação do ataque de 20 ms.
