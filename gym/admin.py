from django.contrib import admin
from django.contrib.auth.models import Group
from .models import Cliente, Plano, Pagamento, Servico, Presenca, ClientePlano, TipoPlano, DiaSemana

# Customiza o título do admin
admin.site.site_header = "Academia System - Administração"
admin.site.site_title = "Academia Admin"
admin.site.index_title = "Painel de Administração"

# Cliente Admin
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'identidade', 'telefone', 'email', 'status')
    list_filter = ('status',)
    search_fields = ('nome', 'identidade', 'email', 'telefone')
    
    fieldsets = (
        ('Informações Pessoais', {
            'fields': ('nome', 'identidade', 'telefone', 'email', 'imagem', 'idade', 'sexo')
        }),
        ('Endereço', {
            'fields': ('endereco',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )

# Plano Admin 
@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'preco', 'get_servicos')
    list_filter = ('tipo',)
    search_fields = ('nome', 'descricao')
    
    def get_servicos(self, obj):
        return ", ".join([s.nome for s in obj.servicos.all()])
    get_servicos.short_description = 'Serviços'

# Pagamento Admin
@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'plano', 'metodo', 'total', 'data', 'usuario')
    list_filter = ('metodo', 'data')
    search_fields = ('cliente__nome',)
    readonly_fields = ('data', 'usuario', 'total')
    date_hierarchy = 'data'

# Serviço Admin
@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'horario', 'get_planos_count')
    search_fields = ('nome', 'descricao')
    filter_horizontal = ('dias',)  # ✅ Este pode ficar porque 'dias' não tem tabela intermediária
    
    def get_planos_count(self, obj):
        return obj.planos.count()
    get_planos_count.short_description = 'Qtd. Planos'

# Presença Admin
@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'tipo', 'data', 'hora', 'usuario')
    list_filter = ('tipo', 'data')
    search_fields = ('cliente__nome',)
    date_hierarchy = 'data'
    readonly_fields = ('data', 'hora')

# ClientePlano Admin
@admin.register(ClientePlano)
class ClientePlanoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'plano', 'data_inicio', 'data_fim', 'ativo', 'status_vencimento')
    list_filter = ('ativo', 'status_vencimento', 'data_inicio')
    search_fields = ('cliente__nome', 'plano__nome')
    readonly_fields = ('data_inicio',)

# TipoPlano Admin
@admin.register(TipoPlano)
class TipoPlanoAdmin(admin.ModelAdmin):
    list_display = ('get_nome_display', 'dias')
    list_filter = ('nome',)

# DiaSemana Admin
@admin.register(DiaSemana)
class DiaSemanaAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

# Remove grupo (opcional)
try:
    admin.site.unregister(Group)
except:
    pass