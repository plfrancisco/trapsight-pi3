# Política de segurança

O TrapSight é um protótipo acadêmico com login, upload de imagens e banco de dados. Se você encontrar uma falha de segurança, agradecemos que ela seja relatada de forma privada.

## Como relatar uma vulnerabilidade

1. Abra a aba **Security** do repositório e clique em **Report a vulnerability** (relato privado de vulnerabilidades do GitHub).
2. Descreva o problema, os passos para reproduzi-lo e o impacto que você enxerga.
3. Não inclua a falha em uma *issue* pública nem em um *pull request*, para que ela não fique exposta antes da correção.

Se o botão não aparecer, abra uma *issue* pedindo um canal privado de contato, **sem descrever a falha**.

## O que esperar

O projeto tem um único mantenedor e é mantido em regime de melhor esforço. A meta é confirmar o recebimento em até 7 dias. Não há prazo garantido de correção nem programa de recompensas.

## Versões com correção

Somente a versão mais recente, na branch `main`, recebe correções.

## Regras para testar

- Teste apenas com as **contas de demonstração** descritas no [README](README.md). Não tente acessar contas ou dados de outras pessoas.
- Não envie fotos pessoais ou sensíveis: as imagens da demonstração ficam guardadas no banco.
- Não faça testes de carga, de negação de serviço nem varreduras automatizadas intensas contra a demonstração publicada. Ela roda em planos gratuitos.
- Se acessar dados que não deveria, pare, não os copie e relate o ocorrido.

## Escopo

Dentro do escopo: a aplicação (frontend e API), o banco de dados e as configurações de publicação deste repositório.

Fora do escopo: vulnerabilidades da Vercel, do Supabase e do GitHub em si (relate-as aos respectivos fornecedores) e falhas que exijam acesso físico ao computador do mantenedor.

As proteções já existentes (senhas com Argon2id, CSRF, limites de uso, permissões mínimas no banco) estão descritas em [`.context/rules/security_spec.md`](.context/rules/security_spec.md).
