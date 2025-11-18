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
from .models import Assistencia, ClientePlano
from .models import Servico, DiaSemana, PlanoServico
from .models import Cliente, Plano, Pagamento
from .forms import ClienteForm, PlanoForm, PagamentoForm, ClientePlanoFormSet, ServicoForm
from .models import Servico
from threading import Lock
from django.db import models
from django.db.models import Q

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

#Assistencias
@login_required
def assistencia_list(request):
    assistencias = Assistencia.objects. select_related('cliente','usuario').order_by('-data','-hora')
    return render(request, 'assistencias/lista.html',{'assistencias':assistencias})

@login_required
def assistencia_create(request):
    clientes= Cliente.objects.filter(status=True)
    if request.method =="POST":
        cliente_id = request.POST.get('cliente')
        tipo = request.POST.get('tipo')
        cliente=get_object_or_404(Cliente, pk=cliente_id)

        Assistencia.objects.create(
            cliente=cliente,
            usuario=request.user,
            tipo=tipo
        )
        return redirect('assistencia_list')
    return render(request, 'assistencias/form.html', {'clientes':clientes})

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

# reconhecimento
@login_required
def reconhecimento_once_view(request):
    """Executa reconhecimento facial uma vez"""
    
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'academia', 'reconhecimento'))
    reconhece_path = os.path.join(base, 'reconhece.py')
    trainer_path = os.path.join(base, 'trainer.yml')
    
    # Validações
    if not os.path.exists(trainer_path):
        messages.error(request, '❌ Modelo não treinado! Treine o modelo primeiro.')
        return redirect('assistencia_list')
    
    if not os.path.exists(reconhece_path):
        messages.error(request, f'❌ Script não encontrado: {reconhece_path}')
        return redirect('assistencia_list')
    
    try:
        python_exec = sys.executable
        # Abre em nova janela no Windows
        creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        
        subprocess.Popen([python_exec, reconhece_path], creationflags=creationflags)
        messages.success(request, '🎥 Câmera aberta! Pressione Q para fechar.')
        
    except Exception as e:
        messages.error(request, f'❌ Erro ao abrir câmera: {str(e)}')
    
    return redirect('assistencia_list')  # ✅ Volta para lista de assistências

@login_required
def assistencia_csv_export(request):
    """Exporta assistências para CSV"""
    assistencias = Assistencia.objects.select_related('cliente', 'usuario').order_by('-data', '-hora')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="assistencias_{date.today().strftime("%Y%m%d")}.csv"'
    
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
    for a in assistencias:
        writer.writerow([
            a.id,
            a.cliente.nome,
            a.cliente.identidade,
            'IA Facial' if a.tipo == 'facial' else 'Manual',
            a.data.strftime('%d/%m/%Y'),
            a.hora.strftime('%H:%M:%S'),
            a.usuario.username if a.usuario else 'Sistema'
        ])
    
    return response

@login_required
def assistencia_limpar(request):
    """Limpa todas as assistências após confirmação"""
    if request.method == 'POST':
        count = Assistencia.objects.count()
        Assistencia.objects.all().delete()
        messages.success(request, f'🗑️ {count} assistência(s) deletada(s) com sucesso!')
        return redirect('assistencia_list')
    
    # Se não for POST, mostra página de confirmação
    total = Assistencia.objects.count()
    return render(request, 'assistencias/confirmar_limpar.html', {'total': total})

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
