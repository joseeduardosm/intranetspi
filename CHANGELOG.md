# Registro de Alterações

Todas as mudanças importantes deste projeto são documentadas neste arquivo.

## [0.2.0] - 2026-06-06
- Reformulada a navegação global:
  - Substituída a navbar horizontal por uma sidebar vertical dentro e fora da área autenticada.
  - A sidebar inicia recolhida, expande ao passar o mouse ou receber foco e diferencia visualmente os itens de primeiro e segundo nível.
  - Removido o item redundante "Home", mantendo "Intranet SPI" como acesso à página inicial.
  - Mantida a sidebar também na tela de login e atualizado o teste de renderização da navbar pública.
- Reforçado o envio do formulário de logout para atualizar o token CSRF antes da requisição e evitar falhas causadas por páginas antigas no navegador.
- Redesenhada a página de detalhe dos imóveis do RegulaSGI:
  - Criados cartões de resumo e uma timeline processual mais clara, sem exibição de percentual.
  - Renomeado o modal para "Histórico Completo do Imóvel" e simplificado o histórico para mostrar apenas eventos efetivamente registrados.
  - Corrigido o cálculo de dias para considerar o fuso horário local e impedir valores negativos.
- Aprimorada a listagem de imóveis do RegulaSGI:
  - Adicionada a coluna "Prazo" antes das ações, com próxima etapa, data limite, dias restantes e barra de progresso.
  - Definidas as faixas de progresso em verde até 50%, amarelo de 51% a 75% e vermelho acima de 75%.
  - Corrigido o posicionamento do menu de ações para sobrepor a área rolável da tabela sem ser cortado.
- Adicionadas as pastas locais de certificados ao `.gitignore`, evitando o versionamento de certificados e chaves privadas.
- Documentados arquivos `.py`, `.html` e `.css` dos apps e templates principais com cabeçalhos de autoria, resumo do objetivo do arquivo e comentários explicativos em português brasileiro.
  - Incluídos comentários nos apps `acls`, `aplicacoesspi`, `assinatura_e_mail`, `atalhos`, `licitacoes`, `navbar`, `noticias`, `organograma`, `regulariza_sgi`, `setores` e `usuarios`.
  - Documentados templates globais, templates por app e CSS estáticos ainda sem cabeçalho.
  - Preservado o comportamento existente, com foco em explicar fluxos de permissões, formulários, serviços, views, templates, organogramas, ramais e integrações entre apps.
- Atualizada a orientação do projeto em `AGENTS.md` para reforçar que código gerado deve ser comentado de forma explicativa e legível.
- Adicionada dependência `whitenoise` (v6.12.0) ao `requirements.txt` para resolver erro de módulo ausente e melhorar o tratamento de arquivos estáticos.
- Atualizado o conjunto de testes:
  - Corrigida a asserção em `assinatura_e_mail/tests.py` para o nome correto da Secretaria.
  - Corrigida a asserção de texto da UI em `noticias/tests.py` para coincidir com o rótulo do botão atualizado "Ver todas as notícias publicadas".
  - Garantido que todos os testes agora passam (198 no total, cobertura de 100%).
- Modificados os formulários de perfil de usuário em `usuarios/forms.py`:
  - Adicionado "(Opcional)" aos rótulos dos campos `celular` e `data_nascimento` em ambos `UsuarioPerfilForm` e `UsuarioCreateForm`.
- Verificada a integração do repositório e assegurado que não há quebras após puxar o código mais recente.

## [0.1.0] - 2026-06-05
- Lançamento inicial após corrigir a dependência e atualizar os rótulos dos formulários.

## Histórico dos Aplicativos

- **usuarios**: Gerencia perfis de usuários, permite edição de dados pessoais e inclusão de campos opcionais como celular e data de nascimento.
- **noticias**: Publicação e gerenciamento de notícias; inclui listagem, detalhe e filtragem por categorias.
- **assinatura_e_mail**: Integração de assinatura eletrônica em documentos e envio de e‑mails automatizados.
- **assinatura_e_mail/tests**: Cobertura de testes automatizados para garantir a correta geração de PDFs e envios.
- **noticias/tests**: Testes de interface e funcionalidade de listagem e navegação de notícias.
- **assinatura_e_mail/migrations**: Controle de versionamento do modelo de assinatura e ajustes de schema.
- **usuarios/migrations**: Histórico de migrações para campos de perfil, incluindo adição de campos opcionais.
