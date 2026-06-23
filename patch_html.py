filepath = '/root/aplicacoesspi/templates/contratos/contrato_form.html'
with open(filepath, 'r') as f:
    c = f.read()

script = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    const dataInicioField = document.querySelector('input[name="data_inicio_vigencia"]');
    const numeroContratoField = document.querySelector('input[name="numero_contrato"]');
    
    if (dataInicioField && numeroContratoField && !numeroContratoField.value) {
        dataInicioField.addEventListener('change', function() {
            const dataVal = this.value;
            if (dataVal) {
                const year = dataVal.split('-')[0];
                if (year.length === 4) {
                    fetch(`/contratos/proximo-numero/?ano=${year}`)
                        .then(response => response.json())
                        .then(data => {
                            if (data.numero && !numeroContratoField.value) {
                                numeroContratoField.value = data.numero;
                            }
                        });
                }
            }
        });
    }
});
</script>
{% endblock %}
"""

if "proximo-numero" not in c:
    c = c.replace("{% endblock %}", script)

with open(filepath, 'w') as f:
    f.write(c)
