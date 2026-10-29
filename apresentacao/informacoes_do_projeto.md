# TrapSight — Informações do projeto para o vídeo de apresentação

Atualizado em 29/10/2026. Texto sem termos técnicos, para servir de base ao roteiro do vídeo. Este arquivo não é o roteiro.

## O projeto em uma frase

O TrapSight olha a foto de uma armadilha adesiva e diz quanto da superfície já está tomado por insetos e quando é a hora de trocar o refil.

Hoje essa decisão é tomada no olho, por visitas periódicas. O sistema troca o "acho que já está cheia" por uma medida objetiva: a porcentagem da área coberta por insetos, um aviso de situação (ok, atenção ou trocar) e uma estimativa de quantos dias faltam para a armadilha saturar.

É um projeto de validação técnica: prova que a ideia funciona com uma aplicação web de demonstração, sem depender de uma câmera instalada em campo.

## O problema

Saber a hora certa de trocar o refil de uma armadilha adesiva de mosquito ainda depende de olhar e de visitas periódicas, e errar o momento custa dinheiro nos dois sentidos.

Armadilhas adesivas ficam em mercados, açougues e estabelecimentos parecidos. A empresa que as vende ou mantém precisa decidir quando cada uma está cheia demais.

- **Troca cedo demais:** a equipe técnica se desloca sem necessidade e o refil é jogado fora ainda com vida útil.
- **Troca tarde demais:** a armadilha saturada perde a eficácia e deixa de proteger o local.

O problema foi confirmado em conversas com um gerente da empresa parceira, que faz parte da própria equipe do projeto. Os valores exatos (custo de cada deslocamento, preço do refil, quantas trocas antecipadas por mês) **ainda não foram levantados**, então o impacto financeiro é qualitativo, não um número.

## Para quem é

O TrapSight serve a quem precisa decidir quando trocar armadilhas adesivas: as empresas que as vendem e mantêm, e os donos dos locais onde elas ficam.

- **Empresas de controle de pragas e fabricantes de armadilhas:** veem quais armadilhas precisam de visita e planejam a rota da equipe, em vez de visitar todas.
- **Donos de mercados, açougues e similares:** acompanham as próprias armadilhas e sabem quando pedir a troca.

O projeto não escolheu ainda entre os dois modelos de uso, a versão para a empresa, a versão para o dono do local, ou as duas com painéis diferentes. Nesta etapa o foco é provar que a medição funciona.

O sistema de demonstração tem login: as contas são criadas por um administrador (gerente), não há cadastro aberto, e existem dois papéis, o gerente, que cria as contas, e o operador, que usa o sistema.

## Como funciona

Da foto ao aviso de troca, o caminho tem sete passos.

1. **A foto.** Alguém fotografa a placa adesiva da armadilha (o refil de 450 × 220 mm) e envia a imagem pelo sistema.
2. **O reconhecimento.** Um programa de inteligência artificial acha a placa na imagem e a divide em três partes: o que é fundo, o que é placa limpa e o que é placa coberta por insetos. Sujeira e poeira não contam como cobertura.
3. **A medida.** O sistema calcula que parte da placa está coberta. O cálculo é sobre a placa, não sobre a foto inteira, então não muda se a foto foi tirada mais perto ou mais longe.
4. **O aviso.** O resultado vira uma de três situações: **ok** (menos de 10% coberta), **atenção** (de 10% a 20%) ou **trocar** (mais de 20%).
5. **O histórico.** Cada foto fica guardada no histórico daquela armadilha e daquele refil.
6. **A previsão.** Com as medições ao longo do tempo, o sistema estima quantos dias faltam até a armadilha saturar, para planejar a visita antes do problema.
7. **A troca.** Quando o refil é trocado, o ciclo recomeça e a duração de cada refil fica registrada.

Os limites de 10% e 20% são um ponto de partida baseado em dados públicos de armadilhas reais, e ainda precisam ser confirmados com a empresa parceira.

