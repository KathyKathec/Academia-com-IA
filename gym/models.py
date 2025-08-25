from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
from django.db import models
from django.contrib.auth.models import User  # importamos el User de Django

# -----------------------------
# Tipo de Plano
# -----------------------------
class TipoPlano(models.Model):
    TIPOS = [
        ("mensal", "Mensal"),
        ("diario", "Diário"),
        ("semanal", "Semanal"),
        ("outros", "Outros"),
    ]
    nome = models.CharField(max_length=50, choices=TIPOS, default="mensal")

    def __str__(self):
        return self.nome

# -----------------------------
# Plano
# -----------------------------
class Plano(models.Model):
    tipo = models.ForeignKey(TipoPlano, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    descricao = models.TextField(blank=True, null=True)
    dias_por_semana = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    status = models.BooleanField(default=True)  # ativo/desativado
    
    def __str__(self):
        return f"{self.nome} - {self.tipo.nome}"

# -----------------------------
# Cliente
# -----------------------------
class Cliente(models.Model):
    identidade = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logradouro=models.TextField(blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)
    imagem = models.ImageField(upload_to='clientes/', blank=True, null=True)
    status = models.BooleanField(default=True)  # ativo ou não, se verdadeiro entao esta ativo.
    
    def __str__(self):
        return self.nome

# -----------------------------
# ClientePlano (relacional)
# -----------------------------
class ClientePlano(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE)
    data_inicio = models.DateField()
    data_fim = models.DateField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    status_vencimento = models.CharField(max_length=20, choices=[("atrasado","Atrasado"),("em dia","Em dia")])  
    
    def __str__(self):
        return f"{self.cliente.nome} - {self.plano.nome}"

# -----------------------------
# Pagamento
# -----------------------------
class Pagamento(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # quem registrou
    data = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=50)
    juros = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    descontos = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    
    def __str__(self):
        return f"Pagamento {self.id} - {self.cliente.nome}"

# -----------------------------
# Assistência (com IA no futuro)
# -----------------------------
class Assistencia(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # admin ou funcionário
    data = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20, choices=[("manual","Manual"),("facial","Facial com IA")])
    
    def __str__(self):
        return f"{self.cliente.nome} - {self.data} {self.tipo}"
