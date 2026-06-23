filepath = '/root/aplicacoesspi/aplicacoesspi/settings.py'
with open(filepath, 'r') as f:
    c = f.read()

import re

old_db = """DATABASES = {
    'default': {
        # Banco SQLite usado pelo ambiente atual do projeto.
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}"""

new_db = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'spi_db',
        'USER': 'spi_user',
        'PASSWORD': 'admin123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}"""

c = c.replace(old_db, new_db)

with open(filepath, 'w') as f:
    f.write(c)