## O que o usuário vê

A aplicação web gira em torno de um painel inicial que já mostra o que precisa de atenção primeiro.

| Tela | O que mostra ou permite |
| --- | --- |
| Entrar | Login com e-mail e senha; no primeiro acesso de uma conta nova, a senha inicial precisa ser trocada |
| Painel inicial | Todas as armadilhas ordenadas por urgência, com a miniatura da última foto e um painel de alertas |
| Nova análise | Envio da foto, com a máscara colorida sobre a imagem, o percentual coberto e a situação (ok, atenção ou trocar) |
| Detalhe da armadilha | Gráfico de evolução da cobertura, histórico por refil e a previsão de dias até saturar |
| Timelapse (dentro do detalhe) | As fotos de um refil passando em sequência, sincronizadas com o gráfico |
| Cadastro de armadilha | Escolha do modelo em um catálogo do fabricante (o primeiro é o StickFly K-45), em vez de texto livre |
| Contas | Só para o gerente: cria contas de operador |

O sistema também registra a troca de refil e funciona no celular, com a navegação adaptada ao tamanho da tela.

## Como a inteligência artificial aprende

Para ensinar o programa a reconhecer insetos colados, a equipe montou o próprio conjunto de 3.000 imagens, porque não existe uma base pública pronta para esse cenário.

A ideia é simples: o programa aprende vendo muitos exemplos em que a resposta certa já é conhecida.

- **De onde vem a resposta certa:** de um conjunto público de 69 fotos reais de armadilhas de luz ultravioleta, com cerca de 24 mil insetos já marcados por pesquisadores.
- **Como as imagens foram montadas:** os insetos reais são recortados dessas fotos e colados em outras placas, reais ou simuladas no formato do refil StickFly K-45, com quantidades diferentes de cobertura. Como a equipe sabe onde cada inseto foi colocado, a resposta certa de cada imagem nasce junto com ela, sem precisar marcar tudo à mão.
- **Sujeira e poeira de propósito:** as imagens trazem sujeira que não conta como inseto, para o programa aprender a diferença.
- **Provas justas:** 14 das 69 placas reais ficaram guardadas só para a avaliação final, e nenhuma placa aparece ao mesmo tempo no treino e na verificação. Isso evita um resultado bonito por decorar as respostas.
- **Divisão das imagens:** 2.100 para treinar, 450 para ajustar e 450 para testar.

Algumas partes das fotos reais são difíceis de classificar até para uma pessoa. Essas partes foram marcadas como "ignorar", para não ensinar o programa nada errado.

Como ponto de comparação, a equipe também criou um método clássico bem simples, que só separa o escuro do claro. A pergunta que o projeto quer responder com números é onde a inteligência artificial supera esse método simples, principalmente com placa suja e refil velho.

## Tecnologias usadas

O projeto usa tecnologias abertas e populares, organizadas em quatro frentes: inteligência artificial, servidor, interface e infraestrutura.

| Frente | Tecnologia | Para que serve |
| --- | --- | --- |
| Inteligência artificial | Python | Linguagem em que o modelo e o gerador de imagens são escritos |
| Inteligência artificial | PyTorch e segmentation_models_pytorch | Treinam e executam a rede neural U-Net, com um codificador ResNet34 já pré-treinado |
| Inteligência artificial | OpenCV | Trata imagens e serve de método clássico de comparação |
| Inteligência artificial | Albumentations | Varia as imagens de treino (luz, giro, ruído) |
| Inteligência artificial | SAM (Segment Anything) | Recorta os insetos das fotos reais para montar as imagens |
| Servidor | FastAPI | Recebe a foto, roda a análise e entrega o resultado |
| Servidor | SQLAlchemy e Alembic | Conversam com o banco e controlam as mudanças da sua estrutura |
| Banco de dados | PostgreSQL | Guarda armadilhas, refis, análises, imagens e contas |
| Interface | React e TypeScript | Constroem as telas |
| Interface | Vite e Tailwind CSS | Preparam o site e cuidam do visual |
| Interface | Recharts | Desenha os gráficos de evolução |
| Infraestrutura | Docker e Docker Compose | Sobem o sistema todo com um comando, igual em qualquer computador |
| Infraestrutura | Caddy | Porta de entrada com HTTPS automático, no ambiente de testes de segurança |
| Infraestrutura | Vercel e Supabase | Previstos para publicar o site e o banco na internet (ainda não publicados) |
| Qualidade | pytest, Ruff, ESLint e GitHub Actions | Testes e verificações automáticas a cada alteração do código |
| Segurança | OWASP ZAP, Nuclei e suíte própria de testes de invasão | Procuram falhas antes de publicar |

