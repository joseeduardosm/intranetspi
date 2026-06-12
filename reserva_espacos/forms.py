"""Formulários do módulo de reserva de espaços."""

from __future__ import annotations

import calendar
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import ObjetoReservavel, ReservaRecurso
BOOTSTRAP_INPUT = "form-control form-control-lg"
BOOTSTRAP_TEXTAREA = "form-control"


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes visuais coerentes com o restante do portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.SelectMultiple):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            else:
                css = BOOTSTRAP_INPUT
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {css}".strip()


class ObjetoReservavelForm(BootstrapModelForm):
    """Formulário do cadastro de objetos que aparecerão no calendário."""

    class Meta:
        model = ObjetoReservavel
        fields = ["nome", "localizacao", "cor", "ativo"]
        widgets = {
            "cor": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }


class ReservaRecursoForm(BootstrapModelForm):
    """Formulário de criação e edição com suporte a recorrência."""

    conflict_error_message = "Já existe uma reserva para este objeto no intervalo informado."

    recorrencia = forms.ChoiceField(
        label="Recorrência",
        required=False,
        choices=[
            ("", "Sem recorrência"),
            ("daily", "Diária"),
            ("weekly", "Semanal"),
            ("biweekly", "Quinzenal"),
            ("monthly", "Mensal"),
        ],
    )
    recorrencia_fim = forms.DateField(
        label="Data fim da recorrência",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = ReservaRecurso
        fields = [
            "objeto",
            "data",
            "hora_inicio",
            "hora_fim",
            "titulo",
            "responsavel",
            "observacoes",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)
        objetos = ObjetoReservavel.objects.filter(ativo=True).order_by("nome")
        if self.instance and self.instance.pk:
            objetos = ObjetoReservavel.objects.filter(Q(pk=self.instance.objeto_id) | Q(ativo=True)).order_by("nome")
        self.fields["objeto"].queryset = objetos.distinct()
        self.fields["objeto"].label_from_instance = lambda obj: obj.nome_exibicao
        self.fields["data"].input_formats = ["%Y-%m-%d"]
        self.fields["hora_inicio"].input_formats = ["%H:%M"]
        self.fields["hora_fim"].input_formats = ["%H:%M"]

        # No cadastro, o responsável deve refletir o próprio usuário logado,
        # evitando divergência entre quem reservou e quem aparece no registro.
        if self.request_user and getattr(self.request_user, "is_authenticated", False) and not (self.instance and self.instance.pk):
            self.initial["responsavel"] = self.get_responsavel_padrao()
            self.fields["responsavel"].widget.attrs["readonly"] = True
            self.fields["responsavel"].help_text = "Preenchido automaticamente com o seu usuário."

        if self.instance and self.instance.pk:
            self.fields["recorrencia"].disabled = True
            self.fields["recorrencia_fim"].disabled = True

    def get_responsavel_padrao(self) -> str:
        """Retorna o nome que deve ser gravado como responsável da reserva."""

        if not self.request_user:
            return ""
        perfil = getattr(self.request_user, "perfil", None)
        if perfil and perfil.nome_completo:
            return perfil.nome_completo
        return self.request_user.get_full_name() or self.request_user.username

    def is_recurring_series(self) -> bool:
        """Indica se a reserva editada já pertence a uma série existente."""

        return bool(self.instance and self.instance.pk and self.instance.serie_id)

    def _add_months(self, base_date, months: int):
        """Soma meses preservando o dia quando o mês destino suportar."""

        year = base_date.year + (base_date.month - 1 + months) // 12
        month = (base_date.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        return base_date.replace(year=year, month=month, day=min(base_date.day, last_day))

    def get_recurrence_dates(self):
        """Expande a data base nas ocorrências da recorrência informada."""

        data = self.cleaned_data.get("data")
        recorrencia = self.cleaned_data.get("recorrencia") or ""
        recorrencia_fim = self.cleaned_data.get("recorrencia_fim")
        if not data:
            return []
        if not recorrencia:
            return [data]
        if not recorrencia_fim:
            return [data]

        dates = [data]
        current = data
        if recorrencia == "daily":
            delta = timedelta(days=1)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "weekly":
            delta = timedelta(days=7)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "biweekly":
            delta = timedelta(days=14)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "monthly":
            while True:
                current = self._add_months(current, 1)
                if current > recorrencia_fim:
                    break
                dates.append(current)
        return dates

    def validate_series_update_conflicts(self, instance: ReservaRecurso) -> None:
        """Valida conflitos de todas as datas da série ao editar com escopo total."""

        if not instance.serie_id:
            return
        objeto = self.cleaned_data.get("objeto")
        hora_inicio = self.cleaned_data.get("hora_inicio")
        hora_fim = self.cleaned_data.get("hora_fim")
        if not (objeto and hora_inicio and hora_fim):
            return
        ocorrencias = ReservaRecurso.objects.filter(serie_id=instance.serie_id).order_by("data")
        inicio_min = hora_inicio.hour * 60 + hora_inicio.minute
        fim_min = hora_fim.hour * 60 + hora_fim.minute
        for ocorrencia in ocorrencias:
            conflitos = ReservaRecurso.objects.filter(objeto=objeto, data=ocorrencia.data).exclude(serie_id=instance.serie_id)
            for reserva in conflitos:
                r_inicio = reserva.hora_inicio.hour * 60 + reserva.hora_inicio.minute
                r_fim = reserva.hora_fim.hour * 60 + reserva.hora_fim.minute
                if inicio_min < r_fim and fim_min > r_inicio:
                    raise ValidationError(self.conflict_error_message)

    def clean(self):
        """Executa as validações de recorrência, horários e conflitos."""

        cleaned = super().clean()
        objeto = cleaned.get("objeto")
        data = cleaned.get("data")
        hora_inicio = cleaned.get("hora_inicio")
        hora_fim = cleaned.get("hora_fim")
        recorrencia = cleaned.get("recorrencia") or ""
        recorrencia_fim = cleaned.get("recorrencia_fim")

        if self.instance and self.instance.pk and recorrencia:
            self.add_error("recorrencia", "A recorrência só pode ser definida na criação.")

        if recorrencia and not recorrencia_fim:
            self.add_error("recorrencia_fim", "Informe a data fim para usar recorrência.")
        if recorrencia and data and recorrencia_fim and recorrencia_fim < data:
            self.add_error("recorrencia_fim", "A data fim deve ser maior ou igual à data inicial.")

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora final deve ser maior que a hora inicial.")

        if objeto and data and hora_inicio and hora_fim:
            dates = self.get_recurrence_dates() or [data]
            inicio_min = hora_inicio.hour * 60 + hora_inicio.minute
            fim_min = hora_fim.hour * 60 + hora_fim.minute
            for occ_date in dates:
                conflitos = ReservaRecurso.objects.filter(objeto=objeto, data=occ_date).exclude(pk=self.instance.pk)
                for reserva in conflitos:
                    r_inicio = reserva.hora_inicio.hour * 60 + reserva.hora_inicio.minute
                    r_fim = reserva.hora_fim.hour * 60 + reserva.hora_fim.minute
                    if inicio_min < r_fim and fim_min > r_inicio:
                        self.add_error(None, self.conflict_error_message)
                        return cleaned

        # Mesmo se alguém tentar alterar o valor manualmente via POST, o backend
        # mantém o responsável como o próprio usuário na criação.
        if self.request_user and getattr(self.request_user, "is_authenticated", False) and not (self.instance and self.instance.pk):
            cleaned["responsavel"] = self.get_responsavel_padrao()

        return cleaned
