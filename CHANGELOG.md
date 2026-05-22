# Changelog

Todas as mudancas importantes do Aplicacoes SPI serao documentadas neste arquivo.

## [0.4.0] - 2026-05-22

### Adicionado

- Adicionado modulo Noticias com CRUD para superusuarios, imagem destaque, status de rascunho, agendada e publicada, campo fixada e anexos PDF.
- Adicionada home publica de noticias com carousel, cards laterais, pagina de detalhe, pagina "todas as noticias" paginada e comando `publicar_noticias_agendadas`.
- Adicionado modulo de gestao da navbar com menus e submenus, ordenacao, status ativo/inativo, links internos/externos e opcao de abrir em nova aba.
- Adicionado botao para duplicar DFD, copiando campos e itens da tabela vinculada.
- Adicionado suporte a upload de midia via `MEDIA_URL` e `MEDIA_ROOT`.

### Alterado

- Alterada a raiz e a home do sistema para abrir a tela publica de noticias.
- Alterada a barra superior para a identidade "Intranet SPI" com menus dinamicos cadastrados no banco.
- Ajustado o fluxo de edicao de DFD e ETP TIC para abrir primeiro os dados basicos, mantendo o acesso as secoes por botao separado.
- Ajustado o layout da home de noticias para usar o slider e cards laterais sem lista inferior.
- Ajustada a exibicao de imagem destaque: slider preenche o quadro por deformacao e cards laterais preenchem por capa.
- Ajustado o anexo PDF da noticia para exibir link de acesso ao final do texto.
- Tornada a URL da navbar opcional para menus pai usados apenas como dropdown.

### Configuracao

- Adicionada dependencia `Pillow` para suporte a `ImageField`.

## [0.3.0] - 2026-05-20

### Adicionado

- Adicionado botao para duplicar TR inteiro na listagem, copiando sessoes, itens, subitens e tabelas.
- Adicionado campo editavel do item 1.2 no DFD, exibido apos a tabela da secao Descricao Sucinta do Objeto.
- Adicionado suporte a destaque em vermelho com `*` e `**` no DFD, incluindo preview, tabela e exportacao DOCX.
- Adicionada coluna SIAFISICO e campos de unidade, valor unitario e valor total na tabela do DFD.

### Alterado

- Ajustada a numeracao do DFD para iniciar indices apenas na secao Descricao Sucinta do Objeto.
- Ajustada a exportacao DOCX do DFD com Verdana 10 no texto, Verdana 8 nas tabelas, Informacoes Preliminares alinhada a esquerda e Responsaveis centralizado.
- Ajustado o botao Concluir do DFD para salvar a secao atual antes de concluir.
- Normalizado o item 1.2 do DFD para exportar sempre como `1.2.` mesmo quando digitado com prefixos alternativos.
- Melhorada a interpretacao de marcacoes com asterisco para destacar palavras soltas, frases e paragrafos inteiros.

## [0.2.0] - 2026-05-20

### Adicionado

- Adicionado modulo DFD em licitacoes, com listagem, criacao, edicao por secoes fixas, preview, conclusao, exclusao e exportacao DOCX.
- Adicionada tabela estruturada de itens no DFD, com CRUD e exportacao para DOCX.
- Adicionada tabela de itens no item 1.1 do Termo de Referencia, com CRUD, exibicao no detalhe e exportacao DOCX.
- Adicionado suporte a marcacao textual em vermelho por asterisco nos itens do TR, com renderizacao na tela e no DOCX.
- Adicionada opcao de posicao ao mover/duplicar itens do TR como subitem.
- Adicionado atalho Ctrl+Enter para salvar formularios de item do TR.

### Alterado

- Ajustada a exportacao do TR para remover recuos em itens e subitens.
- Atualizadas regras de duplicacao para preservar linhas tabeladas vinculadas aos itens.
- Atualizado `.gitignore` para ignorar `docs/` e backups locais `db.sqlite3*`.

## [0.1.0] - 2026-05-18

### Adicionado

- Publicada a base inicial do projeto Django Aplicacoes SPI.
- Adicionado modulo de licitacoes com modelos, formularios, servicos, rotas, views e templates.
- Adicionados arquivos estaticos, templates base e tela de login.
- Adicionado documento modelo em `docs/tr-modelo.docx`.
- Adicionado `requirements.txt` com as dependencias do ambiente atual.
- Adicionado `.gitignore` para evitar versionar ambiente virtual, banco SQLite local, caches e arquivos de ambiente.

### Configuracao

- Repositorio configurado para uso via SSH no GitHub.