## Segurança e publicação

Como o sistema foi pensado para ficar na internet, a segurança entrou no projeto desde o começo, e nada será publicado antes de passar por uma bateria de testes de invasão.

- **Acesso só com login.** Não há cadastro aberto: as contas são criadas por um gerente, e a senha inicial precisa ser trocada no primeiro acesso.
- **Senhas protegidas.** Elas são guardadas de um jeito que, mesmo se o banco vazasse, não dá para lê-las (método Argon2id).
- **Proteções contra abuso.** Há bloqueio após tentativas erradas de senha, limite de análises por usuário e limite de contas criadas por hora.
- **Banco de dados fechado.** Só o servidor da aplicação fala com ele, com permissões mínimas. Nada do banco fica acessível de fora.
- **Registro das ações administrativas.** Cada ação de gerenciamento de contas fica gravada para consulta posterior.
- **Testes de invasão automáticos.** Uma suíte própria tenta quebrar o sistema como um atacante faria, antes de cada publicação.

A hospedagem prevista é a Vercel para o site e o Supabase para o banco, e **a publicação ainda não foi feita**.

## Empresa parceira e origem dos dados

O projeto nasceu de uma necessidade real de uma empresa do ramo de controle de pragas, que vende armadilhas adesivas de mosquito, e usa como referência o equipamento StickFly K-45.

**A empresa.** Um dos integrantes da equipe, o Gustavo, é gerente nessa empresa e foi a ponte com a operação real. **O nome da empresa é mantido em sigilo a pedido do grupo**; ainda está em aberto se ela pode ser citada no vídeo ou no relatório final. Enquanto isso, o texto fala apenas em "empresa parceira".

**O equipamento.** A armadilha de referência é fixada na parede e usa três lâmpadas de luz ultravioleta que atraem os insetos até uma placa adesiva.

| Item | Medida |
| --- | --- |
| Modelo | StickFly K-45 |
| Tamanho da armadilha (comprimento × altura × largura) | 50 × 27 × 22 cm |
| Placa adesiva (o refil, que é o que a câmera olha) | 450 × 220 mm |
| Lâmpadas | 3 de 15 W, luz ultravioleta (UVA) |
| Alimentação | 110 V ou 220 V |

**As imagens e os dados.** As fotos usadas para ensinar o programa vêm de dois conjuntos de dados públicos, de pesquisadores que os publicaram com licença aberta (CC BY 4.0). Os créditos precisam aparecer no vídeo:

