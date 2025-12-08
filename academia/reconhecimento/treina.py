import os
import sys
import cv2
import numpy as np
from pathlib import Path

# CONFIGURA ENCODING UTF-8 NO WINDOWS
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente

BASE_DIR = Path(__file__).resolve().parent.parent.parent
dataset_dir = BASE_DIR / 'dataset'
trainer_path = Path(__file__).resolve().parent / 'trainer.yml'

print("\n" + "="*70)
print("TREINAMENTO DO MODELO - DIAGNOSTICO COMPLETO")
print("="*70 + "\n")

# Detector
detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def analisar_imagem(img_path):
    """Analisa qualidade da imagem"""
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    
    if img is None:
        return None, "ERRO: Arquivo corrompido"
    
    # Calcula métricas
    altura, largura = img.shape
    brilho_medio = np.mean(img)
    contraste = np.std(img)
    
    # Tenta detectar face
    faces = detector.detectMultiScale(img, 1.1, 4)
    tem_face = len(faces) > 0
    
    # Classifica qualidade
    problemas = []
    if brilho_medio < 50:
        problemas.append("Muito escura")
    elif brilho_medio > 200:
        problemas.append("Muito clara")
    
    if contraste < 30:
        problemas.append("Baixo contraste")
    
    if not tem_face:
        problemas.append("Sem face detectada")
    
    qualidade = "OK" if not problemas else " | ".join(problemas)
    
    return img, qualidade

def carregar_imagens():
    face_samples = []
    ids = []
    stats = {}
    
    if not dataset_dir.exists():
        print(f"[ERRO] Dataset nao encontrado: {dataset_dir}")
        return face_samples, ids, stats
    
    print("Analisando dataset...\n")
    
    for pasta_cliente in dataset_dir.iterdir():
        if not pasta_cliente.is_dir():
            continue
        
        try:
            client_id = int(pasta_cliente.name)
            cliente = Cliente.objects.get(id=client_id)
        except:
            print(f"[AVISO] Ignorando pasta: {pasta_cliente.name}")
            continue
        
        print(f"\n{'='*70}")
        print(f"CLIENTE ID {client_id}: {cliente.nome}")
        print(f"{'='*70}")
        
        stats[client_id] = {
            'nome': cliente.nome,
            'total': 0,
            'ok': 0,
            'falhas': 0,
            'problemas': []
        }
        
        for img_file in sorted(pasta_cliente.glob('*.jpg')):
            stats[client_id]['total'] += 1
            
            # Analisa imagem
            gray, qualidade = analisar_imagem(img_file)
            
            if gray is None:
                stats[client_id]['falhas'] += 1
                stats[client_id]['problemas'].append(f"{img_file.name}: {qualidade}")
                print(f"  [ERRO] {img_file.name}: {qualidade}")
                continue
            
            if qualidade != "OK":
                print(f"  [AVISO] {img_file.name}: {qualidade}")
            
            # Redimensiona (SEM outros processamentos)
            gray = cv2.resize(gray, (200, 200))
            
            face_samples.append(gray)
            ids.append(client_id)
            stats[client_id]['ok'] += 1
        
        # Mostra resumo do cliente
        total = stats[client_id]['total']
        ok = stats[client_id]['ok']
        falhas = stats[client_id]['falhas']
        taxa = (ok / total * 100) if total > 0 else 0
        
        print(f"\nRESUMO: {ok}/{total} OK ({taxa:.1f}%) | {falhas} falhas")
        
        if taxa < 70:
            print(f"[ATENCAO] Taxa baixa! Recapture com:")
            print(f"  - Melhor iluminacao")
            print(f"  - Face centralizada")
            print(f"  - Sem sombras no rosto")
    
    return face_samples, ids, stats

# Carrega imagens
face_samples, ids, stats = carregar_imagens()

print(f"\n{'='*70}")
print("ESTATISTICAS GERAIS")
print(f"{'='*70}")

