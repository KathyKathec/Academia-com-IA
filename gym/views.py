# gym/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, timedelta, datetime
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
    """Lista todos os clientes com busca"""
    query = request.GET.get('q', '')  #  Captura termo de busca
    
    clientes_list = Cliente.objects.all()
    
    #  Aplica filtro de busca se houver termo
    if query:
        clientes_list = clientes_list.filter(
            Q(nome__icontains=query) |
            Q(identidade__icontains=query) |
            Q(telefone__icontains=query) |
            Q(email__icontains=query)
        )
    
    clientes_list = clientes_list.order_by('-id')
    
    clientes_data = []
    hoje = date.today()
    
    for cliente in clientes_list:
        plano_ativo = ClientePlano.objects.filter(
            cliente=cliente, 
            ativo=True
        ).first()
        
        if plano_ativo:
            dias_restantes = (plano_ativo.data_fim - hoje).days
            
            if dias_restantes < 0:
                status_vencimento = f'Vencido há {abs(dias_restantes)} dias'
                status_class = 'text-danger'
            elif dias_restantes == 0:
                status_vencimento = 'Vence hoje'
                status_class = 'text-warning'
            elif dias_restantes <= 7:
                status_vencimento = f'Vence em {dias_restantes} dias'
                status_class = 'text-warning'
            else:
                status_vencimento = plano_ativo.data_fim.strftime('%d/%m/%Y')
                status_class = 'text-success'
            
            plano_nome = plano_ativo.plano.nome
        else:
            status_vencimento = 'Sem plano'
            status_class = 'text-secondary'
            plano_nome = '-'
        
        clientes_data.append({
            'pk': cliente.pk,
            'nome': cliente.nome,
            'identidade': cliente.identidade,
            'telefone': cliente.telefone,
            'email': cliente.email,
            'imagem': cliente.imagem,
            'plano': plano_nome,
            'status_vencimento': status_vencimento,
            'status_class': status_class,
        })
    
    context = {
        'clientes': clientes_data,
        'query': query,  #  Passa o termo de busca para o template
        'total': len(clientes_data),  #  Total de resultados
    }
    
    return render(request, 'clientes/lista.html', context)
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
    """Cria um novo pagamento"""
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        plano_id = request.POST.get('plano')
        metodo = request.POST.get('metodo')
        
        try:
            cliente = Cliente.objects.get(pk=cliente_id)
            plano = Plano.objects.get(pk=plano_id)
            
            # Cria o pagamento
            pagamento = Pagamento.objects.create(
                cliente=cliente,
                plano=plano,
                metodo=metodo,
                total=plano.preco,
                usuario=request.user
            )
            
            # Cria ou atualiza o ClientePlano
            cliente_plano, created = ClientePlano.objects.get_or_create(
                cliente=cliente,
                plano=plano,
                defaults={
                    'data_inicio': date.today(),
                    'data_fim': date.today() + timedelta(days=plano.tipo.dias),
                    'ativo': True
                }
            )
            
            if not created:
                # Atualiza plano existente
                cliente_plano.data_inicio = date.today()
                cliente_plano.data_fim = date.today() + timedelta(days=plano.tipo.dias)
                cliente_plano.ativo = True
                cliente_plano.save()
            
            messages.success(request, f'✅ Pagamento registrado com sucesso! Plano válido até {cliente_plano.data_fim.strftime("%d/%m/%Y")}')
            return redirect('pagamento_list')
            
        except Exception as e:
            messages.error(request, f'❌ Erro ao processar pagamento: {str(e)}')
    
    # ✅ DEFINE OS MÉTODOS DE PAGAMENTO
    metodos = [
        {
            'value': 'dinheiro',
            'label': 'Dinheiro',
            'icon': 'cash-stack',
            'color': 'success'
        },
        {
            'value': 'cartao',
            'label': 'Cartão',
            'icon': 'credit-card',
            'color': 'primary'
        },
        {
            'value': 'pix',
            'label': 'PIX',
            'icon': 'qr-code',
            'color': 'info'
        }
    ]
    
    clientes = Cliente.objects.filter(status=True).order_by('nome')
    planos = Plano.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes,
        'planos': planos,
        'metodos': metodos,  # ✅ Passa os métodos para o template
    }
    
    return render(request, 'pagamento/form.html', context)
