import re

with open('/root/aplicacoesspi/aplicacoesspi/settings.py', 'r') as f:
    settings = f.read()

# Trocar para sqlite3 temporariamente
settings = re.sub(r"'ENGINE': 'django\.db\.backends\.postgresql',", "'ENGINE': 'django.db.backends.sqlite3',", settings)
settings = re.sub(r"'NAME': 'spi_db',", "'NAME': BASE_DIR / 'db.sqlite3',", settings)

with open('/root/aplicacoesspi/aplicacoesspi/settings.py', 'w') as f:
    f.write(settings)