- Ong & Lim (2025). *An annotated image dataset of urban insects for computer vision and deep learning*. Figshare. [DOI 10.6084/m9.figshare.28280792.v1](https://doi.org/10.6084/m9.figshare.28280792.v1).
- Colares, Peres & Dambros (2025). *5-fold dataset for deep learning training using insect images from sticky traps in Central Amazon*. Figshare. [DOI 10.6084/m9.figshare.28688198](https://doi.org/10.6084/m9.figshare.28688198).

A validação com fotos reais da própria empresa parceira ainda não foi feita.

## Equipe e instituição

O TrapSight é o Projeto Integrador de Sistemas Inteligentes III do curso de Tecnologia em Sistemas Inteligentes da Fatec "Shunji Nishimura", em Pompeia.

| Pessoa | Papel |
| --- | --- |
| Pedro Lucas Francisco | Integrante da equipe, curso de Tecnologia em Sistemas Inteligentes |
| Gustavo | Integrante da equipe e gerente na empresa parceira, que trouxe o problema real |

Os demais integrantes e o professor orientador não estão registrados no repositório. **A preencher antes do vídeo:** nomes e papéis de todos, e o nome do orientador.

## Em que ponto o projeto está

A aplicação completa e o conjunto de imagens estão prontos; o treinamento da inteligência artificial e a publicação na internet são as próximas etapas. Situação em 29/10/2026.

| Etapa | Situação |
| --- | --- |
| Aplicação web (painel, cadastro, nova análise, detalhe, timelapse, contas e login) | Pronta, rodando no computador |
| Servidor, banco de dados e previsão de dias até saturar | Prontos |
| Conjunto de 3.000 imagens de treino, validação e teste | Pronto e auditado em 8 critérios de qualidade |
| Método clássico de comparação (separa escuro de claro) | Pronto: nota de 0,84 em 1 no conjunto de teste |
| Dados de demonstração (seis armadilhas simuladas) | Em ajuste final |
| Treinamento da inteligência artificial (U-Net) | **Ainda não feito.** O código de treino está pronto, falta executar |
| Comparação entre a inteligência artificial e o método clássico | Depende do treinamento |
| Testes de segurança completos | Em preparação |
| Publicação na internet (Vercel e Supabase) | Ainda não feita |
| Validação com fotos da empresa parceira | Não iniciada |

A nota de 0,84 mede o quanto a área marcada pelo método coincide com a resposta certa (1 é perfeito). É o ponto de partida que a inteligência artificial precisa superar.

## Para o vídeo: o que usar e o que não dizer

Todos os números abaixo foram conferidos no projeto e podem ser ditos com segurança; as frases são sugestões de ideia, não texto pronto.

### Números que podem aparecer

- **3.000** imagens montadas para ensinar e testar o programa (2.100 para treinar, 450 para ajustar, 450 para testar).
- **69** fotos reais de armadilhas como ponto de partida, com cerca de **24 mil** insetos já marcados.
- **14** dessas placas guardadas só para a avaliação final, sem nunca entrarem no treino.
- **3** situações possíveis: ok (menos de 10% coberta), atenção (10% a 20%) e trocar (mais de 20%).
- **450 × 220 mm**: o tamanho da placa adesiva que o sistema analisa.
- **8** critérios de qualidade conferidos no conjunto de imagens.

### Ideias fortes

- Trocar o "acho que está cheia" por uma medida.
- Nem cedo demais (desperdício), nem tarde demais (armadilha sem efeito).
- Não conta insetos: mede quanto da placa está coberta, porque os insetos se sobrepõem.
- Sujeira e poeira não contam: a medida é de quanta capacidade de captura ainda resta.
- Além de dizer como está, avisa quantos dias faltam.
- O problema veio de uma empresa de verdade, por meio de um integrante da própria equipe.

### O que não dizer

- **Não dizer que a inteligência artificial já foi treinada** nem citar um percentual de acerto dela: o treinamento ainda não foi feito.
- **Não prometer economia** em reais ou em porcentagem: os custos da empresa ainda não foram levantados.
- **Não dizer que está na internet:** a publicação ainda não foi feita.
- **Não dizer que há câmera instalada em campo:** isso está fora do escopo; as fotos são enviadas manualmente.
- **Não apresentar os dados da demonstração como reais:** as seis armadilhas mostradas são simuladas.
- **Não tratar 10% e 20% como definitivos:** são um ponto de partida a confirmar com a empresa.
- **Não citar o nome da empresa** sem autorização do grupo.
- **Não dizer que foi validado com fotos da empresa:** isso ainda não foi feito.
