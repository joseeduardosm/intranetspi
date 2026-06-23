import re

with open('/root/aplicacoesspi/aplicacoesspi/settings.py', 'r') as f:
    settings = f.read()

# Trocar para PostgreSQL
settings = re.sub(r"'ENGINE': 'django\.db\.backends\.sqlite3',", "'ENGINE': 'django.db.backends.postgresql',", settings)
settings = re.sub(r"'NAME': BASE_DIR / 'db\.sqlite3',", "'NAME': 'spi_db',", settings)

with open('/root/aplicacoesspi/aplicacoesspi/settings.py', 'w') as f:
    f.write(settings)
