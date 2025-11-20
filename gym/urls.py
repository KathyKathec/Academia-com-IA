# gym/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('home', views.home, name='home'),
    
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/novo/', views.criar_cliente, name='criar_cliente'),
    path('clientes/<int:pk>/', views.cliente_detail, name='cliente_detail'),
    path('clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/deletar/', views.deletar_cliente, name='deletar_cliente'),

    path('planos/', views.plano_list, name='plano_list'),
    path('planos/novo/', views.plano_create, name='plano_create'),
    path('planos/<int:pk>/editar/', views.plano_edit, name='plano_edit'),
    path('planos/<int:pk>/deletar/', views.plano_delete, name='plano_delete'),

    path('pagamentos/', views.pagamento_list, name='pagamento_list'),
    path('pagamentos/csv/', views.pagamento_csv, name='pagamento_csv'),
    path('pagamentos/novo/', views.criar_pagamento, name='criar_pagamento'),
    path('pagamentos/limpar/', views.pagamento_limpar, name='pagamento_limpar'),

    path('servicos/', views.servico_list, name='servico_list'),
    path('servicos/novo/', views.servico_create, name='servico_create'),
    path('servicos/<int:pk>/editar/', views.servico_edit, name='servico_edit'),
    path('servicos/<int:pk>/deletar/', views.servico_delete, name='servico_delete'),

    path('presencas/', views.presenca_list, name='presenca_list'),
    path('presencas/nova/', views.presenca_create, name='presenca_create'),
    path('presencas/csv/', views.presenca_csv_export, name='presenca_csv_export'),
    path('presencas/limpar/', views.presenca_limpar, name='presenca_limpar'),

    path('coletar_imagens_cliente', views.coletar_imagens_cliente, name='coletar_imagens_cliente'),
    path('reconhecimento_one', views.reconhecimento_once_view, name='reconhecimento_once_view'),
    path('treinar_modelo', views.treinar_modelo, name='treinar_modelo'),

    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path('clientes/<int:pk>/coletar/', views.coletar_imagens_cliente, name='coletar_imagens_cliente'),
    path('reconhecimento/treinar/', views.treinar_modelo, name='treinar_modelo'),
    # chama reconhecimento para um cliente específico (POST)
    path('reconhecimento/one/<int:pk>/', views.reconhecimento_once_view, name='reconhecimento_one_cliente'),
    # opcional: rota sem target (não necessária se sempre for por cliente)
    path('reconhecimento/one/', views.reconhecimento_once_view, name='reconhecimento_one'),
  ]
