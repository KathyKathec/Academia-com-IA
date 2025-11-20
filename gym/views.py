# gym/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, timedelta
import csv
import subprocess
import sys
import os
from django.contrib import messages
from .models import ClientePlano
from .models import Servico, DiaSemana, PlanoServico
from .models import Cliente, Plano, Pagamento, ClientePlano, Servico, Presenca
from .forms import ClienteForm, PlanoForm, PagamentoForm, ClientePlanoFormSet, ServicoForm
from .models import Servico
from threading import Lock
from django.db import models
from django.db.models import Q
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

# Lock para evitar múltiplas chamadas simultâneas
capture_lock = Lock()
capture_processes = {}  # rastreia processos em execução

# Home
@login_required
def home(request):
    return render(request, 'home.html')

# Criar cliente com plano 
def criar_cliente(request):
    if request.method == "POST":
        form = ClienteForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Salva cliente primeiro
            cliente = form.save(commit=False)
            cliente.status = True  # cliente ativo
            cliente.save()

            # inicializa o formset com a instância do cliente
            formset = ClientePlanoFormSet(request.POST, instance=cliente)
            if formset.is_valid():
                # Salva os planos SEM calcular data_fim
                planos = formset.save(commit=False)
                for cliente_plano in planos:
                    # Define data_inicio mas NÃO define data_fim
                    # data_fim será definida quando fizer o primeiro pagamento
                    if not cliente_plano.data_inicio:
                        cliente_plano.data_inicio = date.today()
                    cliente_plano.ativo = False  # Inativo até o primeiro pagamento
                    cliente_plano.data_fim = None  # Sem vencimento até o pagamento
                    cliente_plano.save()
                
                messages.warning(request, f"Cliente {cliente.nome} criado! Registre o primeiro pagamento para ativar o plano.")
                return redirect('lista_clientes')
            # se formset não for válido, ele vai mostrar os erros
        else:
            # se form não for válido, cria o formset vazio só pra não quebrar o template
            formset = ClientePlanoFormSet(request.POST)
    else:
        form = ClienteForm()
        formset = ClientePlanoFormSet()

    return render(request, 'clientes/form.html', {
        'form': form,
        'formset': formset,
    })


# Editar cliente 
def editar_cliente(request, pk):
    cliente = Cliente.objects.get(pk=pk)
    form = ClienteForm(request.POST or None, request.FILES or None, instance=cliente)
    formset = ClientePlanoFormSet(request.POST or None, instance=cliente)

    aviso_vencimento = None
    for cp in cliente.clienteplano_set.filter(ativo=True):
        if cp.data_fim:
            dias_restantes = (cp.data_fim - date.today()).days
            if dias_restantes < 0:
                aviso_vencimento = f"Plano {cp.plano.nome} vencido!"
            elif dias_restantes <= 7:
                aviso_vencimento = f"Plano {cp.plano.nome} vence em {dias_restantes} dias"

    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('lista_clientes')

    return render(request, 'clientes/form.html', {
        'form': form,
        'formset': formset,
        'aviso_vencimento': aviso_vencimento
    })




#Listar clientes

from datetime import date, timedelta

