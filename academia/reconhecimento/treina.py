import os
import sys
import cv2
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente

# CAMINHOS ABSOLUTOS
dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../dataset'))
trainer_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'trainer.yml'))

print(f"\n[INFO] Dataset: {dataset_dir}")
print(f"[INFO] Trainer: {trainer_path}\n")

detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def carregar_imagens():
    face_samples = []
    ids = []
    
    if not os.path.exists(dataset_dir):
        print(f"❌ Dataset não encontrado: {dataset_dir}")
        return face_samples, ids
    
    for pasta_cliente in os.listdir(dataset_dir):
        pasta_path = os.path.join(dataset_dir, pasta_cliente)
        if not os.path.isdir(pasta_path):
            continue
        
        try:
            client_id = int(pasta_cliente)
        except ValueError:
            continue
        
        for img_name in os.listdir(pasta_path):
            if not img_name.lower().endswith('.jpg'):
                continue
            
            img_path = os.path.join(pasta_path, img_name)
            gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if gray_img is None:
                continue
            
            faces = detector.detectMultiScale(gray_img)
            for (x, y, w, h) in faces:
                face_samples.append(gray_img[y:y+h, x:x+w])
                ids.append(client_id)
    
    return face_samples, ids

print("[INFO] Carregando imagens...")
face_samples, ids = carregar_imagens()

if len(face_samples) == 0:
    print("❌ Nenhuma imagem encontrada!")
    sys.exit(1)

print(f"✅ {len(face_samples)} faces carregadas de {len(set(ids))} clientes\n")

print("[INFO] Treinando modelo...")
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train(face_samples, np.array(ids))
recognizer.write(trainer_path)

print(f"✅ Modelo treinado e salvo em: {trainer_path}\n")

clientes_treinados = Cliente.objects.filter(id__in=set(ids))
print(f"🧠 Clientes treinados: {len(clientes_treinados)}")
for c in clientes_treinados:
    print(f"   - {c.id}: {c.nome}")