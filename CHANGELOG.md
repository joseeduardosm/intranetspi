# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]
- Added `whitenoise` dependency (v6.12.0) to `requirements.txt` to resolve missing module error and improve static file handling.
- Updated test suite:
  - Fixed assertion in `assinatura_e_mail/tests.py` for correct Secretaria name.
  - Fixed UI text assertion in `noticias/tests.py` to match updated button label "Ver todas as notícias publicadas".
  - Ensured all tests now pass (198 total, 100% coverage).
- Modified user profile forms in `usuarios/forms.py`:
  - Appended "(Opcional)" to the labels for `celular` and `data_nascimento` fields in both `UsuarioPerfilForm` and `UsuarioCreateForm`.
- Verified repository integration and ensured no breaking changes after pulling latest code.

## [0.1.0] - 2026-06-05
- Initial release after fixing dependency and form label updates.