@login_required
def lista_clientes(request):
    clientes = Cliente.objects.all()
    clientes_info = []
    
    for cliente in clientes:
        # DEBUG: imprime no console
        plano_ativo = cliente.clienteplano_set.filter(ativo=True).first()
        print(f"Cliente: {cliente.nome}")
        print(f"Plano ativo: {plano_ativo}")
        if plano_ativo:
            print(f"  - Plano: {plano_ativo.plano.nome}")
            print(f"  - Data fim: {plano_ativo.data_fim}")
            print(f"  - Ativo: {plano_ativo.ativo}")
        print("---")
        
        if plano_ativo and plano_ativo.data_fim:
            # USA data_fim diretamente (já foi calculada no pagamento)
            data_vencimento = plano_ativo.data_fim
            dias_restantes = (data_vencimento - date.today()).days

            if dias_restantes < 0:
                status_class = "text-danger"
                status_vencimento = f"Vencido há {abs(dias_restantes)} dias"
            elif dias_restantes <= 7:
                status_class = "text-warning"
                status_vencimento = f"Vence em {dias_restantes} dias"
            else:
                status_class = "text-success"
                status_vencimento = f"Vence em {dias_restantes} dias"
        else:
            status_class = "text-secondary"
            status_vencimento = "Sem plano ativo"
            
        clientes_info.append({
            'pk': cliente.pk,
            'nome': cliente.nome,
            'imagem': cliente.imagem,
            'identidade': cliente.identidade,
            'plano': plano_ativo.plano.nome if plano_ativo else "-",
            'status_vencimento': status_vencimento,
            'status_class': status_class
        })
    
    return render(request, 'clientes/lista.html', {
        'clientes': clientes_info,
        'today': date.today()
    })

# delete cliente
def deletar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        cliente.delete()
        return redirect('lista_clientes')
    return render(request, 'clientes/confirm_delete.html', {'cliente': cliente})


# Detalhes do cliente