if len(face_samples) < 10:
    print(f"[ERRO] Apenas {len(face_samples)} imagens validas!")
    print("[INFO] Necessario: Minimo 10 fotos por cliente")
    print("[INFO] Recomendado: 50+ fotos por cliente")
    print("\nSOLUCAO:")
    print("1. Recapture com melhor qualidade")
    print("2. Use boa iluminacao")
    print("3. Centralize o rosto na camera")
    sys.exit(1)

total_clientes = len(set(ids))
total_faces = len(face_samples)
media = total_faces / total_clientes

print(f"Clientes: {total_clientes}")
print(f"Faces validas: {total_faces}")
print(f"Media: {media:.1f} por cliente")

if media < 30:
    print(f"\n[AVISO] Media baixa! Recapture mais fotos.")

# Lista todos os IDs únicos
ids_unicos = sorted(set(ids))
print(f"\nIDs que serao treinados: {ids_unicos}")

# Mostra distribuição
print(f"\nDistribuicao de faces por cliente:")
from collections import Counter
contagem = Counter(ids)
for client_id in sorted(contagem.keys()):
    cliente = Cliente.objects.get(id=client_id)
    print(f"  ID {client_id:3d} ({cliente.nome:20s}): {contagem[client_id]:3d} fotos")

print(f"\n{'='*70}")
print("INICIANDO TREINAMENTO")
print(f"{'='*70}\n")

# Cria e treina reconhecedor
recognizer = cv2.face.LBPHFaceRecognizer_create()

print(f"[INFO] Treinando com {len(face_samples)} amostras...")
recognizer.train(face_samples, np.array(ids))
print(f"[OK] Treinamento concluido!")

# Salva modelo
trainer_path.parent.mkdir(parents=True, exist_ok=True)
print(f"\n[INFO] Salvando modelo em: {trainer_path}")
recognizer.write(str(trainer_path))

if trainer_path.exists():
    tamanho = trainer_path.stat().st_size
    print(f"[OK] Modelo salvo! ({tamanho} bytes)")
else:
    print(f"[ERRO] Arquivo nao foi criado!")
    sys.exit(1)

# TESTE INTERNO
print(f"\n{'='*70}")
print("VALIDACAO INTERNA")
print(f"{'='*70}\n")

acertos = 0
erros = 0
detalhes_erros = []

for client_id in ids_unicos:
    indices = [i for i, x in enumerate(ids) if x == client_id]
    
    if len(indices) < 3:
        continue
    
    import random
    test_indices = random.sample(indices, min(5, len(indices)))
    
    cliente = Cliente.objects.get(id=client_id)
    
    print(f"\nTestando ID {client_id} ({cliente.nome}):")
    
    for idx in test_indices:
        sample = face_samples[idx]
        pred_id, confidence = recognizer.predict(sample)
        
        if pred_id == client_id:
            acertos += 1
            status = "[OK]"
        else:
            erros += 1
            status = "[ERRO]"
            detalhes_erros.append(f"ID {client_id} previsto como {pred_id} (conf: {confidence:.1f})")
        
        print(f"  {status} Previu: ID {pred_id:3d} | Confianca: {confidence:5.1f}")

taxa_acerto = (acertos / (acertos + erros) * 100) if (acertos + erros) > 0 else 0

print(f"\n{'='*70}")
print(f"RESULTADO FINAL: {acertos} acertos / {erros} erros ({taxa_acerto:.1f}%)")
print(f"{'='*70}")

if erros > 0:
    print(f"\nERROS DETALHADOS:")
    for erro in detalhes_erros:
        print(f"  - {erro}")

if taxa_acerto >= 90:
    print("\n[OK] EXCELENTE! Modelo pronto.")
elif taxa_acerto >= 70:
    print("\n[AVISO] ACEITAVEL. Pode funcionar, mas considere recapturar.")
else:
    print("\n[ERRO] RUIM! Recapture TODAS as fotos!")
    print("\nDICAS:")
    print("  - Use iluminacao uniforme")
    print("  - Evite sombras no rosto")
    print("  - Centralize a face")
    print("  - Faca pequenas variacoes de angulo")

print(f"\n{'='*70}\n")