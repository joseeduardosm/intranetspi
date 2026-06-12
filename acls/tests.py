# Criado por OpenAI Codex em 08/06/2026
# Objetivo: garantir que o ACL aceite múltiplos usuários e grupos sem perder a lógica de acesso.

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from .forms import RegraAcessoForm
from .models import Recurso, RegraAcesso
from .utils import obter_nivel_acesso


class RegraAcessoFormTests(TestCase):
    """Valida o comportamento do formulário com seleção múltipla de alvos."""

    def setUp(self):
        User = get_user_model()
        self.usuario_1 = User.objects.create_user(username='ana', password='123')
        self.usuario_2 = User.objects.create_user(username='bruno', password='123')
        self.grupo_1 = Group.objects.create(name='Financeiro')
        self.grupo_2 = Group.objects.create(name='Contratos')
        # O sinal do app já pode ter cadastrado este recurso automaticamente.
        self.recurso, _ = Recurso.objects.get_or_create(slug='acls', defaults={'nome': 'ACL'})

    def test_formulario_aceita_varios_usuarios_e_grupos(self):
        # O formulário deve persistir todos os alvos selecionados de uma vez.
        form = RegraAcessoForm(
            data={
                'recurso': self.recurso.pk,
                'nivel': RegraAcesso.NIVEL_MODIFICACAO,
                'usuarios': [self.usuario_1.pk, self.usuario_2.pk],
                'grupos': [self.grupo_1.pk, self.grupo_2.pk],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        regra = form.save()

        self.assertCountEqual(regra.usuarios.values_list('pk', flat=True), [self.usuario_1.pk, self.usuario_2.pk])
        self.assertCountEqual(regra.grupos.values_list('pk', flat=True), [self.grupo_1.pk, self.grupo_2.pk])

    def test_formulario_exige_ao_menos_um_alvo(self):
        # Continua inválido salvar uma regra sem usuários e sem grupos.
        form = RegraAcessoForm(
            data={
                'recurso': self.recurso.pk,
                'nivel': RegraAcesso.NIVEL_LEITURA,
                'usuarios': [],
                'grupos': [],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Você deve selecionar pelo menos um Usuário ou um Grupo/Setor.', form.non_field_errors())

    def test_formulario_exibe_nome_completo_no_picker_de_usuarios(self):
        self.usuario_1.first_name = 'Ana'
        self.usuario_1.last_name = 'Souza'
        self.usuario_1.save(update_fields=['first_name', 'last_name'])

        form = RegraAcessoForm()

        self.assertEqual(form.fields['usuarios'].label_from_instance(self.usuario_1), 'Ana Souza')


class ObterNivelAcessoTests(TestCase):
    """Garante que a apuração de permissão considere os novos relacionamentos múltiplos."""

    def setUp(self):
        User = get_user_model()
        self.usuario_direto = User.objects.create_user(username='carla', password='123')
        self.usuario_por_grupo = User.objects.create_user(username='diego', password='123')
        self.usuario_sem_acesso = User.objects.create_user(username='eva', password='123')
        self.grupo = Group.objects.create(name='Jurídico')
        self.usuario_por_grupo.groups.add(self.grupo)
        # O sinal do app já pode ter cadastrado este recurso automaticamente.
        self.recurso, _ = Recurso.objects.get_or_create(slug='contratos', defaults={'nome': 'Contratos'})

    def test_regra_por_usuario_tem_prioridade_sobre_grupo(self):
        # A regra direta do usuário continua prevalecendo sobre a herdada por grupo.
        regra_grupo = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_LEITURA)
        regra_grupo.grupos.add(self.grupo)

        regra_usuario = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra_usuario.usuarios.add(self.usuario_por_grupo)

        self.assertEqual(obter_nivel_acesso(self.usuario_por_grupo, 'contratos'), RegraAcesso.NIVEL_CONTROLE_TOTAL)

    def test_regra_por_grupo_atende_usuario_associado(self):
        # O usuário deve herdar o maior nível disponível entre seus grupos.
        regra_grupo = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_MODIFICACAO)
        regra_grupo.grupos.add(self.grupo)

        self.assertEqual(obter_nivel_acesso(self.usuario_por_grupo, 'contratos'), RegraAcesso.NIVEL_MODIFICACAO)

    def test_usuario_fora_dos_alvos_fica_sem_acesso(self):
        # Se houver regras no recurso e o usuário não estiver em nenhuma delas, o acesso deve ser negado.
        regra_usuario = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_LEITURA)
        regra_usuario.usuarios.add(self.usuario_direto)

        self.assertIsNone(obter_nivel_acesso(self.usuario_sem_acesso, 'contratos'))