def cliente_detail(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    planos_ativos = cliente.clienteplano_set.filter(ativo=True)
    pagamentos = cliente.pagamento_set.all().order_by('-data')
    return render(request, 'clientes/detail.html', {
        'cliente': cliente,
        'planos_ativos': planos_ativos,
        'pagamentos': pagamentos
    })




# Listar planos
def plano_list(request):
    planos = Plano.objects.all()
    return render(request, 'plano/lista.html', {'planos': planos})

# Criar plano
def plano_create(request):
    if request.method == 'POST':
        form = PlanoForm(request.POST)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.save()
            form.save_m2m()  # salva as relações com serviços
            return redirect('plano_list')
    else:
        form = PlanoForm()
    return render(request, 'plano/form.html', {'form': form})

#Editar plano
def plano_edit(request, pk):
    plano = get_object_or_404(Plano, pk=pk)
    if request.method == 'POST':
        form = PlanoForm(request.POST, instance=plano)
        if form.is_valid():
            form.save()
            return redirect('plano_list')
    else:
        form = PlanoForm(instance=plano)
    return render(request, 'plano/form.html', {'form': form})

#deletar plano
@login_required
def plano_delete(request, pk):
    """Deleta um plano"""
    plano = get_object_or_404(Plano, pk=pk)
    
    if request.method == 'POST':
        nome_plano = plano.nome
        plano.delete()
        messages.success(request, f'🗑️ Plano "{nome_plano}" deletado com sucesso!')
        return redirect('plano_list')
    
    # Verifica quantos clientes têm este plano
    clientes_com_plano = ClientePlano.objects.filter(plano=plano, ativo=True).count()
    
    return render(request, 'plano/confirmar_delete.html', {
        'plano': plano,
        'clientes_com_plano': clientes_com_plano
    })


# Criar pagamento

@login_required
def criar_pagamento(request):
    if request.method == 'POST':
        form = PagamentoForm(request.POST)
        if form.is_valid():
            pagamento = form.save(commit=False)
            pagamento.usuario = request.user
            pagamento.save()  # O total é calculado automaticamente no save() do modelo
            
            cliente = pagamento.cliente
            plano = pagamento.plano
            duracao_dias = plano.tipo.dias
            
            # Data do pagamento
            data_pagamento = pagamento.data.date() if hasattr(pagamento.data, 'date') else pagamento.data
            
            # Desativa planos anteriores DIFERENTES
            planos_antigos = ClientePlano.objects.filter(
                cliente=cliente,
                ativo=True
            ).exclude(plano=plano)
            
            if planos_antigos.exists():
                for plano_antigo in planos_antigos:
                    plano_antigo.ativo = False
                    plano_antigo.data_fim = data_pagamento  # Encerra na data do novo pagamento
                    plano_antigo.status_vencimento = 'cancelado'
                    plano_antigo.save()
                    print(f"❌ Plano desativado: {plano_antigo.plano.nome} (Cliente: {cliente.nome})")
            
            # Busca ou cria ClientePlano para o plano atual
            cliente_plano, created = ClientePlano.objects.get_or_create(
                cliente=cliente,
                plano=plano,
                defaults={
                    'data_inicio': data_pagamento,
                    'data_fim': data_pagamento + timedelta(days=duracao_dias),
                    'ativo': True,
                    'status_vencimento': 'em dia'
                }
            )
            
            if not created:
                # Se já existe este plano, renova/estende
                if cliente_plano.data_fim and cliente_plano.data_fim >= data_pagamento and cliente_plano.ativo:
                    # Ainda não venceu: estende
                    cliente_plano.data_fim = cliente_plano.data_fim + timedelta(days=duracao_dias)
                else:
                    # Já venceu ou estava inativo: renova
                    cliente_plano.data_inicio = data_pagamento
                    cliente_plano.data_fim = data_pagamento + timedelta(days=duracao_dias)
                    cliente_plano.ativo = True
                    cliente_plano.status_vencimento = 'em dia'
                cliente_plano.save()
            
            nova_data = cliente_plano.data_fim
            messages.success(request, f'✅ Pagamento registrado! Plano: {plano.nome} | Vencimento: {nova_data.strftime("%d/%m/%Y")}')
            
            # ✅ Informa se houve troca de plano
            if planos_antigos.exists():
                planos_desc = ", ".join([p.plano.nome for p in planos_antigos])
                messages.info(request, f'ℹ️ Plano(s) anterior(es) desativado(s): {planos_desc}')
            
            return redirect('pagamento_list')
    else:
        form = PagamentoForm()
    
    # ✅ MANTÉM AS LISTAS para o template
    planos = Plano.objects.all()
    clientes = Cliente.objects.all()
    
    return render(request, 'pagamento/form.html', {
        'form': form,
        'planos': planos,
        'clientes': clientes
    })


# Listar pagamentos
def pagamento_list(request):
    # Pega o termo de busca
    search = request.GET.get('search', '')
    
    pagamentos = Pagamento.objects.select_related('cliente', 'plano', 'usuario').all()
    
    # Aplica filtro se houver busca
    if search:
        pagamentos = pagamentos.filter(
            models.Q(cliente__nome__icontains=search) | 
            models.Q(cliente__identidade__icontains=search)
        )
    
    pagamentos = pagamentos.order_by('-data')
    
    return render(request, 'pagamento/lista.html', {
        'pagamentos': pagamentos,
        'search': search
    })


# Exportar pagamentos para CSV
@login_required
def pagamento_csv(request):
    pagamentos = Pagamento.objects.select_related('cliente', 'plano', 'plano__tipo', 'usuario').all()
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="pagamentos.csv"'
    
    writer = csv.writer(response, delimiter=';') 
    
    # Cabeçalho
    writer.writerow([
        'ID',
        'Cliente',
        'Identidade',
        'Plano',
        'Tipo de Plano',
        'Método',
        'Valor do Plano',
        'Juros',
        'Descontos',
        'Total Pago',
        'Data/Hora',
        'Registrado por'
    ])
    
    # dados formatados
    for p in pagamentos:
        writer.writerow([
            p.id,
            p.cliente.nome,
            p.cliente.identidade,
            p.plano.nome,
            p.plano.tipo.get_nome_display(),
            p.get_metodo_display(),
            f'R$ {p.plano.preco:.2f}'.replace('.', ','),
            f'R$ {(p.juros or 0):.2f}'.replace('.', ','),
            f'R$ {(p.descontos or 0):.2f}'.replace('.', ','),
            f'R$ {p.total:.2f}'.replace('.', ','),
            p.data.strftime('%d/%m/%Y %H:%M:%S'),
            p.usuario.username if p.usuario else 'Sistema'
        ])
    
    return response
# Limpar todos os pagamentos
@login_required
def pagamento_limpar(request):
    """Limpa todos os pagamentos após confirmação"""
    if request.method == 'POST':
        count = Pagamento.objects.count()
        Pagamento.objects.all().delete()
        messages.success(request, f'🗑️ {count} pagamento(s) deletado(s) com sucesso!')
        return redirect('pagamento_list')
    
    # Se não for POST, mostra página de confirmação
    total = Pagamento.objects.count()
    total_valor = sum(p.total for p in Pagamento.objects.all())
    return render(request, 'pagamento/confirmar_limpar.html', {
        'total': total,
        'total_valor': total_valor
    })


# Serviço views
@login_required
def servico_list(request):
    servicos = Servico.objects.prefetch_related('dias', 'planos').all()
    return render(request, 'servicos/lista.html', {'servicos': servicos})

@login_required
def servico_create(request):
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.save()
            # salva M2M se disponível
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            # associa planos se o campo existir no form
            planos_qs = form.cleaned_data.get('planos') if 'planos' in form.cleaned_data else None
            if planos_qs is not None:
                servico.planos.set(planos_qs)
            return redirect('servico_list')
    else:
        form = ServicoForm()
    return render(request, 'servicos/form.html', {'form': form})

@login_required
def servico_edit(request, pk):
    servico = get_object_or_404(Servico, pk=pk)
    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            planos_qs = form.cleaned_data.get('planos') if 'planos' in form.cleaned_data else None
            if planos_qs is not None:
                servico.planos.set(planos_qs)
            return redirect('servico_list')
    else:
        form = ServicoForm(instance=servico)
    return render(request, 'servicos/form.html', {'form': form, 'servico': servico})


#deletar serviço

def servico_delete(request, pk):
    """Deleta um serviço"""
    servico = get_object_or_404(Servico, pk=pk)
    
    if request.method == 'POST':
        nome_servico = servico.nome
        servico.delete()
        messages.success(request, f'🗑️ Serviço "{nome_servico}" deletado com sucesso!')
        return redirect('servico_list')
    
    # Verifica quantos planos usam este serviço
    planos_com_servico = servico.planos.count()
    
    return render(request, 'servicos/confirmar_deletar.html', {
        'servico': servico,
        'planos_com_servico': planos_com_servico,
        'planos': servico.planos.all()
    })


#coleta de imagens
@login_required
def coletar_imagens_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'academia', 'reconhecimento'))
    script = os.path.join(base, 'coleta.py')
    python_exec = sys.executable
    
    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    
    try:
        proc = subprocess.Popen([python_exec, script, '--id', str(pk), '--count', '30'], creationflags=creationflags)
        messages.success(request, f"Coleta iniciada para {cliente.nome}. Feche ESC para terminar.")
    except Exception as exc:
        messages.error(request, f"Erro: {exc}")
    
    return redirect('cliente_detail', pk=pk)



