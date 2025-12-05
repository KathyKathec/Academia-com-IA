import os
import sys
import cv2
import argparse

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
# garantir raiz do projeto no PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia.settings')
import django
django.setup()

from gym.models import Cliente

parser = argparse.ArgumentParser()
parser.add_argument('--id', type=int, required=True, help='ID do cliente')
parser.add_argument('--count', type=int, default=30, help='Número de imagens')
args = parser.parse_args()

client_id = args.id
count_target = args.count

# CAMINHO ABSOLUTO para dataset (na raiz do projeto)
dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../dataset'))
client_path = os.path.join(dataset_dir, str(client_id))
os.makedirs(client_path, exist_ok=True)

print(f"\n[INFO] Capturando {count_target} imagens para cliente {client_id}")
print(f"[INFO] Salvando em: {client_path}\n")

face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
cam = cv2.VideoCapture(0)

if not cam.isOpened():
    print("❌ Câmera não disponível!")
    sys.exit(1)

count = 0
try:
    while count < count_target:
        ret, img = cam.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_detector.detectMultiScale(gray, 1.3, 5)
        
        for (x, y, w, h) in faces:
            count += 1
            filename = os.path.join(client_path, f"User.{client_id}.{count}.jpg")
            cv2.imwrite(filename, gray[y:y+h, x:x+w])
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            print(f"[+] {count}/{count_target}")
        
        cv2.putText(img, f'{count}/{count_target}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow(f'Capturando Cliente {client_id}', img)
        
        k = cv2.waitKey(100) & 0xff
        if k == 27:
            break
finally:
    cam.release()
    cv2.destroyAllWindows()

print(f"\n✅ {count} imagens salvas em: {client_path}")