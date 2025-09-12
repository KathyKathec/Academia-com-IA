# gym/forms.py

from django.forms import ModelForm, inlineformset_factory
from django import forms
from .models import Cliente, Plano, Pagamento, ClientePlano


class ClienteForm(ModelForm):
    class Meta:
        model = Cliente
        fields = ['identidade', 'nome', 'telefone', 'email', 'endereco', 'idade', 'sexo', 'imagem', 'status']
        error_messages = {
            'identidade': {
                'required': "O campo Identidade é obrigatório.",
                'unique': "Já existe um cliente com essa identidade.",
            },
            'nome': {
                'required': "O nome do cliente é obrigatório.",
            },
            'idade': {
                'invalid': "Informe uma idade válida.",
            },
            'email': {
                'invalid': "Digite um e-mail válido.",
            },
            
        }
# Inline formset: criar o Plano junto com o Cliente
ClientePlanoFormSet = inlineformset_factory(
    Cliente,
    ClientePlano,
    fields=['plano', 'data_inicio', 'data_fim', 'ativo'],
    extra=1,
    can_delete=False
)



        
class PlanoForm(ModelForm):
    class Meta:
        model = Plano
        fields = ['tipo', 'nome', 'preco', 'descricao', 'dias_por_semana', 'status']
        error_messages = {
            'nome': {
                'required': "O nome do plano é obrigatório.",
            },
            'preco': {
                'required': "O preço é obrigatório.",
                'invalid': "Digite um valor numérico válido.",
            },
        }



class PagamentoForm(ModelForm):
    class Meta:
        model = Pagamento
        fields = ['cliente', 'plano', 'metodo', 'juros', 'descontos', 'total']
        error_messages = {
            'cliente': {
                'required': "Selecione um cliente.",
            },
            'plano': {
                'required': "Selecione um plano.",
            },
            'metodo': {
                'required': "Informe o método de pagamento.",
            },
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # somente leitura
        self.fields['total'].widget.attrs['readonly'] = True
        #bootstrap
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})




    # validação 
    def clean_idade(self):
        idade = self.cleaned_data.get('idade')
        if idade and idade < 12:
            raise forms.ValidationError("Clientes devem ter pelo menos 12 anos de idade.")
        return idade
    
    def clean_dias_por_semana(self):
        dias = self.cleaned_data.get('dias_por_semana')
        if dias and (dias < 1 or dias > 7):
            raise forms.ValidationError("O número de dias por semana deve estar entre 1 e 7.")
        return dias