# treinamento de modelo
@login_required
def treinar_modelo(request):
    if request.method != 'POST':
        return redirect('lista_clientes')
    
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'academia', 'reconhecimento'))
    script = os.path.join(base, 'treina.py')
    python_exec = sys.executable
    
    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    
    try:
        proc = subprocess.run([python_exec, script], capture_output=True, text=True, timeout=120, creationflags=creationflags)
        output = (proc.stdout or proc.stderr).strip()
        messages.success(request, output or "Modelo treinado com sucesso!")
    except Exception as exc:
        messages.error(request, f"Erro: {exc}")
    
    return redirect(request.META.get('HTTP_REFERER') or 'lista_clientes')
#presenca 
@login_required
def presenca_list(request):
    presencas = Presenca.objects.select_related('cliente', 'usuario').order_by('-data', '-hora')
    return render(request, 'presencas/lista.html', {'presencas': presencas})

@login_required
def presenca_create(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        tipo = request.POST.get('tipo', 'manual')
        
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        Presenca.objects.create(
            cliente=cliente,
            usuario=request.user,
            tipo=tipo
        )
        
        messages.success(request, f'✅ Presença de {cliente.nome} registrada!')
        return redirect('presenca_list')
    
    clientes = Cliente.objects.filter(status=True).order_by('nome')
    return render(request, 'presencas/form.html', {'clientes': clientes})

@login_required
def presenca_csv_export(request):
    """Exporta presenças para CSV"""
    presencas = Presenca.objects.select_related('cliente', 'usuario').order_by('-data', '-hora')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="presencas_{date.today().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response, delimiter=';')
    
    # Cabeçalho
    writer.writerow([
        'ID',
        'Cliente',
        'Identidade',
        'Tipo',
        'Data',
        'Hora',
        'Registrado por'
    ])
    
    # Dados
    for p in presencas:
        writer.writerow([
            p.id,
            p.cliente.nome,
            p.cliente.identidade,
            'IA Facial' if p.tipo == 'facial' else 'Manual',
            p.data.strftime('%d/%m/%Y'),
            p.hora.strftime('%H:%M:%S'),
            p.usuario.username if p.usuario else 'Sistema'
        ])
    
    return response

@login_required
def presenca_limpar(request):
    """Limpa todas as presenças após confirmação"""
    if request.method == 'POST':
        count = Presenca.objects.count()
        Presenca.objects.all().delete()
        messages.success(request, f'🗑️ {count} presença(s) deletada(s) com sucesso!')
        return redirect('presenca_list')
    
    total = Presenca.objects.count()
    return render(request, 'presencas/confirmar_limpar.html', {'total': total})

@login_required
def reconhecimento_once_view(request):
    """Executa reconhecimento facial uma vez"""
    
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'academia', 'reconhecimento'))
    reconhece_path = os.path.join(base, 'reconhece.py')
    trainer_path = os.path.join(base, 'trainer.yml')
    
    if not os.path.exists(trainer_path):
        messages.error(request, '❌ Modelo não treinado! Treine o modelo primeiro.')
        return redirect('presenca_list')
    
    if not os.path.exists(reconhece_path):
        messages.error(request, f'❌ Script não encontrado: {reconhece_path}')
        return redirect('presenca_list')
    
    try:
        python_exec = sys.executable
        creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        subprocess.Popen([python_exec, reconhece_path], creationflags=creationflags)
        messages.success(request, '🎥 Câmera aberta! Pressione Q para fechar.')
    except Exception as e:
        messages.error(request, f'❌ Erro ao abrir câmera: {str(e)}')
    
    return redirect('presenca_list')

