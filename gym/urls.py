# gym/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/novo/', views.criar_cliente, name='criar_cliente'),
    path('clientes/<int:pk>/', views.cliente_detail, name='cliente_detail'),
    path('clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),

    path('planos/', views.plano_list, name='plano_list'),
    path('planos/novo/', views.plano_create, name='plano_create'),
    path('planos/<int:pk>/editar/', views.plano_edit, name='plano_edit'),

    path('pagamentos/', views.pagamento_list, name='pagamento_list'),
    path('pagamentos/novo/', views.pagamento_create, name='pagamento_create'),
    path('pagamentos/csv/', views.pagamento_csv, name='pagamento_csv'),

    path('login/', auth_views.LoginView.as_view(template_name='gym/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
   
]
