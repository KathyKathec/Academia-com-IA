from django.contrib import admin
from .models import Plano, Cliente, ClientePlano, TipoPlano, Pagamento, Assistencia  

# Register your models here.

admin.site.register(Plano)
admin.site.register(Cliente)
admin.site.register(ClientePlano)
admin.site.register(TipoPlano)
admin.site.register(Pagamento)
admin.site.register(Assistencia)