# Login
def login_view(request):
    """View de login"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'✅ Bem-vindo, {user.username}!')
            return redirect('home')
        else:
            messages.error(request, '❌ Usuário ou senha incorretos!')
    
    return render(request, 'login/login.html')

# Logout
@login_required
def logout_view(request):
    """View de logout"""
    username = request.user.username
    logout(request)
    messages.success(request, f'👋 Até logo, {username}!')
    return redirect('login')

# Registro (já existe, mas vou adicionar aqui para referência)
@login_required
def registro_view(request):
    """Registra novo usuário - apenas para usuários autorizados"""
    
    if not request.user.is_staff:
        messages.error(request, '❌ Você não tem permissão para criar usuários!')
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        is_staff = request.POST.get('is_staff') == 'on'
        
        if not username or not password:
            messages.error(request, '❌ Preencha todos os campos obrigatórios!')
            return render(request, 'login/registro.html')
        
        if len(password) < 4:
            messages.error(request, '❌ A senha deve ter no mínimo 4 caracteres!')
            return render(request, 'login/registro.html')
        
        if password != password_confirm:
            messages.error(request, '❌ As senhas não coincidem!')
            return render(request, 'login/registro.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'❌ O usuário "{username}" já existe!')
            return render(request, 'login/registro.html')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        if is_staff:
            user.is_staff = True
            user.save()
        
        messages.success(request, f'✅ Usuário "{username}" criado com sucesso!')
        return redirect('home')
    
    return render(request, 'login/registro.html')

