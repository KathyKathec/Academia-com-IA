import cv2
import os
import sys
from pathlib import Path

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

def capturar_imagens(cliente_id, num_fotos=50):
    """Captura múltiplas fotos do cliente para treinamento"""
    
    try:
        cliente = Cliente.objects.get(id=cliente_id)
        print(f"\n{'='*60}")
        print(f"CAPTURA DE IMAGENS - {cliente.nome}")
        print(f"{'='*60}")
    except Cliente.DoesNotExist:
        print(f"[ERRO] Cliente ID {cliente_id} nao encontrado!")
        return
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    dataset_dir = BASE_DIR / 'dataset' / str(cliente_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] Salvando em: {dataset_dir}")
    print(f"[INFO] Meta: {num_fotos} fotos")
    print("\nINSTRUCOES:")
    print("  1. Posicione seu rosto no centro")
    print("  2. Mantenha iluminacao clara")
    print("  3. Faca pequenas variacoes de angulo")
    print("  4. Pressione ESC para cancelar\n")
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cam.isOpened():
        print("[ERRO] Nao foi possivel acessar camera!")
        return
    
    count = 0
    print("[INFO] Aguardando deteccao de rosto...")
    
    try:
        while count < num_fotos:
            ret, frame = cam.read()
            
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(100, 100)
            )
            
            if len(faces) == 1:
                (x, y, w, h) = faces[0]
                
                face_roi = gray[y:y+h, x:x+w]
                
                filename = dataset_dir / f"{count+1:03d}.jpg"
                cv2.imwrite(str(filename), face_roi)
                
                count += 1
                print(f"[OK] {count:02d}/{num_fotos} capturadas", end='\r')
                
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"{count}/{num_fotos}", (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            elif len(faces) == 0:
                cv2.putText(frame, "NENHUM ROSTO", (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                cv2.putText(frame, "MULTIPLAS FACES", (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            cv2.imshow('Captura de Fotos', frame)
            
            if cv2.waitKey(1) & 0xFF == 27:
                break
    
    finally:
        cam.release()
        cv2.destroyAllWindows()
    
    print(f"\n\n[OK] {count} fotos capturadas com sucesso!\n")
    return count >= num_fotos * 0.8

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("[ERRO] Uso: python captura.py <ID_CLIENTE>")
        sys.exit(1)
    
    try:
        cliente_id = int(sys.argv[1])
        capturar_imagens(cliente_id)
    except ValueError:
        print("[ERRO] ID deve ser numerico!")