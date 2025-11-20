import os
import sys
import cv2
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente, Presenca

trainer_path = os.path.join(os.path.dirname(__file__), 'trainer.yml')

if not os.path.exists(trainer_path):
    print(f"❌ Modelo não encontrado: {trainer_path}")
    print("Execute primeiro: python academia/reconhecimento/treina.py")
    sys.exit(1)

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(trainer_path)

detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

clientes = {c.id: c.nome for c in Cliente.objects.all()}
print(f"🧠 {len(clientes)} clientes carregados")

last_recognition = {}
TIMEOUT_SECONDS = 15

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Não foi possível abrir a câmera!")
    sys.exit(1)

print("\n🎥 Câmera aberta. Pressione 'q' para sair.\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(100, 100)
    )
    
    for (x, y, w, h) in faces:
        # ✅ MESMA NORMALIZAÇÃO DO TREINO
        face_roi = gray[y:y+h, x:x+w]
        face_resized = cv2.resize(face_roi, (200, 200))
        
        # Reconhecimento
        client_id, confidence = recognizer.predict(face_resized)
        
        # ✅ Ajuste o threshold (quanto menor, mais confiança)
        if confidence < 70:  # Ajuste este valor se necessário
            nome = clientes.get(client_id, f"ID {client_id}")
            
            # Timeout entre reconhecimentos
            now = datetime.now()
            if client_id in last_recognition:
                diff = (now - last_recognition[client_id]).seconds
                if diff < TIMEOUT_SECONDS:
                    texto = f"{nome} (aguarde {TIMEOUT_SECONDS - diff}s)"
                    cor = (255, 165, 0)  # Laranja
                else:
                    # Registra presença
                    try:
                        cliente = Cliente.objects.get(id=client_id)
                        Presenca.objects.create(cliente=cliente, tipo='facial')
                        last_recognition[client_id] = now
                        print(f"✅ Presença registrada: {nome} ({confidence:.1f})")
                        texto = f"{nome} - REGISTRADO!"
                        cor = (0, 255, 0)  # Verde
                    except Exception as e:
                        print(f"❌ Erro ao registrar: {e}")
                        texto = f"{nome} - ERRO"
                        cor = (0, 0, 255)  # Vermelho
            else:
                # Primeira vez
                try:
                    cliente = Cliente.objects.get(id=client_id)
                    Presenca.objects.create(cliente=cliente, tipo='facial')
                    last_recognition[client_id] = now
                    print(f"✅ Presença registrada: {nome} ({confidence:.1f})")
                    texto = f"{nome} - REGISTRADO!"
                    cor = (0, 255, 0)
                except Exception as e:
                    print(f"❌ Erro: {e}")
                    texto = f"{nome} - ERRO"
                    cor = (0, 0, 255)
        else:
            texto = f"Desconhecido ({confidence:.1f})"
            cor = (0, 0, 255)
        
        # Desenha retângulo e texto
        cv2.rectangle(frame, (x, y), (x+w, y+h), cor, 2)
        cv2.putText(frame, texto, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
    
    cv2.imshow('Reconhecimento Facial - Pressione Q para sair', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\n👋 Câmera fechada.")