# Changelog

Todas as mudancas importantes do Aplicacoes SPI serao documentadas neste arquivo.

## [0.8.0] - 2026-06-01

### Adicionado

- Adicionado modulo `atalhos`, com CRUD administrativo, validacao de links internos e externos e exibicao publica na home de noticias.
- Adicionado modulo `assinatura_e_mail`, com formulario autenticado, pre-preenchimento por perfil, previa e download de assinatura institucional em PNG.
- Adicionado suporte ao dominio `portal.spi.sp.gov.br`, mantendo compatibilidade com os acessos legados por `intranet.spi.sp.gov.br`.
- Adicionada ordenacao manual de itens da navbar pela tela de gerenciamento, refletindo imediatamente na barra publica.
- Adicionada carga estruturada do arquivo `docs/trv2.md` no ETP TIC `8`, posicionada apos o item `12.2` e renumerada pelo proprio app.

### Alterado

- Alterada a home publica de noticias para layout em duas colunas, com noticias a esquerda e painel de atalhos a direita.
- Alterada a grade principal de noticias para concentrar o slider na faixa superior e reposicionar os cards menores abaixo dele.
- Alterados os cards de atalhos para tamanho fixo em duas colunas, com rodape sem quebra e ajuste dinamico de fonte.
- Alterado o card "Ver todas as noticias publicadas" para usar bloco proprio, sem imagem, com centralizacao e preenchimento tipografico do placeholder.
- Alterado o slider de noticias para usar preenchimento proporcional da imagem, evitando distorcao.
- Alterada a previa da assinatura de e-mail para preservar o layout-base de referencia e ampliar a exibicao na interface.

### Corrigido

- Corrigida a ausencia da tabela inicial de `atalhos` no banco local.
- Corrigidos artefatos visuais na geracao da assinatura de e-mail, incluindo sobra de texto no bloco institucional e na area do telefone.
- Corrigido o encaixe do card final da home de noticias, removendo herancas indevidas dos cards com imagem.

## [0.7.0] - 2026-05-29

### Adicionado

- Adicionado modulo de usuarios e ramais, com listagem administrativa, cadastro, edicao, exclusao, perfis com foto, busca, ordenacao e paginacao.
- Adicionada listagem publica de ramais em cards, com modal de contato, campos estruturados e acoes de e-mail para Teams, Outlook e copia para a area de transferencia.
- Adicionado controle de recadastro de perfil para usuarios comuns, exigindo dados obrigatorios no primeiro acesso e revalidacao periodica.
- Adicionado suporte a diretorios LDAP configuraveis para autenticacao.
- Adicionado compartilhamento de TR, ETP TIC e DFD entre usuarios.
- Adicionadas anotacoes por fornecedor no painel de Pesquisa de Preco.

### Alterado

- Alterada a listagem de usuarios para paginar de 10 em 10 registros.
- Alterada a listagem de ramais para exibir apenas cadastros completos.
- Alterada a validacao de perfil para exigir e-mail, foto, ramal, cargo, setor, andar e bloco.
- Alterado o fluxo de logout para excluir usuario de primeiro acesso quando o cadastro nao for finalizado.
- Alterada a autenticacao LDAP para nao apagar e-mail ja cadastrado quando o atributo `mail` vier vazio.
- Alteradas permissoes de licitacoes para que Administradores do Sistema acessem todos os documentos sem restricoes de propriedade ou compartilhamento.
- Alterado o detalhe de noticias para transformar URLs digitadas no texto em links clicaveis.
- Alterado o suporte a anexos de noticias para permitir download de arquivos nao PDF e manter visualizacao inline para PDF.
- Alterado o rodape global para exibir a mensagem institucional centralizada.

### Corrigido

- Corrigido recadastro repetido apos novo login causado por e-mail apagado pelo LDAP.
- Corrigidas quebras de layout no modal de contato dos ramais.
- Corrigida a visibilidade de TRs para administradores do sistema.

## [0.6.0] - 2026-05-26

### Adicionado

- Adicionada Pesquisa de Preço ao Termo de Referência, com criação por aquisição ou serviço, pesquisador responsável, vigência para serviços e painel por TR.
- Adicionado cadastro global de fornecedores, com vínculo às pesquisas de preço e reutilização entre TRs.
- Adicionado lançamento de orçamento por fornecedor, com preços unitários por item herdado da tabela do item 1.1, validade do orçamento e cálculo automático de totais e médias.
- Adicionado anexo obrigatório do documento do fornecedor ao salvar orçamento, com download direto pelo botão Orçamento após o orçamento estar alimentado.
- Adicionada exportação XLSX da Pesquisa de Preço baseada na planilha modelo `PCs - Tab Alternativa`, preservando formatação, cores e mesclas.
- Adicionadas opções de destaque em vermelho nos formulários de item do TR e ETP TIC, incluindo marcação de texto, filhos e filhos de sessão.
- Adicionada legenda de parsers nos formulários de novo item do TR e ETP TIC.
- Adicionadas migrações para fornecedores, pesquisas de preço, pesquisador, remoção do e-mail duplicado de fornecedor, anexo de orçamento e múltiplos e-mails de contato.

### Alterado

- Alterado o cadastro de fornecedor para manter somente `E-mail do contato`, permitindo múltiplos e-mails separados por ponto e vírgula.
- Alterado o painel de Pesquisa de Preço para exibir nome, e-mail de contato e telefone do fornecedor, com cópia individual de cada e-mail por clique.
- Alterado o parser de itens para aceitar alíneas `$$` e incisos `**` mesmo quando usados diretamente em subitem.
- Alteradas telas de sessão para permitir marcar todos os itens filhos em vermelho.
- Alterado o botão Orçamento no painel para abrir o formulário enquanto o orçamento não estiver completo e baixar o anexo quando já houver resposta com documento.

### Configuração

- Adicionada dependência `openpyxl` para geração da planilha XLSX da Pesquisa de Preço.

## [0.5.0] - 2026-05-25

### Adicionado

- Adicionado editor dinâmico para ETP TIC, com sessões, itens, subitens, subseções, incisos, alíneas, movimentação, duplicação, limpeza de filhos e exportação DOCX.
- Adicionadas colunas "Atualizado em" e "Alterado por" nas listagens de TR e ETP TIC.
- Adicionado registro do último usuário que alterou TR e ETP TIC.
- Adicionados tooltips acionados por clique nas ações das listagens de TR e ETP TIC.
- Adicionado `AGENTS.md` com instruções do projeto para manter textos visíveis em português brasileiro com acentos.

### Alterado

- Ajustada a listagem de ETP TIC para diferenciar documentos dinâmicos e legados.
- Ajustados menus de ação do detalhe do TR e do ETP TIC para melhor uso em tabelas extensas.
- Removido o overlay escuro das imagens da página pública de notícias.
- Alterado o título das notícias no carrossel e nos cards laterais para rodapé azul no tom da navbar.
- Ajustado o tamanho automático dos títulos no rodapé das notícias para manter uma linha sem cortar letras com acentos, cedilha ou descendentes.
- Atualizados textos e testes do módulo de notícias para novas regras de exibição e gerenciamento.

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