# Listar pagamentos
def pagamento_list(request):
    """Lista todos os pagamentos com filtros"""
    search = request.GET.get('search', '')
    metodo = request.GET.get('metodo', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    pagamentos = Pagamento.objects.select_related('cliente', 'plano', 'usuario').all()
    
    # Filtro de busca por nome/identidade
    if search:
        pagamentos = pagamentos.filter(
            Q(cliente__nome__icontains=search) |
            Q(cliente__identidade__icontains=search)
        )
    
    # Filtro por método de pagamento
    if metodo:
        pagamentos = pagamentos.filter(metodo=metodo)
    
    # Filtro por data início
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            pagamentos = pagamentos.filter(data__gte=data_inicio_obj)
        except ValueError:
            messages.warning(request, '⚠️ Data de início inválida')
    
    # Filtro por data fim
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            pagamentos = pagamentos.filter(data__lte=data_fim_obj)
        except ValueError:
            messages.warning(request, '⚠️ Data de fim inválida')
    
    pagamentos = pagamentos.order_by('-data')
    
    # Calcula estatísticas
    total_valor = sum(p.total for p in pagamentos)
    total_pagamentos = pagamentos.count()
    
    # Atalhos de datas
    hoje = date.today()
    semana_inicio = hoje - timedelta(days=hoje.weekday())
    mes_inicio = hoje.replace(day=1)
    
    context = {
        'pagamentos': pagamentos,
        'search': search,
        'metodo': metodo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_valor': total_valor,
        'total_pagamentos': total_pagamentos,
        'hoje': hoje.strftime('%Y-%m-%d'),
        'semana_inicio': semana_inicio.strftime('%Y-%m-%d'),
        'mes_inicio': mes_inicio.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'pagamento/lista.html', context)


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
    """Lista todas as presenças com filtros"""
    # ✅ Captura parâmetros de filtro
    cliente_id = request.GET.get('cliente', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    tipo = request.GET.get('tipo', '')
    
    # Busca todas as presenças
    presencas = Presenca.objects.all().select_related('cliente', 'usuario')
    
    #  Aplica filtro de cliente
    if cliente_id:
        presencas = presencas.filter(cliente_id=cliente_id)
    
    #  Aplica filtro de data início
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            presencas = presencas.filter(data__gte=data_inicio_obj)
        except ValueError:
            messages.warning(request, '⚠️ Data de início inválida')
    
    #  Aplica filtro de data fim
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            presencas = presencas.filter(data__lte=data_fim_obj)
        except ValueError:
            messages.warning(request, '⚠️ Data de fim inválida')
    
    #  Aplica filtro de tipo
    if tipo:
        presencas = presencas.filter(tipo=tipo)
    
    presencas = presencas.order_by('-data', '-hora')
    
    #  Busca todos os clientes para o select
    clientes = Cliente.objects.filter(status=True).order_by('nome')
    
    #  Calcula estatísticas
    total_presencas = presencas.count()
    presencas_facial = presencas.filter(tipo='facial').count()
    presencas_manual = presencas.filter(tipo='manual').count()
    
    #  Calcula datas para atalhos
    hoje = date.today()
    semana_inicio = hoje - timedelta(days=hoje.weekday())
    mes_inicio = hoje.replace(day=1)
    
    context = {
        'presencas': presencas,
        'clientes': clientes,
        'cliente_id': cliente_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo': tipo,
        'total_presencas': total_presencas,
        'presencas_facial': presencas_facial,
        'presencas_manual': presencas_manual,
        'hoje': hoje.strftime('%Y-%m-%d'),
        'semana_inicio': semana_inicio.strftime('%Y-%m-%d'),
        'mes_inicio': mes_inicio.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'presencas/lista.html', context)

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
    """Exporta presenças para CSV COM FILTROS"""
    #  Captura os mesmos filtros da listagem
    cliente_id = request.GET.get('cliente', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    tipo = request.GET.get('tipo', '')
    
    #  Aplica os mesmos filtros
    presencas = Presenca.objects.select_related('cliente', 'usuario').all()
    
    if cliente_id:
        presencas = presencas.filter(cliente_id=cliente_id)
    
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            presencas = presencas.filter(data__gte=data_inicio_obj)
        except ValueError:
            pass
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            presencas = presencas.filter(data__lte=data_fim_obj)
        except ValueError:
            pass
    
    if tipo:
        presencas = presencas.filter(tipo=tipo)
    
    presencas = presencas.order_by('-data', '-hora')
    
    # Nome do arquivo com filtros
    nome_arquivo = f'presencas_{date.today().strftime("%Y%m%d")}'
    if cliente_id:
        cliente = Cliente.objects.get(pk=cliente_id)
        nome_arquivo += f'_{cliente.nome.replace(" ", "_")}'
    if data_inicio or data_fim:
        nome_arquivo += '_periodo'
    nome_arquivo += '.csv'
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    
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

