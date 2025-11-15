import os
import sys
import time
import cv2
import argparse
from datetime import timedelta
from django.utils import timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente, Assistencia

parser = argparse.ArgumentParser()
parser.add_argument('--target-id', type=int, help='ID do cliente alvo (opcional)')
parser.add_argument('--timeout', type=int, default=25, help='Timeout em segundos')
parser.add_argument('--cooldown', type=int, default=3600, help='Cooldown em segundos')
parser.add_argument('--threshold', type=float, default=60.0, help='Limiar de confiança')
args = parser.parse_args()

# CAMINHO ABSOLUTO
trainer_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'trainer.yml'))

if not os.path.exists(trainer_path):
    print(f"ERROR: trainer.yml não encontrado em {trainer_path}")
    sys.exit(2)

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(trainer_path)
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

print(f"\n[INFO] Iniciando reconhecimento (timeout={args.timeout}s)...\n")

start = time.time()
cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("ERROR: câmera não disponível")
    sys.exit(3)

message = "Nenhum reconhecimento."
found = False

try:
    while True:
        if time.time() - start > args.timeout:
            message = "Timeout: nenhum rosto reconhecido."
            break

        ret, frame = cam.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.2, 5)

        for (x, y, w, h) in faces:
            try:
                id_pred, confidence = recognizer.predict(gray[y:y+h, x:x+w])
            except:
                continue

            if confidence <= args.threshold:
                if args.target_id and id_pred != args.target_id:
                    continue

                try:
                    cliente = Cliente.objects.get(pk=id_pred)
                except Cliente.DoesNotExist:
                    message = f"Reconhecido id={id_pred} (não cadastrado)."
                    found = True
                    break

                plano_ativo = cliente.clienteplano_set.filter(ativo=True).first()
                if not plano_ativo:
                    message = f"{cliente.nome}: sem plano ativo."
                    found = True
                    break

                now = timezone.now()
                cutoff = now - timedelta(seconds=args.cooldown)
                recent = Assistencia.objects.filter(cliente=cliente, tipo="facial", data__gte=cutoff).exists()
                
                if recent:
                    message = f"{cliente.nome}: presença já registrada recentemente."
                else:
                    Assistencia.objects.create(cliente=cliente, tipo="facial")
                    message = f"✅ Assistência registrada para {cliente.nome}!"
                
                found = True
                break

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        cv2.putText(frame, message, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow('Reconhecimento', frame)

        if found:
            cv2.waitKey(800)
            break

        k = cv2.waitKey(10) & 0xff
        if k == 27:
            message = "Cancelado pelo usuário."
            break
finally:
    cam.release()
    cv2.destroyAllWindows()
    print(message)