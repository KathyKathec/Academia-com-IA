# gym/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, timedelta
import csv
from .models import Assistencia
from .models import Servico, DiaSemana, PlanoServico
from .models import Cliente, Plano, Pagamento
from .forms import ClienteForm, PlanoForm, PagamentoForm, ClientePlanoFormSet

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

            # Agora inicializa o formset com a instância do cliente
            formset = ClientePlanoFormSet(request.POST, instance=cliente)
            if formset.is_valid():
                formset.save()
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
        plano_ativo = cliente.clienteplano_set.filter(ativo=True).first()
        
        if plano_ativo:
            data_inicio = plano_ativo.data_inicio
            tipo_plano = plano_ativo.plano.tipo.nome  # assumindo que tipo tem campo nome
            
            # Calcula duração baseado no tipo do plano
            if 'anual' in tipo_plano.lower():
                duracao = 365
            elif 'semestral' in tipo_plano.lower():
                duracao = 180
            elif 'trimestral' in tipo_plano.lower():
                duracao = 90
            else:  # mensal
                duracao = 30
            
            data_vencimento = data_inicio + timedelta(days=duracao)
            dias_restantes = (data_vencimento - date.today()).days

            if dias_restantes < 0:
                status_class = "text-danger"
                status_vencimento = f"Vencido há {abs(dias_restantes)} dias"
            elif dias_restantes <= 7:
                status_class = "text-warning"
                status_vencimento = f"Vence em {dias_restantes} dias"
            else:
                status_class = "text-success"
                status_vencimento = f"Em dia (vence em {dias_restantes} dias)"
        else:
            status_class = "text-secondary"
            status_vencimento = "Sem plano ativo"
            
        clientes_info.append({
            'pk': cliente.pk,
            'nome': cliente.nome,
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
            form.save()
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
def pagamento_create(request):
    planos = Plano.objects.filter(status=True)
    clientes = Cliente.objects.filter(status=True)

    if request.method == "POST":
        form = PagamentoForm(request.POST)
        if form.is_valid():
            pagamento = form.save(commit=False)
            pagamento.usuario = request.user  # atribui o usuário logado
            pagamento.save()
            return redirect('pagamento_list')
    else:
        form = PagamentoForm()

    return render(request, 'pagamento/form.html', {
        'form': form,
        'planos': planos,
        'clientes': clientes
    })


# Listar pagamentos
def pagamento_list(request):
    pagamentos = Pagamento.objects.all()
    
    return render(request, 'pagamento/lista.html', {'pagamentos': pagamentos})


# Exportar pagamentos para CSV
@login_required
def pagamento_csv(request):
    pagamentos = Pagamento.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pagamentos.csv"'
    writer = csv.writer(response)
    writer.writerow(['Cliente', 'Plano', 'Método', 'Total', 'Data'])
    for pagamento in pagamentos:
        writer.writerow([
            str(pagamento.cliente),
            str(pagamento.plano),
            str(pagamento.metodo),
            str(pagamento.total),
            pagamento.data.strftime('%d/%m/%Y %H:%M')
        ])
    return response

@login_required
def servico_list(request):
    servicos= Servico.objects.prefetch_related('dias').all()
    return render(request, 'servicos/lista.html',{'servicos': servicos})

@login_required
def servico_create(request):
    dias= DiaSemana.objects.all()
    planos = Plano.objects.filter(status=True)

    if request.method == "POST":
        nome = request.POST.get('nome')
        descricao=request.POST.get('descricao')
        horario = request.POST.get('horario')
        dias_selecionados= request.POST.getlist('dias')
        planos_selecionados= request.POST.getlist('planos')

        servico= Servico.objects.create(nome=nome, descricao=descricao, horario=horario)
        servico.dias.set(dias_selecionados)

        #para asociar planos
        for plano_id in planos_selecionados:
            plano= get_object_or_404(Plano, pk=plano_id)
            PlanoServico.objects.create(plano=plano, servico=servico)

        return redirect('servico_list')
    return render(request, 'servicos/form.html', {'dias':dias, 'planos':planos})

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
