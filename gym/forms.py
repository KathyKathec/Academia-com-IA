# gym/forms.py
from django import forms
from django.forms import ModelForm, inlineformset_factory
from .models import Cliente, Plano, Pagamento, ClientePlano, Servico, DiaSemana

# -----------------------------
# CLIENTE
# -----------------------------
class ClienteForm(ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'identidade', 'nome', 'telefone', 'email', 
            'endereco', 'idade', 'sexo', 'imagem', 'status'
        ]
        error_messages = {
            'identidade': {
                'required': "O campo Identidade é obrigatório.",
                'unique': "Já existe um cliente com essa identidade.",
            },
            'nome': {'required': "O nome do cliente é obrigatório."},
            'email': {'invalid': "Digite um e-mail válido."},
        }

ClientePlanoFormSet = inlineformset_factory(
    Cliente,
    ClientePlano,
    fields=['plano', 'data_inicio', 'data_fim', 'ativo'],
    extra=1,
    can_delete=False
)

# -----------------------------
# PLANO
# -----------------------------
class PlanoForm(forms.ModelForm):
    servicos = forms.ModelMultipleChoiceField(
        queryset=Servico.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Plano
        fields = [
            'tipo',         
            'nome',
            'preco',
            'descricao',
            'dias_por_semana',
            'status',
            'servicos',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'preco': forms.NumberInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dias_por_semana': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'servicos': forms.CheckboxSelectMultiple(),
        }

# -----------------------------
# PAGAMENTO
# -----------------------------
class PagamentoForm(forms.ModelForm):
    class Meta:
        model = Pagamento
        fields = ['cliente', 'plano', 'metodo', 'juros', 'descontos', 'total'] 
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'plano': forms.Select(attrs={'class': 'form-control'}),
            'metodo': forms.Select(attrs={'class': 'form-control'}),
            'juros': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'descontos': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            
        }
    
    def clean_total(self):
        total = self.cleaned_data.get('total')
        if total is not None and total < 0:
            raise forms.ValidationError("O total não pode ser negativo.")
        return total
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['plano'].queryset = Plano.objects.select_related('tipo').all()
        self.fields['cliente'].queryset = Cliente.objects.all()

        self.fields['plano'].label_from_instance = lambda obj: f"{obj.nome} ({obj.tipo.get_nome_display()}) - R$ {obj.preco}"

# -----------------------------
# SERVIÇO
# -----------------------------
class ServicoForm(forms.ModelForm):
    dias = forms.ModelMultipleChoiceField(
        queryset=DiaSemana.objects.exclude(nome__iexact='domingo').order_by('id'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    planos = forms.ModelMultipleChoiceField(
        queryset=Plano.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Servico
        fields = ['nome', 'descricao', 'horario', 'dias', 'planos']
        widgets = {
            'horario': forms.TimeInput(format='%H:%M', attrs={'placeholder': 'HH:MM', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows':3}),
        }
