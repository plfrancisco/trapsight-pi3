# Como contribuir

O TrapSight é um projeto acadêmico (Projeto Integrador, Fatec Pompeia) com **um único mantenedor**. Sugestões e relatos de problemas são bem-vindos; o ritmo de resposta é de melhor esforço.

## Relatar um problema ou sugerir algo

Abra uma [*issue*](https://github.com/plfrancisco/trapsight-pi3/issues) e inclua:

- o que você esperava e o que aconteceu;
- os passos para reproduzir, com a versão (veja o [`CHANGELOG.md`](CHANGELOG.md)) e o navegador ou sistema usado;
- uma imagem ou o texto do erro, se houver. Não envie dados pessoais nem senhas.

**Falhas de segurança não vão em *issue*.** Siga o [`SECURITY.md`](SECURITY.md).

## Enviar uma mudança

1. Abra uma *issue* antes, descrevendo a mudança. Isso evita trabalho que não possa ser aceito.
2. Faça um *fork*, crie uma branch e prepare o ambiente com o [guia de execução](.context/docs/EXECUCAO.md).
3. Rode os testes antes de enviar. Não há CI automático, então a conferência é local:
   - backend: `scripts/testar-backend.sh` (e `uv run ruff check src tests`, `uv run ruff format --check src tests`);
   - frontend: `npm run lint`, `npm run build` e `npm test`.
4. Envie o *pull request* explicando o que mudou e por quê. Mudanças de comportamento precisam de teste.

## Padrões do projeto

- **Commits:** uma linha, em português, no formato `tipo: descrição` (`feat`, `fix`, `docs`, `chore`, `style`).
- **Código:** o backend segue o `ruff`; o frontend, o ESLint do repositório.
- **Segredos:** nunca versione `.env`, chaves, senhas ou dados reais. O `.gitignore` já cobre os arquivos de ambiente.
- **Documentação:** se a mudança altera o que o README ou o guia descrevem, atualize-os no mesmo *pull request*.

## Licença das contribuições

Ao enviar uma contribuição, você concorda que ela seja distribuída sob a [licença MIT](LICENSE) do projeto.
