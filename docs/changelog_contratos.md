# Changelog do App Contratos

## 2026-06-06

### Adicionado
- Novo app Django `contratos` integrado ao projeto `aplicacoesspi`.
- Rotas do módulo em `contratos/urls.py` com namespace `contratos:`.
- Modelos para contratos, empresas, responsáveis, itens, aditivos, documentos, diário de bordo, pagamentos por competência, checklist, medições, avaliação de qualidade, eventos financeiros e memória de retroatividade.
- Página inicial do módulo, listagem principal de contratos, cadastro de empresas e painel de contrato.
- Dashboard inicial com indicadores financeiros e gerenciais server-rendered.
- Exportação XLSX do diário de bordo contratual.
- CSS próprio do módulo em `static/contratos/css/contratos.css`.
- Testes automatizados cobrindo cálculos, ACL, exportação, numeração incremental e detalhamento por itens.

### Alterado
- Cadastro de contratos passou a oferecer numeração incremental automática no formato `NNN/AAAA`, baseada no ano da vigência.
- Campo `Detalhamento do objeto` foi convertido para um mecanismo estruturado por itens com botão `+ item`, inspirado no fluxo do TR.
- Campo `Empresa contratada` recebeu atalho `+` para abrir rapidamente o CRUD de empresas.
- Fluxo de autorização de pagamento ganhou tela de confirmação com espera visual de 10 segundos.
- ACL foi ajustada para não tentar resolver objeto inexistente em `CreateView` com usuários de nível `MODIFICACAO`.

### Observações
- A exportação em PDF e gráficos Plotly continuam dependentes de bibliotecas não disponíveis no ambiente atual.
- O recurso ACL `contratos` precisa existir no banco do ambiente para o módulo aparecer na seção `Módulos` da navbar.
