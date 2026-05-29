# Instruções do projeto
- Textos de interface devem usar português brasileiro com acentos e cedilha.
- Não converter textos visíveis para ASCII, sempre usar UTF8.
- Manter ASCII apenas em identificadores técnicos quando fizer sentido.
## Django
- Usar os padrões existentes do projeto antes de criar novas abstrações.
- Rodar `./.venv/bin/python manage.py check` após alterações, mas evitar testes excessivos para economizar tokens.
- Rodar testes específicos do app alterado quando houver mudança em views, models, forms ou templates. Mas evitar testes excessivos para economizar tokens.
- Criar migrações quando alterar models.
- cada modulo deve ter seu arquivo .css separado para quando mexer no estilo, afetar somente aquele modulo obrigatoriamente.