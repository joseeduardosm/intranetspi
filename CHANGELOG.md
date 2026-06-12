# Registro de Alterações

Todas as mudanças importantes deste projeto são documentadas neste arquivo.

## [0.3.4] - 2026-06-12
- Ajustado o formulário do módulo `reserva_espacos` para exibir conflitos de sobreposição de reserva em modal Bootstrap, substituindo a mensagem inline abaixo do campo de horário.
- Padronizada a validação de conflito do módulo para retornar erro não associado a campo tanto na criação quanto na edição simples e na edição de séries recorrentes.
- Ampliada a suíte de testes do `reserva_espacos` para cobrir a renderização do modal de conflito e a nova estratégia de validação.

## [0.3.3] - 2026-06-09
- Reestruturado o módulo `regulariza_sgi` com novo cadastro e detalhe do imóvel em abas:
  - `Dados Iniciais`, `Dívida` e `Observações`;
  - subabas `Observações` e `Timeline` no detalhe;
  - inclusão de `Número SGI`, `Imissão na posse`, `Imunidade` e novos campos de dívida.
- Ajustado o fluxo processual do RegulaSGI para manter `prorrogação` e `manifestação` disponíveis em paralelo após o protocolo, até o registro da manifestação final.
- Criado o histórico funcional consolidado do imóvel:
  - observações com usuário, data/hora e paginação;
  - timeline geral para cadastro, edição, SEI, anexos, protocolo, prorrogação, manifestação e novos ciclos.
- Refinada a experiência do formulário do imóvel:
  - campo `Imunidade` com radiobox inline `Sim/Não`;
  - exibição condicional de `Tempo de imunidade (anos)` apenas quando `Sim` estiver marcado;
  - ocultação de `SEI` e `Link SEI` no cadastro novo, mantendo-os apenas onde fazem sentido no detalhe/edição.
- Ajustado o bloco de processos SEI no detalhe para usar o próprio número do processo como link clicável, sem exibir a URL bruta.
- Convertidos os campos `Dívidas não ajuizadas`, `Dívidas ajuizadas` e `Encargos` para valores monetários:
  - autoformatação em tela no padrão brasileiro `2.123,32`;
  - persistência em banco como valores decimais;
  - migração dos dados legados em texto para formato numérico.
- Adicionadas migrações, filtro de template para moeda e ampliação da suíte de testes do `regulariza_sgi`, mantendo `manage.py check` e os testes do módulo verdes após as mudanças.

## [0.3.2] - 2026-06-08
- Criado o módulo `contratos_v2` com identidade visual isolada, rotas próprias e fluxo inicial de cadastro de contratos.
- Estruturado o domínio de competências mensais com checklist versionado, avaliação de qualidade por itens, medição, pagamento e estados operacionais.
- Implementado o detalhamento dos responsáveis internos com cards clicáveis e modal de contato reutilizando o padrão do módulo de ramais.
- Ajustada a área de avaliação de qualidade para exibir justificativa do fiscal e manifestação do gestor apenas quando a nota fica abaixo da máxima, com estado pendente até a conclusão das manifestações exigidas.
- Adicionada a etapa de medição com opção de pró-rata nas competências de borda da vigência.
- Refinados os cards de status da competência para destacar pendências de avaliação em amarelo até a manifestação do gestor.
- Ampliado o conjunto de formulários e ações do `contratos_v2`, incluindo versões de checklist, grupos, itens, escalas, faixas de liberação e geração idempotente de competências.

## [0.3.1] - 2026-06-08
- Atualizado o módulo `acls` para permitir múltiplos alvos por regra:
  - substituídos os vínculos únicos por relacionamentos muitos-para-muitos com usuários e grupos/setores;
  - ajustada a tela `acls/nova/` para seleção de zero ou vários usuários e zero ou vários grupos/setores em cada regra;
  - preservada a prioridade da regra direta de usuário sobre a regra herdada por grupo na apuração de permissões;
  - criada migração para converter automaticamente os vínculos antigos para a nova estrutura.
- Refinada a apresentação do módulo `acls`:
  - atualizada a listagem para exibir todos os usuários e grupos associados a cada regra;
  - separado o CSS específico do módulo em arquivo próprio, sem estilos inline no template.
- Ampliada a cobertura de testes do `acls` para validar seleção múltipla e cálculo de nível de acesso.
- Ajustados os testes do módulo `contratos` para a nova estrutura de regras de ACL.
- Atualizados textos da experiência de autenticação e perfil:
  - alterado o nome exibido na tela de login para `Intranet SPI`;
  - revisada a mensagem de atualização cadastral obrigatória com texto institucional mais detalhado.
- Removido do `acls.signals` o cadastro manual segregado do recurso `organograma`, mantendo o fluxo centralizado de sincronização de recursos.

## [0.3.0] - 2026-06-07
- Criado e integrado o novo módulo `contratos` ao projeto `aplicacoesspi`, com rotas próprias, ACL dedicada e identidade visual isolada em CSS.
- Estruturado o domínio contratual com cadastros de contrato, empresa contratada, responsáveis da empresa, itens, termos aditivos, documentos, ocorrências, competências de pagamento, checklist padrão, avaliação de qualidade e eventos financeiros.
- Automatizado o ciclo inicial do contrato:
  - geração de competências conforme a vigência, inclusive períodos parciais no início e no fim;
  - bloqueio operacional das competências até o cadastro do checklist padrão do contrato;
  - replicação do checklist padrão para todas as competências já criadas.
- Implementados os fluxos operacionais do detalhe do contrato:
  - inclusão e manutenção de itens;
  - anexos de checklist com ações de anexar, editar, ver e limpar;
  - medição mensal baseada automaticamente nos itens do contrato;
  - lançamento de pagamento com anexos obrigatórios e conclusão da competência.
- Aprimorada a experiência de uso do módulo:
  - cadastro de empresa em modal sem perda dos dados já digitados no contrato;
  - preenchimento automático do número do contrato no formato `NNN/AAAA`;
  - links para responsáveis internos com cartão/modal de contato;
  - menus de ações `...` nas listagens e grades do contrato;
  - ordenação crescente e decrescente em todas as colunas da listagem principal;
  - link direto no número do contrato para abrir o detalhe.
- Ajustados cálculos e exibições financeiras do contrato:
  - separação explícita entre base mensal e valor global;
  - exibição monetária padronizada em reais;
  - vigência refletida corretamente no valor global consolidado.
- Adicionadas migrações, templates parciais, tela de medição em lote e tags auxiliares específicas do módulo `contratos`.

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
