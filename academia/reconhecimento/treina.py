import os
import sys
import cv2
import numpy as np
from pathlib import Path

# ✅ CONFIGURA ENCODING UTF-8 NO WINDOWS
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
print("TREINAMENTO DO MODELO")
print("="*70 + "\n")

# Detector
detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def carregar_imagens():
    """Carrega imagens com pre-processamento otimizado"""
    face_samples = []
    ids = []
    
    if not dataset_dir.exists():
        return face_samples, ids
    
    for pasta_cliente in dataset_dir.iterdir():
        if not pasta_cliente.is_dir():
            continue
        
        try:
            client_id = int(pasta_cliente.name)
            cliente = Cliente.objects.get(id=client_id)
        except:
            continue
        
        ok = 0
        total = 0
        
        for img_file in sorted(pasta_cliente.glob('*.jpg')):
            total += 1
            gray = cv2.imread(str(img_file), cv2.IMREAD_GRAYSCALE)
            
            if gray is None:
                continue
            
            # ✅ SÓ REDIMENSIONA - SEM PROCESSAMENTO
            gray = cv2.resize(gray, (200, 200))
            
            face_samples.append(gray)
            ids.append(client_id)
            ok += 1
        
        print(f"[OK] ID {client_id:3d} - {cliente.nome:30s} | {ok}/{total}")
    
    return face_samples, ids

# Carrega imagens
face_samples, ids = carregar_imagens()

if len(face_samples) < 10:
    print(f"\n[ERRO] Apenas {len(face_samples)} imagens!")
    sys.exit(1)

print(f"\n[INFO] Total: {len(face_samples)} faces de {len(set(ids))} clientes")
print("[INFO] Treinando...\n")

# CRIA RECONHECEDOR
recognizer = cv2.face.LBPHFaceRecognizer_create()

# Treina
recognizer.train(face_samples, np.array(ids))

# ✅ GARANTE QUE O DIRETORIO EXISTE
trainer_path.parent.mkdir(parents=True, exist_ok=True)

# Salva
recognizer.write(str(trainer_path))

# Verifica se foi criado
if trainer_path.exists():
    tamanho = trainer_path.stat().st_size
    print(f"[OK] Modelo salvo: {trainer_path}")
    print(f"[OK] Tamanho: {tamanho} bytes\n")
else:
    print("[ERRO] Falha ao salvar modelo!\n")