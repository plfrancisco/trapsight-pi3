# PROPOSTA INDIVIDUAL DE SOLUÇÃO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** respostas ao formulário acadêmico de proposta individual

---

# 1. Contexto do documento

Respostas ao formulário "Proposta Individual de Solução" — Projeto Integrador
de Sistemas Inteligentes III, Fatec "Shunji Nishimura" de Pompeia.

Baseado no projeto de visão computacional para armadilhas adesivas descrito em
`project_overview.md`.

---

# 2. Problema a ser solucionado

Empresas que distribuem armadilhas adesivas de mosquito para mercados,
açougues e estabelecimentos similares dependem de inspeção manual periódica
para saber quando cada armadilha está saturada e precisa de troca. Esse
processo é impreciso: a troca pode ocorrer cedo demais, gerando desperdício de
material e visitas desnecessárias, ou tarde demais, fazendo a armadilha perder
eficácia e comprometer o controle de pragas no estabelecimento. Não há hoje um
critério objetivo e automatizado para determinar o momento certo da troca.

---

# 3. Proposta de solução

Desenvolvimento de um sistema de visão computacional que analisa imagens
capturadas por uma câmera fixa acoplada à armadilha adesiva e estima
automaticamente o nível de saturação da superfície, medindo o percentual de
área coberta por insetos. Quando esse percentual ultrapassa um limiar
definido, o sistema indica que a armadilha está pronta para troca. O fluxo
principal é: captura da imagem, segmentação da área coberta, cálculo do
percentual e classificação do status.

---

# 4. Valor para o usuário

A solução elimina a dependência de inspeção visual humana periódica, reduzindo
desperdício de armadilhas trocadas antes da hora e evitando períodos em que a
armadilha fica saturada e ineficaz sem que ninguém perceba. Para a empresa
distribuidora, isso pode se tornar um diferencial de serviço, permitindo saber
exatamente quais clientes precisam de visita de troca. Para o estabelecimento,
garante controle de pragas mais consistente sem esforço manual de
monitoramento.

---

# 5. Reação esperada do contexto

A resistência esperada é baixa, já que a solução é majoritariamente automática
e não exige mudança de rotina do estabelecimento — a câmera opera de forma
passiva, sem necessidade de interação do usuário no dia a dia. O maior ponto
de atenção é a aceitação da empresa distribuidora quanto à instalação de um
dispositivo de câmera na armadilha, o que exigirá comunicação clara sobre o
propósito: monitoramento da armadilha, não vigilância do ambiente.

---

# 6. Viabilidade e pontos fortes

O projeto tem viabilidade técnica adequada ao escopo de um MVP acadêmico. A
tarefa central é um problema de segmentação de imagem — separar pixels de área
coberta por insetos da superfície limpa — abordável com modelos de segmentação
treinados, como a arquitetura U-Net, e técnicas de transfer learning, o que
reduz a necessidade de um dataset grande. O critério de saturação é objetivo e
mensurável (percentual de área coberta), o que facilita a validação.

---

# 7. Obstáculos e pontos fracos

O principal obstáculo é a obtenção de um dataset de imagens de armadilhas
adesivas com anotação suficiente para treinar o modelo, já que não existe uma
base pública pronta para esse cenário específico — isso pode exigir captura e
rotulagem manual de imagens. Outro risco é a variação de condições reais de
captura, como iluminação, ângulo e sujeira na lente da câmera, afetar a
precisão da segmentação. Também é necessário calibrar o limiar de percentual
que define o momento da troca, o que idealmente requer validação com dados
reais de uso.

---

# 8. Escopo mínimo sugerido

O MVP consistirá em um modelo de visão computacional treinado que recebe uma
imagem de uma armadilha adesiva e retorna o percentual estimado de área
coberta por insetos, classificando o status como "ok", "atenção" ou "trocar"
com base em um limiar definido. Não há integração com hardware real de câmera
em campo nem painel completo para usuários finais nesta fase — o foco é
validar a viabilidade técnica do modelo com um conjunto de imagens de teste.

---

# 9. Evidência de sucesso

O critério de sucesso do MVP é a estimativa do percentual de área coberta com
erro absoluto de até 5 pontos percentuais em um conjunto de fotos reais com
gabarito conhecido, nunca utilizado no treinamento, com acurácia de
classificação do status igual ou superior a 90%.

A margem de 5 pontos não é arbitrária: decorre da projeção de quando a
armadilha saturará, que é calculada a partir da variação entre medições
sucessivas. Um erro maior tornaria essa estimativa instável a ponto de perder
utilidade prática.

Constitui reprovação, independentemente das demais métricas, qualquer caso em
que uma armadilha saturada seja classificada como em condição normal — o erro
na direção que compromete o controle de pragas.

---

# FIM DA PROPOSTA INDIVIDUAL
